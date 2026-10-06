from fastapi import APIRouter, Depends, HTTPException, Security, Query, BackgroundTasks
from fastapi.responses import StreamingResponse
import io
import csv
from typing import List, Optional
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import or_, select, update
from app.core.database import get_db
from app.auth.deps import get_authorized_actor, get_current_user
from app.models import Device, User, Site, APIKey, UserRole, VoucherSale, VoucherBatch
from app.models.core import decrypt_device_secrets
from app.services import hotspot_cache
from app.services import voucher_jobs
import routeros_api
import paramiko
from uuid import UUID
from datetime import datetime
import time
import logging
import re
import os
import json
import redis
import redis.exceptions

logger = logging.getLogger(__name__)

router = APIRouter()

# How stale cached hotspot data must be (in seconds) before /summary and
# /system-info report `stale: True`. Must stay a comfortable margin above
# agents/monitor_agent.py's DEEP_INSPECT_INTERVAL (default 30s, env override
# on the agent container) -- that's how often "active"/"system" are normally
# rewritten. Not imported directly: the backend and monitor agent are
# separate containers/deployments, so this is a single named constant with
# this comment as the pointer to its source of truth instead of wiring an
# env var or shared config module across that boundary for one value. If
# DEEP_INSPECT_INTERVAL is ever raised, raise this too (keep >= 3x it).
#
# 90, not 60 (2x): during a voucher-write burst, each write forces a
# ~14.5s blocked refetch of the "users" dataset on the agent's deep-inspect
# loop; with several hotspot devices sharing that sequential poll loop, one
# iteration can approach the old 60s threshold on perfectly healthy data,
# flapping this flag (and the operator-facing health badge) to stale/red
# with nothing actually wrong. 90s (3x DEEP_INSPECT_INTERVAL) gives enough
# margin to absorb that without masking a genuine outage.
HOTSPOT_STALE_THRESHOLD_SECONDS = 90

# Redis client for caching hotspot reads
try:
    redis_client = redis.Redis(
        host=os.getenv("REDIS_HOST", "redis"),
        port=6379,
        db=0,
        decode_responses=True
    )
    redis_client.ping()
except Exception:
    redis_client = None
    logger.warning("Redis unavailable; hotspot caching disabled.")

def cache_key(device_id: str, endpoint: str) -> str:
    return f"hotspot:{device_id}:{endpoint}"


def _redis_setex(key: str, ttl: int, value: str):
    """Set Redis key with TTL, logging errors instead of silently ignoring."""
    if not redis_client:
        return
    try:
        redis_client.setex(key, ttl, value)
    except redis.exceptions.RedisError as e:
        logger.warning(f"Redis cache write failed for {key}: {e}")


def _redis_get(key: str) -> Optional[str]:
    """Get Redis key, logging errors instead of silently ignoring."""
    if not redis_client:
        return None
    try:
        return redis_client.get(key)
    except redis.exceptions.RedisError as e:
        logger.warning(f"Redis cache read failed for {key}: {e}")
        return None


# RouterOS API connection cache (shared across requests within this process)
_router_pool_cache = {}
_CONN_CACHE_TTL = int(os.getenv("ROUTER_CONN_CACHE_TTL", "60"))

class PooledConnection:
    """Wrapper that keeps the underlying pool alive for reuse."""
    __slots__ = ("_pool",)

    def __init__(self, pool):
        self._pool = pool

    def get_api(self):
        return self._pool.get_api()

    def disconnect(self):
        # Intentional no-op: cache manages lifecycle
        pass

def _cache_key(ip, port):
    return (ip, int(port))

def get_api_pool(ip, username, password, port=8728):
    key = _cache_key(ip, port)
    now = time.time()
    cached = _router_pool_cache.get(key)

    if cached:
        pool, last_used = cached
        if now - last_used < _CONN_CACHE_TTL:
            try:
                api = pool.get_api()
                api.get_resource('/system/resource').get()
                _router_pool_cache[key] = (pool, now)
                return PooledConnection(pool)
            except Exception:
                logger.warning(f"Stale pool for {ip}:{port}, reconnecting...")
                try:
                    pool.disconnect()
                except Exception:
                    pass
        else:
            try:
                pool.disconnect()
            except Exception:
                pass

    pool = routeros_api.RouterOsApiPool(
        ip,
        username=username,
        password=password,
        port=port,
        plaintext_login=True,
        use_ssl=False
    )
    _router_pool_cache[key] = (pool, now)
    logger.info(f"New RouterOS API connection to {ip}:{port}")
    return PooledConnection(pool)

def _evict_pool(ip, port=8728):
    """Forcefully close and remove a cached pool (used on protocol desync)."""
    key = _cache_key(ip, port)
    cached = _router_pool_cache.pop(key, None)
    if cached:
        pool, _ = cached
        try:
            pool.disconnect()
        except Exception:
            pass
        logger.info(f"Evicted pool for {ip}:{port}")

# Schemas
class HotspotUser(BaseModel):
    name: str
    password: Optional[str] = None
    profile: Optional[str] = "default"
    uptime: Optional[str] = None
    bytes_in: Optional[int] = 0
    bytes_out: Optional[int] = 0
    limit_uptime: Optional[str] = None
    limit_bytes_total: Optional[int] = None
    comment: Optional[str] = None

class HotspotProfile(BaseModel):
    name: str
    rateLimit: Optional[str] = None
    sharedUsers: Optional[int] = 1

class BatchUserCreate(BaseModel):
    qty: int
    prefix: Optional[str] = ""
    profile: Optional[str] = "default"
    time_limit: Optional[str] = None
    data_limit: Optional[str] = None
    length: Optional[int] = 10
    random_mode: Optional[bool] = False
    format: Optional[str] = "alphanumeric" # alphanumeric, numeric

class HotspotActive(BaseModel):
    id: Optional[str] = None
    user: str
    address: str
    uptime: str
    bytes_in: int
    bytes_out: int
    mac_address: Optional[str] = None
    remaining_time: Optional[str] = None
    limit_uptime: Optional[str] = None
    limit_bytes_total: Optional[int] = None

class SaleRecord(BaseModel):
    device_id: UUID
    username: str
    profile: Optional[str] = "default"
    uptime: Optional[str] = "0s"
    bytes: Optional[int] = 0
    comment: Optional[str] = ""


def parse_routeros_time(time_str: str) -> int:
    """Converts RouterOS time (1d2h3m4s or HH:MM:SS) to seconds."""
    if not time_str or time_str in ("0s", "00:00:00", ""):
        return 0
    
    # Handle HH:MM:SS format
    if ":" in time_str:
        try:
            parts = [p for p in time_str.split(':') if p.strip()]
            if len(parts) == 3: # HH:MM:SS
                h, m, s = map(int, parts)
                return h * 3600 + m * 60 + s
            elif len(parts) == 2: # MM:SS
                m, s = map(int, parts)
                return m * 60 + s
        except (ValueError, TypeError):
            pass # Fall through to regex-like parser
            
    # Handle 1d2h3m4s format
    total_seconds = 0
    current_val = ""
    multipliers = {'d': 86400, 'h': 3600, 'm': 60, 's': 1}
    
    for char in time_str:
        if char.isdigit():
            current_val += char
        elif char in multipliers:
            if current_val:
                total_seconds += int(current_val) * multipliers[char]
                current_val = ""
                
    return total_seconds

def format_routeros_time(seconds: int) -> str:
    """Converts seconds back to RouterOS time string."""
    if seconds <= 0:
        return "0s"

    periods = [
        ('d', 86400),
        ('h', 3600),
        ('m', 60),
        ('s', 1)
    ]

    result = ""
    for suffix, count in periods:
        if seconds >= count:
            val = seconds // count
            result += f"{val}{suffix}"
            seconds %= count

    return result or "0s"

async def sync_hotspot_sales(device: Device, db: AsyncSession):
    """
    Syncs sold/used vouchers from MikroTik to the local VoucherSale table.
    A voucher is considered 'sold' if uptime > 0.
    Optimized to fetch existing records in bulk and commit inserts in one transaction.
    """
    connection = None
    try:
        db_port = getattr(device, 'ssh_port', 8728) or 8728
        port = 8728 if int(db_port) == 22 else db_port

        connection = get_api_pool(device.ip_address, device.ssh_username or 'admin', device.ssh_password or 'admin', int(port))
        api = connection.get_api()

        users_resource = api.get_resource('/ip/hotspot/user')
        users = users_resource.get()
        logger.info(f"Sync: Found {len(users)} total hotspot users on device {device.name}")

        # Build price map
        hs_settings = device.voucher_template or {}
        profile_pricing = hs_settings.get('profile_pricing', {})
        default_currency = hs_settings.get('default_currency', 'GMD')

        # Build case-insensitive lookup index
        profile_pricing_lower = {k.lower(): v for k, v in profile_pricing.items()}

        def get_pricing(p_name):
            key = (p_name or '').lower()
            if key in profile_pricing_lower:
                entry = profile_pricing_lower[key]
                return entry['price'], entry['currency']
            import re
            match = re.search(r'(\d+)$', p_name or '')
            if match:
                return float(match.group(1)), default_currency
            return 0, default_currency

        # Collect users with uptime > 0
        uptime_users = []
        for u in users:
            uptime_str = u.get('uptime', '0s')
            uptime_sec = parse_routeros_time(uptime_str)
            if uptime_sec > 0:
                uptime_users.append({
                    'name': u.get('name'),
                    'comment': u.get('comment', ''),
                    'profile': u.get('profile', 'default'),
                    'uptime_str': uptime_str,
                    'uptime_sec': uptime_sec,
                    'bytes_in': int(u.get('bytes-in', 0)),
                    'bytes_out': int(u.get('bytes-out', 0)),
                })

        if not uptime_users:
            logger.info(f"Sync Stats: {len(users)} total, 0 with uptime, 0 newly recorded")
            return

        # Fetch existing usernames for this device in ONE query
        usernames = [u['name'] for u in uptime_users]
        # Fetch full existing records so we can backfill price=0 entries
        existing_res = await db.execute(
            select(VoucherSale).where(
                VoucherSale.device_id == device.id,
                VoucherSale.username.in_(usernames)
            )
        )
        existing_sales = {sale.username: sale for sale in existing_res.scalars().all()}
        existing_usernames = set(existing_sales.keys())

        new_sales = 0
        updated_prices = 0
        sale_date = datetime.utcnow()
        for u in uptime_users:
            username = u['name']
            price, currency = get_pricing(u['profile'])

            if username in existing_usernames:
                existing = existing_sales[username]
                changed = False
                # Backfill price/currency if the record was saved with price=0
                if existing.price == 0 and price > 0:
                    existing.price = int(price)
                    existing.currency = currency
                    changed = True
                # Backfill profile name if the record was saved with empty profile
                if not existing.profile and u['profile']:
                    existing.profile = u['profile']
                    changed = True
                # Keep uptime and bytes current (real-time push records start at 0s)
                if u['uptime_sec'] > (existing.uptime_sec or 0):
                    existing.uptime = u['uptime_str']
                    existing.uptime_sec = u['uptime_sec']
                    existing.bytes_total = u['bytes_in'] + u['bytes_out']
                    changed = True
                if changed:
                    updated_prices += 1
                continue

            sale = VoucherSale(
                device_id=device.id,
                site_id=device.site_id,
                username=username,
                profile=u['profile'],
                comment=u['comment'],
                uptime=u['uptime_str'],
                uptime_sec=u['uptime_sec'],
                bytes_total=u['bytes_in'] + u['bytes_out'],
                price=int(price),
                currency=currency,
                created_at=sale_date
            )
            db.add(sale)
            new_sales += 1

        logger.info(f"Sync Stats: {len(users)} total, {len(uptime_users)} with uptime, {new_sales} newly recorded, {updated_prices} prices backfilled")

        # Secondary pass: recover profile for orphaned DB records (recorded with empty profile,
        # session ended so they no longer appear in uptime_users) using the full router user list.
        orphaned_res = await db.execute(
            select(VoucherSale).where(
                VoucherSale.device_id == device.id,
                VoucherSale.profile == ''
            )
        )
        orphaned_sales = {sale.username: sale for sale in orphaned_res.scalars().all()}
        if orphaned_sales:
            router_user_map = {u.get('name'): u.get('profile', '') for u in users}
            profile_recovered = 0
            for username, sale in orphaned_sales.items():
                router_profile = router_user_map.get(username, '')
                if router_profile:
                    sale.profile = router_profile
                    p, c = get_pricing(router_profile)
                    if sale.price == 0 and p > 0:
                        sale.price = int(p)
                        sale.currency = c
                    profile_recovered += 1
            if profile_recovered > 0:
                new_sales += profile_recovered  # ensure commit fires
                logger.info(f"Recovered profile for {profile_recovered} orphaned records on {device.name}")

        if new_sales > 0 or updated_prices > 0:
            await db.commit()
            logger.info(f"Synced {new_sales} new + {updated_prices} updated sales for device {device.name}")

    except Exception as e:
        logger.error(f"Sync Hotspot Sales Error: {e}")
        await db.rollback()
    finally:
        if connection:
            try:
                connection.disconnect()
            except Exception:
                pass


@router.get("/{device_id}/users", response_model=List[HotspotUser])
async def get_hotspot_users(
    device_id: str,
    limit: int = Query(200, ge=0, le=5000),
    offset: int = Query(0, ge=0),
    search: Optional[str] = Query(None, description="Filter by username prefix"),
    refresh: bool = Query(False, description="Deprecated, ignored: this read path always serves from cache, never the router"),
    db: AsyncSession = Depends(get_db),
    actor = Depends(get_authorized_actor)
):
    # Fetch device with visibility check
    if isinstance(actor, User) and actor.role == UserRole.SUPER_ADMIN:
        query = select(Device).where(Device.id == UUID(device_id))
    elif isinstance(actor, APIKey) and not actor.organization_id:
        query = select(Device).where(Device.id == UUID(device_id))
    else:
        query = select(Device).join(Site).where(Device.id == UUID(device_id), Site.organization_id == actor.organization_id)

    res = await db.execute(query)
    device = res.scalars().first()
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")

    # THE RULE: this read path never calls the router, not even on a cache
    # miss. A cold cache is a normal state, reported as an empty list with
    # HTTP 200 — never a router fallthrough, never a 500.
    rows, fetched_at = hotspot_cache.read_dataset(device_id, "users")

    # Guard the type before indexing/iterating: a corrupted cache value could
    # store rows as a dict/int/string instead of a list.
    if not isinstance(rows, list):
        logger.error(f"Hotspot users cache rows not a list for device={device_id} dataset=users")
        return []

    def to_model(u):
        return HotspotUser(
            name=u.get('name'),
            password=u.get('password'),
            profile=u.get('profile'),
            uptime=u.get('uptime'),
            # `or 0` guards a raw row with bytes-in/-out set to '' (empty
            # string): without it, int('') raises and the except below
            # discards the *entire* result list for one bad voucher.
            bytes_in=int(u.get('bytes-in', 0) or 0),
            bytes_out=int(u.get('bytes-out', 0) or 0),
            limit_uptime=u.get('limit-uptime'),
            limit_bytes_total=int(u.get('limit-bytes-total')) if u.get('limit-bytes-total') else None,
            comment=u.get('comment')
        )

    try:
        if search:
            # A search filters by name, which requires looking at every row,
            # so there is no cheaper option than building every model here.
            result = [to_model(u) for u in rows]
            result = [u for u in result if search.lower() in (u.name or '').lower()]
            if limit == 0:
                return result[offset:]
            return result[offset:offset + limit]

        # No search filter: this is the common path (e.g. limit=200 on page
        # load against 11k+ rows). Slice the raw dicts FIRST, then build
        # pydantic models only for the page that will actually be returned,
        # instead of constructing (and response-validating) a model for
        # every row and throwing away all but one page of them.
        page = rows[offset:] if limit == 0 else rows[offset:offset + limit]
        return [to_model(u) for u in page]
    except (TypeError, ValueError, AttributeError) as e:
        logger.error(f"Hotspot users cache row unparseable for device={device_id} dataset=users: {e}")
        return []


@router.post("/{device_id}/users")
async def create_hotspot_user(device_id: str, user: HotspotUser, db: AsyncSession = Depends(get_db), actor = Depends(get_authorized_actor)):
    if isinstance(actor, User) and actor.role == UserRole.SUPER_ADMIN:
        query = select(Device).where(Device.id == UUID(device_id))
    elif isinstance(actor, APIKey) and not actor.organization_id:
        query = select(Device).where(Device.id == UUID(device_id))
    else:
        query = select(Device).join(Site).where(Device.id == UUID(device_id), Site.organization_id == actor.organization_id)

    res = await db.execute(query)
    device = res.scalars().first()
    if not device:
         raise HTTPException(status_code=404, detail="Device not found")

    # Decrypt device secrets (required for async SQLAlchemy)
    decrypt_device_secrets(device)

    try:
        port = getattr(device, 'ssh_port', 8728) or 8728
        connection = get_api_pool(device.ip_address, device.ssh_username or 'admin', device.ssh_password or 'admin', int(port))
        api = connection.get_api()

        # Check if exists
        existing = api.get_resource('/ip/hotspot/user').get(name=user.name)
        if existing:
             raise HTTPException(status_code=400, detail="User already exists")

        api.get_resource('/ip/hotspot/user').add(
            name=user.name,
            password=user.password,
            profile=user.profile
        )
        connection.disconnect()
        hotspot_cache.invalidate(device_id, "users")
        hotspot_cache.request_refresh(device_id)
        return {"status": "success"}
    except Exception as e:
        if "User already exists" in str(e): raise e
        logger.error(f"Create User Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
@router.delete("/{device_id}/users/{username}")
async def delete_hotspot_user(device_id: str, username: str, db: AsyncSession = Depends(get_db), actor = Depends(get_authorized_actor)):
    if isinstance(actor, User) and actor.role == UserRole.SUPER_ADMIN:
        query = select(Device).where(Device.id == UUID(device_id))
    elif isinstance(actor, APIKey) and not actor.organization_id:
        query = select(Device).where(Device.id == UUID(device_id))
    else:
        query = select(Device).join(Site).where(Device.id == UUID(device_id), Site.organization_id == actor.organization_id)
    
    res = await db.execute(query)
    device = res.scalars().first()
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")
    
    decrypt_device_secrets(device)
         
    try:
        port = getattr(device, 'ssh_port', 8728) or 8728
        connection = get_api_pool(device.ip_address, device.ssh_username or 'admin', device.ssh_password or 'admin', int(port))
        api = connection.get_api()
        
        resource = api.get_resource('/ip/hotspot/user')
        user_list = resource.get(name=username)
        if not user_list:
             connection.disconnect()
             raise HTTPException(status_code=404, detail="User not found")
             
        # Safely get internal ID (sometimes .id, sometimes id)
        uid = user_list[0].get('.id') or user_list[0].get('id')
        if not uid:
            logger.error(f"Delete failed: Internal ID not found for user {username}. Response: {user_list[0]}")
            connection.disconnect()
            raise HTTPException(status_code=500, detail="Voucher found but internal identifier missing from router response.")

        resource.remove(id=uid)
        connection.disconnect()
        hotspot_cache.invalidate(device_id, "users")
        hotspot_cache.request_refresh(device_id)
        return {"status": "success"}
    except Exception as e:
        logger.error(f"Delete User Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/{device_id}/profiles", response_model=List[dict])
async def get_hotspot_profiles(
    device_id: str,
    refresh: bool = Query(False, description="Deprecated, ignored: this read path always serves from cache, never the router"),
    db: AsyncSession = Depends(get_db),
    actor = Depends(get_authorized_actor)
):
    if isinstance(actor, User) and actor.role == UserRole.SUPER_ADMIN:
        query = select(Device).where(Device.id == UUID(device_id))
    elif isinstance(actor, APIKey) and not actor.organization_id:
        query = select(Device).where(Device.id == UUID(device_id))
    else:
        query = select(Device).join(Site).where(Device.id == UUID(device_id), Site.organization_id == actor.organization_id)

    res = await db.execute(query)
    device = res.scalars().first()
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")

    # THE RULE: this read path never calls the router, not even on a cache
    # miss. A cold cache is a normal state, reported as an empty list with
    # HTTP 200 — never a router fallthrough, never a 500. active_users counts
    # depend on joining the "profiles", "active" and "users" datasets.
    profiles, profiles_fetched_at = hotspot_cache.read_dataset(device_id, "profiles")
    active, active_fetched_at = hotspot_cache.read_dataset(device_id, "active")
    users, users_fetched_at = hotspot_cache.read_dataset(device_id, "users")

    # Guard the type before indexing/iterating: a corrupted cache value could
    # store rows as a dict/int/string instead of a list.
    if not isinstance(profiles, list) or not isinstance(active, list) or not isinstance(users, list):
        logger.error(f"Hotspot profiles cache rows not a list for device={device_id} datasets=profiles,active,users")
        return []

    try:
        # Build user-to-profile mapping
        user_to_profile = {u.get('name'): u.get('profile') for u in users}

        profile_counts = {p.get('name'): 0 for p in profiles}
        for a in active:
            u_name = a.get('user')
            p_name = user_to_profile.get(u_name)
            if p_name in profile_counts:
                profile_counts[p_name] += 1

        # Parse price/currency from local database settings (Device.voucher_template)
        settings = device.voucher_template or {}
        profile_pricing = settings.get('profile_pricing', {})
        default_currency = settings.get('default_currency', 'GMD')

        # Build serializable result dicts
        result = []
        for p in profiles:
            p_name = p.get('name')
            pricing = profile_pricing.get(p_name, {})
            result.append({
                "name": p_name,
                "rate-limit": p.get('rate-limit'),
                "shared-users": p.get('shared-users'),
                "active_users": profile_counts.get(p_name, 0),
                "custom_price": pricing.get('price', 0),
                "custom_currency": pricing.get('currency', default_currency),
            })
    except (TypeError, ValueError, AttributeError) as e:
        logger.error(f"Hotspot profiles cache row unparseable for device={device_id} datasets=profiles,active,users: {e}")
        return []

    return result

class ProfileSettings(BaseModel):
    price: float
    currency: str

@router.post("/{device_id}/profiles/{profile_name}/settings")
async def update_profile_settings(device_id: str, profile_name: str, settings: ProfileSettings, db: AsyncSession = Depends(get_db), actor = Depends(get_authorized_actor)):
    if isinstance(actor, User) and actor.role == UserRole.SUPER_ADMIN:
        query = select(Device).where(Device.id == UUID(device_id))
    elif isinstance(actor, APIKey) and not actor.organization_id:
        query = select(Device).where(Device.id == UUID(device_id))
    else:
        query = select(Device).join(Site).where(Device.id == UUID(device_id), Site.organization_id == actor.organization_id)
    
    res = await db.execute(query)
    device = res.scalars().first()
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")
    
    decrypt_device_secrets(device)
    try:
        import copy
        from sqlalchemy.orm.attributes import flag_modified
        hs_settings = copy.deepcopy(device.voucher_template) or {}
        if 'profile_pricing' not in hs_settings:
            hs_settings['profile_pricing'] = {}

        hs_settings['profile_pricing'][profile_name] = {
            "price": settings.price,
            "currency": settings.currency
        }

        if settings.currency:
            hs_settings['default_currency'] = settings.currency

        device.voucher_template = hs_settings
        flag_modified(device, 'voucher_template')
        db.add(device)

        # Backfill any existing sale records that were recorded with price=0 for this profile
        if settings.price > 0:
            await db.execute(
                update(VoucherSale)
                .where(
                    VoucherSale.device_id == UUID(device_id),
                    VoucherSale.profile == profile_name,
                    VoucherSale.price == 0
                )
                .values(price=int(settings.price), currency=settings.currency)
            )

        await db.commit()

        return {"status": "success"}
    except Exception as e:
        logger.error(f"Update Profile Settings Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/{device_id}/summary")
async def get_hotspot_summary(device_id: str, db: AsyncSession = Depends(get_db), actor = Depends(get_authorized_actor)):
    if isinstance(actor, User) and actor.role == UserRole.SUPER_ADMIN:
        query = select(Device).where(Device.id == UUID(device_id))
    elif isinstance(actor, APIKey) and not actor.organization_id:
        query = select(Device).where(Device.id == UUID(device_id))
    else:
        query = select(Device).join(Site).where(Device.id == UUID(device_id), Site.organization_id == actor.organization_id)

    res = await db.execute(query)
    device = res.scalars().first()
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")

    # THE RULE: this read path never calls the router, not even on a cache
    # miss. A cold cache is a normal state, reported via "stale", not an error.
    active_sessions, active_fetched_at = hotspot_cache.read_dataset(device_id, "active")
    total_users, users_fetched_at = hotspot_cache.read_dataset(device_id, "users")

    try:
        total_bytes_in = sum(int(a.get('bytes-in', 0) or 0) for a in active_sessions)
        total_bytes_out = sum(int(a.get('bytes-out', 0) or 0) for a in active_sessions)

        # Profile Distribution
        profile_dist = {}
        for u in total_users:
            p = u.get('profile', 'default')
            profile_dist[p] = profile_dist.get(p, 0) + 1

        result = {
            "active_count": len(active_sessions),
            "total_vouchers": len(total_users),
            "total_data_mb": round((total_bytes_in + total_bytes_out) / 1024 / 1024, 2),
            "profile_distribution": [{"name": k, "value": v} for k, v in profile_dist.items()]
        }
    except (TypeError, ValueError, AttributeError) as e:
        logger.error(f"Hotspot summary computation failed for device={device_id} datasets=active,users: {e}")
        result = {
            "active_count": 0,
            "total_vouchers": 0,
            "total_data_mb": 0,
            "profile_distribution": []
        }
        active_fetched_at = None
        users_fetched_at = None

    stale = (
        active_fetched_at is None
        or users_fetched_at is None
        or hotspot_cache.age_seconds(active_fetched_at) > HOTSPOT_STALE_THRESHOLD_SECONDS
    )

    result["fetched_at"] = active_fetched_at
    result["stale"] = stale

    return result

@router.get("/{device_id}/system-info")
async def get_router_system_info(device_id: str, db: AsyncSession = Depends(get_db), actor = Depends(get_authorized_actor)):
    if isinstance(actor, User) and actor.role == UserRole.SUPER_ADMIN:
        query = select(Device).where(Device.id == UUID(device_id))
    elif isinstance(actor, APIKey) and not actor.organization_id:
        query = select(Device).where(Device.id == UUID(device_id))
    else:
        query = select(Device).join(Site).where(Device.id == UUID(device_id), Site.organization_id == actor.organization_id)

    res = await db.execute(query)
    device = res.scalars().first()
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")

    # THE RULE: this read path never calls the router, not even on a cache
    # miss. A cold cache is a normal state, reported via "stale", not an error.
    rows, fetched_at = hotspot_cache.read_dataset(device_id, "system")

    # Guard the type before indexing: read_dataset's contract only promises
    # "[] or whatever JSON decoded under the rows key" — a corrupted cache
    # value could store rows as a dict/int/string, and rows[0] on those is
    # not uniformly a TypeError/ValueError/AttributeError (e.g. a dict with
    # an int key 0 would raise KeyError, a string would silently subscript a
    # character). Treat anything that isn't a non-empty list the same as an
    # empty cache, so indexing below is always safe.
    if not isinstance(rows, list) or not rows:
        return {
            "cpu_load": None,
            "free_memory": None,
            "total_memory": None,
            "uptime": None,
            "version": None,
            "board_name": None,
            "fetched_at": None,
            "stale": True,
        }

    info = rows[0]
    try:
        result = {
            "cpu_load": info.get('cpu-load'),
            # `or 0` guards a raw row with free-memory/total-memory set to ''
            # (empty string) -- same guard as the bytes-in/-out conversions
            # elsewhere in this file.
            "free_memory": int(info.get('free-memory', 0) or 0) / 1024 / 1024,
            "total_memory": int(info.get('total-memory', 0) or 0) / 1024 / 1024,
            "uptime": info.get('uptime'),
            "version": info.get('version'),
            "board_name": info.get('board-name')
        }
    except (TypeError, ValueError, AttributeError) as e:
        logger.error(f"Hotspot system-info cache row unparseable for device={device_id} dataset=system: {e}")
        return {
            "cpu_load": None,
            "free_memory": None,
            "total_memory": None,
            "uptime": None,
            "version": None,
            "board_name": None,
            "fetched_at": None,
            "stale": True,
        }

    age = hotspot_cache.age_seconds(fetched_at)
    result["fetched_at"] = fetched_at
    result["stale"] = age is None or age > HOTSPOT_STALE_THRESHOLD_SECONDS
    return result

@router.post("/{device_id}/profiles")
async def create_hotspot_profile(device_id: str, profile: HotspotProfile, db: AsyncSession = Depends(get_db), actor = Depends(get_authorized_actor)):
    if isinstance(actor, User) and actor.role == UserRole.SUPER_ADMIN:
        query = select(Device).where(Device.id == UUID(device_id))
    elif isinstance(actor, APIKey) and not actor.organization_id:
        query = select(Device).where(Device.id == UUID(device_id))
    else:
        query = select(Device).join(Site).where(Device.id == UUID(device_id), Site.organization_id == actor.organization_id)
    
    res = await db.execute(query)
    device = res.scalars().first()
    if not device:
         raise HTTPException(status_code=404, detail="Device not found")
    
    # Decrypt device secrets (required for async SQLAlchemy)
    decrypt_device_secrets(device)
         
    try:
        port = getattr(device, 'ssh_port', 8728) or 8728
        connection = get_api_pool(device.ip_address, device.ssh_username or 'admin', device.ssh_password or 'admin', int(port))
        api = connection.get_api()
        
        params = {
            'name': profile.name,
            'shared-users': str(profile.sharedUsers)
        }
        if profile.rateLimit:
            params['rate-limit'] = profile.rateLimit
            
        api.get_resource('/ip/hotspot/user/profile').add(**params)
        connection.disconnect()
        hotspot_cache.invalidate(device_id, "profiles")
        hotspot_cache.request_refresh(device_id)
        return {"status": "success"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/{device_id}/profiles/{profile_name}")
async def delete_hotspot_profile(device_id: str, profile_name: str, db: AsyncSession = Depends(get_db), actor = Depends(get_authorized_actor)):
    if isinstance(actor, User) and actor.role == UserRole.SUPER_ADMIN:
        query = select(Device).where(Device.id == UUID(device_id))
    elif isinstance(actor, APIKey) and not actor.organization_id:
        query = select(Device).where(Device.id == UUID(device_id))
    else:
        query = select(Device).join(Site).where(Device.id == UUID(device_id), Site.organization_id == actor.organization_id)

    res = await db.execute(query)
    device = res.scalars().first()
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")

    # Decrypt device secrets (required for async SQLAlchemy)
    decrypt_device_secrets(device)

    try:
        port = getattr(device, 'ssh_port', 8728) or 8728
        connection = get_api_pool(device.ip_address, device.ssh_username or 'admin', device.ssh_password or 'admin', int(port))
        api = connection.get_api()

        # In RouterOS API, removing by name usually requires finding the .id first or using the name if the library supports it
        # routeros-api's remove() typically takes an id.
        resource = api.get_resource('/ip/hotspot/user/profile')
        profile = resource.get(name=profile_name)
        if not profile:
             raise HTTPException(status_code=404, detail="Profile not found")

        resource.remove(id=profile[0]['id'])
        connection.disconnect()
        hotspot_cache.invalidate(device_id, "profiles")
        hotspot_cache.request_refresh(device_id)
        return {"status": "success"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/{device_id}/active", response_model=List[HotspotActive])
async def get_active_users(
    device_id: str,
    limit: int = Query(200, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    refresh: bool = Query(False, description="Deprecated, ignored: this read path always serves from cache, never the router"),
    db: AsyncSession = Depends(get_db),
    actor = Depends(get_authorized_actor)
):
    if isinstance(actor, User) and actor.role == UserRole.SUPER_ADMIN:
        query = select(Device).where(Device.id == UUID(device_id))
    elif isinstance(actor, APIKey) and not actor.organization_id:
        query = select(Device).where(Device.id == UUID(device_id))
    else:
        query = select(Device).join(Site).where(Device.id == UUID(device_id), Site.organization_id == actor.organization_id)

    res = await db.execute(query)
    device = res.scalars().first()
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")

    # THE RULE: this read path never calls the router, not even on a cache
    # miss. A cold cache is a normal state, reported as an empty list with
    # HTTP 200 — never a router fallthrough, never a 500. remaining_time
    # depends on joining the "active" and "users" datasets, so both are read
    # here (once each — the users dataset is ~3.6 MB on the real router).
    active, active_fetched_at = hotspot_cache.read_dataset(device_id, "active")
    users, users_fetched_at = hotspot_cache.read_dataset(device_id, "users")

    # Guard the type before indexing/iterating: a corrupted cache value could
    # store rows as a dict/int/string instead of a list.
    if not isinstance(active, list) or not isinstance(users, list):
        logger.error(f"Hotspot active cache rows not a list for device={device_id} datasets=active,users")
        return []

    try:
        user_limits = {
            u.get('name'): {
                'limit-uptime': u.get('limit-uptime'),
                'limit-bytes-total': int(u.get('limit-bytes-total')) if u.get('limit-bytes-total') else None
            }
            for u in users
        }

        results = []
        for a in active:
            username = a.get('user')
            uptime_str = a.get('uptime', '0s')

            limits = user_limits.get(username, {})
            limit_str = limits.get('limit-uptime')
            limit_bytes = limits.get('limit-bytes-total')

            remaining = "UNLIM"

            # 1. Prefer direct router value if available
            router_time_left = a.get('session-time-left')
            if router_time_left:
                remaining = router_time_left
            # 2. Fallback to calculation
            elif limit_str:
                uptime_sec = parse_routeros_time(uptime_str)
                limit_sec = parse_routeros_time(limit_str)
                rem_sec = max(0, limit_sec - uptime_sec)
                remaining = format_routeros_time(rem_sec)

            results.append(HotspotActive(
                id=a.get('.id') or a.get('id'),
                user=username,
                address=a.get('address'),
                uptime=uptime_str,
                bytes_in=int(a.get('bytes-in', 0) or 0),
                bytes_out=int(a.get('bytes-out', 0) or 0),
                mac_address=a.get('mac-address'),
                remaining_time=remaining,
                limit_uptime=limit_str,
                limit_bytes_total=limit_bytes
            ))
    except (TypeError, ValueError, AttributeError) as e:
        logger.error(f"Hotspot active cache row unparseable for device={device_id} datasets=active,users: {e}")
        return []

    return results[offset:offset + limit]

@router.delete("/{device_id}/active/{active_id}")
async def kick_active_user(device_id: str, active_id: str, db: AsyncSession = Depends(get_db), actor = Depends(get_authorized_actor)):
    if isinstance(actor, User) and actor.role == UserRole.SUPER_ADMIN:
        query = select(Device).where(Device.id == UUID(device_id))
    elif isinstance(actor, APIKey) and not actor.organization_id:
        query = select(Device).where(Device.id == UUID(device_id))
    else:
        query = select(Device).join(Site).where(Device.id == UUID(device_id), Site.organization_id == actor.organization_id)
    
    res = await db.execute(query)
    device = res.scalars().first()
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")
    
    # Decrypt device secrets (required for async SQLAlchemy)
    decrypt_device_secrets(device)
        
    try:
        port = getattr(device, 'ssh_port', 8728) or 8728
        connection = get_api_pool(device.ip_address, device.ssh_username or 'admin', device.ssh_password or 'admin', int(port))
        api = connection.get_api()
        api.get_resource('/ip/hotspot/active').remove(id=active_id)
        connection.disconnect()
        # Deliberately NOT invalidating "active" here (I2): all cache writes
        # are gated by DEEP_INSPECT_INTERVAL (~30s), so invalidating would
        # blank the entire active-sessions list -- which the frontend polls
        # every 15s -- for up to 30s after every single kick. A list that is
        # stale by up to 30s is strictly better than one that goes empty; the
        # agent overwrites this key on its own within that window regardless.
        return {"status": "success"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))



class VoucherTemplate(BaseModel):
    header_text: Optional[str] = "Wi-Fi Voucher"
    footer_text: Optional[str] = "Thank you for visiting!"
    logo_url: Optional[str] = None
    color_primary: Optional[str] = "#2563EB"
    profile_pricing: Optional[dict] = {}
    default_currency: Optional[str] = "GMD"
    portal_mode: str = "netguard"

class PortalModeUpdate(BaseModel):
    mode: str

@router.post("/{device_id}/voucher-template")
async def update_voucher_template(device_id: str, template: VoucherTemplate, db: AsyncSession = Depends(get_db), actor = Depends(get_authorized_actor)):
    if isinstance(actor, User) and actor.role == UserRole.SUPER_ADMIN:
        query = select(Device).where(Device.id == UUID(device_id))
    elif isinstance(actor, APIKey) and not actor.organization_id:
        query = select(Device).where(Device.id == UUID(device_id))
    else:
        query = select(Device).join(Site).where(Device.id == UUID(device_id), Site.organization_id == actor.organization_id)
    
    res = await db.execute(query)
    device = res.scalars().first()
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")
    
    device.voucher_template = template.model_dump()
    await db.commit()

    return {"status": "saved", "template": template}

@router.get("/{device_id}/voucher-template", response_model=VoucherTemplate)
async def get_voucher_template(device_id: str, db: AsyncSession = Depends(get_db), actor = Depends(get_authorized_actor)):
    if isinstance(actor, User) and actor.role == UserRole.SUPER_ADMIN:
        query = select(Device).where(Device.id == UUID(device_id))
    elif isinstance(actor, APIKey) and not actor.organization_id:
        query = select(Device).where(Device.id == UUID(device_id))
    else:
        query = select(Device).join(Site).where(Device.id == UUID(device_id), Site.organization_id == actor.organization_id)
    
    res = await db.execute(query)
    device = res.scalars().first()
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")
        
    if device.voucher_template:
        return VoucherTemplate(**device.voucher_template)
        
    # Return default if not set
    return VoucherTemplate()


async def _portal_device(device_id: str, db: AsyncSession, actor):
    if isinstance(actor, User) and actor.role == UserRole.SUPER_ADMIN:
        query = select(Device).where(Device.id == UUID(device_id))
    elif isinstance(actor, APIKey) and not actor.organization_id:
        query = select(Device).where(Device.id == UUID(device_id))
    else:
        query = select(Device).join(Site).where(Device.id == UUID(device_id), Site.organization_id == actor.organization_id)
    device = (await db.execute(query)).scalars().first()
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")
    return device


def _portal_api(device):
    decrypt_device_secrets(device)
    port = _portal_api_port(device)
    return get_api_pool(device.ip_address, device.ssh_username or "admin", device.ssh_password or "admin", port)


def _portal_api_port(device):
    port = int(getattr(device, "ssh_port", 8728) or 8728)
    return 8728 if port == 22 else port


def _read_router_files(device, name):
    """Return matching files; RouterOS 7 reports no matches as `!empty`."""
    port = _portal_api_port(device)
    connection = _portal_api(device)
    try:
        files = connection.get_api().get_resource("/file")
        try:
            return files.get(name=name)
        except routeros_api.exceptions.RouterOsApiParsingError as exc:
            if "!empty" not in str(exc):
                raise
            _evict_pool(device.ip_address, port)
            return []
    finally:
        connection.disconnect()


def _active_hotspot_directory(device):
    """Read the enabled hotspot's configured, case-sensitive HTML directory."""
    connection = _portal_api(device)
    try:
        api = connection.get_api()
        servers = api.get_resource("/ip/hotspot").get()
        profiles = api.get_resource("/ip/hotspot/profile").get()
        active = next((row for row in servers if not row.get("disabled", False)), None)
        if not active and servers:
            active = servers[0]
        profile_name = active.get("profile") if active else None
        profile = next((row for row in profiles if row.get("name") == profile_name), None)
        directory = str((profile or {}).get("html-directory") or "hotspot").strip("/")
        if not directory or ".." in directory or not re.fullmatch(r"[A-Za-z0-9._/-]+", directory):
            raise HTTPException(status_code=409, detail="The router hotspot HTML directory is not safe to modify")
        return directory
    finally:
        connection.disconnect()


def _read_router_file_content(device, name, rows=None):
    """Read text through the API, with SFTP fallback for RouterOS variants.

    Some RouterOS 7 builds return file metadata from `/file print` but omit
    `contents`. SFTP exposes the same active file without changing the router.
    """
    rows = _read_router_files(device, name) if rows is None else rows
    if not rows:
        return None
    contents = rows[0].get("contents")
    if contents:
        return contents

    decrypt_device_secrets(device)
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    try:
        ssh.connect(
            device.ip_address,
            port=22,
            username=device.ssh_username or "admin",
            password=device.ssh_password or "admin",
            timeout=10,
            banner_timeout=10,
            auth_timeout=10,
            look_for_keys=False,
            allow_agent=False,
        )
        sftp = ssh.open_sftp()
        try:
            with sftp.open(name, "rb") as handle:
                return handle.read().decode("utf-8")
        finally:
            sftp.close()
    except (OSError, UnicodeError, paramiko.SSHException) as exc:
        logger.warning("Could not read RouterOS portal file %s over SFTP: %s", name, exc)
        return None
    finally:
        ssh.close()


def _write_router_file(device, name, contents):
    """Write a RouterOS file, accepting RouterOS 7's successful `!empty` reply.

    Older routeros_api releases cannot parse the `!empty` sentence returned by
    newer RouterOS versions for successful commands. The command has already
    completed when that reply arrives. Evict the now-desynchronised connection
    so the next operation starts with a clean protocol stream.
    """
    port = _portal_api_port(device)
    rows = _read_router_files(device, name)
    connection = _portal_api(device)
    try:
        files = connection.get_api().get_resource("/file")
        try:
            if rows:
                files.set(id=rows[0]["id"], contents=contents)
            else:
                files.add(name=name, contents=contents)
        except routeros_api.exceptions.RouterOsApiParsingError as exc:
            if "!empty" not in str(exc):
                raise
            logger.info("RouterOS accepted file write for %s with an !empty response", name)
            _evict_pool(device.ip_address, port)
    finally:
        connection.disconnect()


@router.get("/{device_id}/portal-config")
async def get_portal_config(device_id: str, db: AsyncSession = Depends(get_db), actor=Depends(get_authorized_actor)):
    device = await _portal_device(device_id, db, actor)
    mode = (device.voucher_template or {}).get("portal_mode", "netguard")
    from app.services.provisioning.sections import custom_portal_button
    return {"mode": mode, "button_html": custom_portal_button(str(device.id))}


@router.post("/{device_id}/portal-mode")
async def set_portal_mode(device_id: str, body: PortalModeUpdate, db: AsyncSession = Depends(get_db), actor=Depends(get_authorized_actor)):
    if body.mode not in {"netguard", "custom"}:
        raise HTTPException(status_code=400, detail="Mode must be netguard or custom")
    device = await _portal_device(device_id, db, actor)
    settings = dict(device.voucher_template or {})
    settings["portal_mode"] = body.mode
    device.voucher_template = settings
    await db.commit()
    return {"status": "saved", "mode": body.mode}


@router.post("/{device_id}/portal/install-custom")
async def install_custom_portal_support(device_id: str, db: AsyncSession = Depends(get_db), actor=Depends(get_authorized_actor)):
    device = await _portal_device(device_id, db, actor)
    directory = _active_hotspot_directory(device)
    login_name = f"{directory}/login.html"
    backup_name = f"{directory}/login.netguard-backup.html"
    helper_name = f"{directory}/netguard-login.html"
    login_rows = _read_router_files(device, login_name)
    if not login_rows:
        raise HTTPException(status_code=409, detail=f"{login_name} was not found on the router")
    original = _read_router_file_content(device, login_name, login_rows)
    if not original:
        raise HTTPException(status_code=409, detail="Router did not return the custom portal contents; no changes were made")
    if not _read_router_files(device, backup_name):
        _write_router_file(device, backup_name, original)
    from app.services.provisioning.sections import custom_portal_button, render_autologin_html
    marker = "<!-- NETGUARD-BUY-START -->"
    updated = original
    if marker not in original:
        button = custom_portal_button(str(device.id))
        pos = original.lower().rfind("</body>")
        updated = original[:pos] + button + original[pos:] if pos >= 0 else original + button
        _write_router_file(device, login_name, updated)
    _write_router_file(device, helper_name, render_autologin_html().replace("\\$", "$"))
    settings = dict(device.voucher_template or {})
    settings["portal_mode"] = "custom"
    device.voucher_template = settings
    await db.commit()
    return {"status": "installed", "mode": "custom", "directory": directory, "backup": backup_name}


@router.post("/{device_id}/portal/restore")
async def restore_custom_portal(device_id: str, db: AsyncSession = Depends(get_db), actor=Depends(get_authorized_actor)):
    device = await _portal_device(device_id, db, actor)
    directory = _active_hotspot_directory(device)
    login_name = f"{directory}/login.html"
    backup_name = f"{directory}/login.netguard-backup.html"
    backups = _read_router_files(device, backup_name)
    backup_contents = _read_router_file_content(device, backup_name, backups)
    if not backup_contents:
        raise HTTPException(status_code=404, detail="No NetGuard portal backup exists on this router")
    _write_router_file(device, login_name, backup_contents)
    return {"status": "restored", "mode": (device.voucher_template or {}).get("portal_mode", "custom"), "directory": directory}

@router.post("/{device_id}/users/batch", status_code=202)
async def batch_generate_users(device_id: str, batch: BatchUserCreate, db: AsyncSession = Depends(get_db), actor = Depends(get_authorized_actor)):

    if isinstance(actor, User) and actor.role == UserRole.SUPER_ADMIN:
        query = select(Device).where(Device.id == UUID(device_id))
    elif isinstance(actor, APIKey) and not actor.organization_id:
        query = select(Device).where(Device.id == UUID(device_id))
    else:
        query = select(Device).join(Site).where(Device.id == UUID(device_id), Site.organization_id == actor.organization_id)

    res = await db.execute(query)
    device = res.scalars().first()
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")

    # Actual voucher generation now happens out-of-band in the worker
    # (agents/voucher_job_worker.py, Task 3): create the batch row up front
    # so it is visible in history even if the enqueue below fails or the
    # operator's browser drops the request, then hand off the work.
    batch_comment = f"Batch-{batch.prefix or 'auto'} | {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"

    try:
        # Get organization_id from device via site
        site_res = await db.execute(select(Site).where(Site.id == device.site_id))
        site = site_res.scalars().first()
        org_id = site.organization_id if site else None
        if not org_id:
            raise ValueError(f"No organization found for device {device_id}")

        voucher_batch = VoucherBatch(
            device_id=device.id,
            organization_id=org_id,
            batch_name=batch_comment,
            prefix=batch.prefix or 'auto',
            profile=batch.profile or 'default',
            time_limit=batch.time_limit,
            data_limit=batch.data_limit,
            count=batch.qty,
            vouchers=[],
            status="queued",
            created_at=datetime.utcnow()
        )
        db.add(voucher_batch)
        await db.commit()
    except Exception as e:
        logger.error(f"Failed to create voucher batch record for device {device_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to create voucher batch: {str(e)}")

    job = {
        "batch_id": str(voucher_batch.id),
        "device_id": device_id,
        "qty": batch.qty,
        "prefix": batch.prefix or 'auto',
        "profile": batch.profile or 'default',
        "time_limit": batch.time_limit,
        "data_limit": batch.data_limit,
        "comment": batch_comment,
        # Naming-shape flags: taken straight from the validated request model
        # so BatchUserCreate's own defaults apply. Do not re-default these
        # here -- a second set of defaults drifting from the model's is how
        # this bug happened the first time.
        "length": batch.length,
        "random_mode": batch.random_mode,
        "format": batch.format,
    }

    if not voucher_jobs.enqueue(job):
        # The row is already committed, so this is the recoverable state:
        # the operator sees a "failed" batch instead of a 500 that implies
        # nothing happened.
        voucher_batch.status = "failed"
        await db.commit()
        return {
            "job_id": str(voucher_batch.id),
            "status": "failed",
            "count": batch.qty,
            "detail": "Voucher batch was recorded but could not be queued for generation. Retry later.",
        }

    logger.info(f"Enqueued voucher batch {voucher_batch.id} for device {device_id}: qty={batch.qty}")
    return {"job_id": str(voucher_batch.id), "status": "queued", "count": batch.qty}

@router.get("/{device_id}/batches")
async def get_voucher_batches(
    device_id: str,
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
    actor = Depends(get_authorized_actor)
):
    """Fetch persisted voucher batch history from the database."""
    if isinstance(actor, User) and actor.role == UserRole.SUPER_ADMIN:
        query = select(Device).where(Device.id == UUID(device_id))
    elif isinstance(actor, APIKey) and not actor.organization_id:
        query = select(Device).where(Device.id == UUID(device_id))
    else:
        query = select(Device).join(Site).where(Device.id == UUID(device_id), Site.organization_id == actor.organization_id)

    res = await db.execute(query)
    device = res.scalars().first()
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")

    try:
        stmt = select(VoucherBatch).where(
            VoucherBatch.device_id == device.id
        ).order_by(VoucherBatch.created_at.desc()).limit(limit).offset(offset)
        res = await db.execute(stmt)
        batches = res.scalars().all()

        return [
            {
                "id": str(b.id),
                "name": b.batch_name,
                "displayName": b.prefix,
                "count": b.count,
                "profile": b.profile,
                "timeLimit": b.time_limit or '',
                "date": b.created_at.strftime('%Y-%m-%d %H:%M') if b.created_at else None,
                "status": b.status,  # null for legacy rows created before job tracking existed
                "vouchers": b.vouchers,
                "data": b.vouchers,  # For backwards compat with frontend handleReprint
            }
            for b in batches
        ]
    except Exception as e:
        logger.error(f"Get Batches Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


class VoucherJobProgress(BaseModel):
    vouchers: List[dict] = []
    status: str


@router.get("/jobs/{job_id}")
async def get_voucher_job(job_id: str, db: AsyncSession = Depends(get_db), actor = Depends(get_authorized_actor)):
    """Poll a background voucher-generation job's progress.

    Keyed by job_id (== VoucherBatch.id) alone -- there is no device_id in
    this path, unlike the other hotspot endpoints, since the operator's
    browser only knows the job_id returned by the batch-create call. Org
    scoping is therefore done directly against VoucherBatch.organization_id
    (set at creation time in batch_generate_users) rather than via a
    Device/Site join.
    """
    try:
        job_uuid = UUID(job_id)
    except ValueError:
        # A malformed id (bad localStorage value, hand-edited URL, etc) can
        # never match a row -- 404 like any other "not found" job, not a 500.
        # This also means a malformed *stored* job id takes the frontend's
        # immediate-clear 404 path on the very first poll, rather than the
        # slower transient-failure path a 500 would trigger.
        raise HTTPException(status_code=404, detail="Job not found")

    if isinstance(actor, User) and actor.role == UserRole.SUPER_ADMIN:
        query = select(VoucherBatch).where(VoucherBatch.id == job_uuid)
    elif isinstance(actor, APIKey) and not actor.organization_id:
        query = select(VoucherBatch).where(VoucherBatch.id == job_uuid)
    else:
        query = select(VoucherBatch).where(
            VoucherBatch.id == job_uuid, VoucherBatch.organization_id == actor.organization_id
        )

    res = await db.execute(query)
    voucher_batch = res.scalars().first()
    if not voucher_batch:
        raise HTTPException(status_code=404, detail="Job not found")

    vouchers = voucher_batch.vouchers or []
    return {
        "job_id": str(voucher_batch.id),
        "status": voucher_batch.status,
        "count": voucher_batch.count,
        "created": len(vouchers),
        "vouchers": vouchers,
    }


@router.post("/jobs/{job_id}/progress")
async def report_voucher_job_progress(
    job_id: str, progress: VoucherJobProgress, db: AsyncSession = Depends(get_db), actor = Depends(get_authorized_actor)
):
    """Consume a progress report from agents/voucher_job_worker.py.

    `progress.vouchers` is only the NEW vouchers since the worker's last
    successful call (see report_progress's docstring in the worker), so this
    must be genuinely append-only: read the current list, extend it, write
    it back. Replacing the column wholesale would discard everything before
    the worker's last ~10-voucher batch.

    This is also a read-modify-write with no lock: if this handler commits
    the append but the worker never sees the 200 (e.g. the ack is lost on a
    docker-internal network partition after the commit -- precisely what the
    worker's 10s client timeout exists to guard against), the worker's local
    pending buffer still believes those vouchers are unsent and resends the
    exact same batch. Since VoucherBatch.vouchers is what the operator
    prints, a naive extend would then store (and let get printed) two slips
    with identical username/password -- a real support/refund problem, not a
    cosmetic one. Router-side voucher usernames are unique by construction
    (the worker generates unique names and the router itself rejects
    collisions), so a username already present in the stored array means
    that exact voucher was already recorded: dedup incoming vouchers by
    "username" against what's already stored (and against each other within
    the same call) before extending, so genuinely new vouchers still
    accumulate but an exact-replay flush is a no-op.
    """
    try:
        job_uuid = UUID(job_id)
    except ValueError:
        # See get_voucher_job's identical guard -- a malformed id is a 404,
        # not a 500.
        raise HTTPException(status_code=404, detail="Job not found")

    if isinstance(actor, User) and actor.role == UserRole.SUPER_ADMIN:
        query = select(VoucherBatch).where(VoucherBatch.id == job_uuid)
    elif isinstance(actor, APIKey) and not actor.organization_id:
        query = select(VoucherBatch).where(VoucherBatch.id == job_uuid)
    else:
        query = select(VoucherBatch).where(
            VoucherBatch.id == job_uuid, VoucherBatch.organization_id == actor.organization_id
        )

    res = await db.execute(query)
    voucher_batch = res.scalars().first()
    if not voucher_batch:
        raise HTTPException(status_code=404, detail="Job not found")

    import copy
    from sqlalchemy.orm.attributes import flag_modified

    current_vouchers = copy.deepcopy(voucher_batch.vouchers) or []
    seen_usernames = {v.get("username") for v in current_vouchers if isinstance(v, dict)}

    new_vouchers = []
    skipped = 0
    for voucher in progress.vouchers:
        username = voucher.get("username") if isinstance(voucher, dict) else None
        if username is not None and username in seen_usernames:
            skipped += 1
            continue
        new_vouchers.append(voucher)
        if username is not None:
            seen_usernames.add(username)

    if skipped:
        logger.info(
            f"Voucher job {job_id} progress: skipped {skipped} duplicate voucher(s) "
            f"already recorded (retry after a lost ack, most likely)"
        )

    current_vouchers.extend(new_vouchers)
    voucher_batch.vouchers = current_vouchers
    flag_modified(voucher_batch, 'vouchers')
    voucher_batch.status = progress.status
    db.add(voucher_batch)
    await db.commit()

    # Only the terminal states mean real vouchers now exist on the router
    # (or, for "failed", whatever was created before the failure) -- an
    # intermediate "running" call must NOT invalidate, or a 500-voucher job
    # forces the monitor agent to refetch the full ~3.6 MB user list every
    # ~10 vouchers, repeatedly blocking its metric loop. See hotspot_cache's
    # own docstring: invalidate() + request_refresh() closes the window
    # between this write and the cache repopulating from ~30 minutes to a
    # second or two.
    if progress.status in ("complete", "failed"):
        hotspot_cache.invalidate(str(voucher_batch.device_id), "users")
        hotspot_cache.request_refresh(str(voucher_batch.device_id))

    return {
        "job_id": str(voucher_batch.id),
        "status": voucher_batch.status,
        "created": len(current_vouchers),
    }


@router.get("/{device_id}/users/search")
async def search_hotspot_user(
    device_id: str,
    name: str = Query(..., description="Username or partial name to search for"),
    db: AsyncSession = Depends(get_db),
    actor = Depends(get_authorized_actor)
):
    """Search for a specific voucher by name on the router, bypassing pagination limits."""
    if isinstance(actor, User) and actor.role == UserRole.SUPER_ADMIN:
        query = select(Device).where(Device.id == UUID(device_id))
    elif isinstance(actor, APIKey) and not actor.organization_id:
        query = select(Device).where(Device.id == UUID(device_id))
    else:
        query = select(Device).join(Site).where(Device.id == UUID(device_id), Site.organization_id == actor.organization_id)

    res = await db.execute(query)
    device = res.scalars().first()
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")

    decrypt_device_secrets(device)

    try:
        port = getattr(device, 'ssh_port', 8728) or 8728
        connection = get_api_pool(device.ip_address, device.ssh_username or 'admin', device.ssh_password or 'admin', int(port))
        api = connection.get_api()

        resource = api.get_resource('/ip/hotspot/user')
        # Try exact match first, then partial
        users = resource.get(name=name)
        if not users:
            # Fallback: get all and filter client-side
            all_users = resource.get()
            name_lower = name.lower()
            users = [u for u in all_users if name_lower in (u.get('name') or '').lower()]

        connection.disconnect()

        if not users:
            raise HTTPException(status_code=404, detail="Voucher not found")

        return [
            HotspotUser(
                name=u.get('name'),
                password=u.get('password'),
                profile=u.get('profile'),
                uptime=u.get('uptime'),
                bytes_in=int(u.get('bytes-in', 0)),
                bytes_out=int(u.get('bytes-out', 0)),
                limit_uptime=u.get('limit-uptime'),
                limit_bytes_total=int(u.get('limit-bytes-total')) if u.get('limit-bytes-total') else None,
                comment=u.get('comment')
            )
            for u in users
        ]
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Search User Error: {e}")
        error_msg = str(e)
        if "Authentication failed" in error_msg:
            raise HTTPException(status_code=401, detail="Router Authentication Failed.")
        if "timed out" in error_msg or "time out" in error_msg:
            raise HTTPException(status_code=504, detail="Router Connection Timed Out.")
        raise HTTPException(status_code=500, detail=f"Router Error: {error_msg}")

@router.delete("/{device_id}/users/bulk")
async def bulk_delete_users(
    device_id: str, 
    comment: Optional[str] = None, 
    expired: bool = False, 
    unused: bool = False,
    db: AsyncSession = Depends(get_db), 
    actor = Depends(get_authorized_actor)
):
    if isinstance(actor, User) and actor.role == UserRole.SUPER_ADMIN:
        query = select(Device).where(Device.id == UUID(device_id))
    elif isinstance(actor, APIKey) and not actor.organization_id:
        query = select(Device).where(Device.id == UUID(device_id))
    else:
        query = select(Device).join(Site).where(Device.id == UUID(device_id), Site.organization_id == actor.organization_id)
        
    res = await db.execute(query)
    device = res.scalars().first()
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")
    
    decrypt_device_secrets(device)
    
    try:
        port = getattr(device, 'ssh_port', 8728) or 8728
        connection = get_api_pool(device.ip_address, device.ssh_username or 'admin', device.ssh_password or 'admin', int(port))
        api = connection.get_api()
        resource = api.get_resource('/ip/hotspot/user')
        
        users = resource.get()
        to_delete = []
        
        def safe_int(v):
            try:
                return int(v) if v else 0
            except ValueError:
                return 0

        for u in users:
            should_delete = False
            if comment and u.get('comment') == comment:
                should_delete = True
            
            if expired:
                uptime_str = u.get('uptime', '0s')
                limit_uptime_str = u.get('limit-uptime')
                
                uptime_sec = parse_routeros_time(uptime_str)
                limit_uptime_sec = parse_routeros_time(limit_uptime_str)
                
                # Mikrotik returns bytes as strings
                bytes_out = safe_int(u.get('bytes-out'))
                bytes_in = safe_int(u.get('bytes-in'))
                total_bytes = bytes_out + bytes_in
                limit_bytes = safe_int(u.get('limit-bytes-total'))
                
                # Robust comparison for "expired":
                # 1. If reached uptime limit
                # 2. If reached data limit
                if limit_uptime_sec > 0 and uptime_sec >= limit_uptime_sec:
                    should_delete = True
                if limit_bytes > 0 and total_bytes >= limit_bytes:
                    should_delete = True
            
            if unused:
                # Delete never used vouchers (uptime is 0s, bytes in/out 0)
                uptime_str = u.get('uptime', '0s')
                uptime_sec = parse_routeros_time(uptime_str)
                bytes_out = safe_int(u.get('bytes-out'))
                bytes_in = safe_int(u.get('bytes-in'))
                
                if uptime_sec == 0 and bytes_out == 0 and bytes_in == 0:
                    should_delete = True

            
            if should_delete:
                to_delete.append(u.get('.id') or u.get('id'))
        
        deleted_count = 0
        failed_count = 0
        errors = []

        # Function to (re)initialize connection and get resource
        def get_resource():
            # Evict stale pool and force fresh connection on protocol desync
            nonlocal connection, api, resource
            _evict_pool(device.ip_address, port)

            # Re-establish
            connection = get_api_pool(device.ip_address, device.ssh_username or 'admin', device.ssh_password or 'admin', int(port))
            api = connection.get_api()
            # Use binary resource for more raw control
            resource = api.get_binary_resource('/ip/hotspot/user')
            return resource

        # Initialize
        resource = get_resource()

        for uid in to_delete:
            if not uid:
                continue
                
            try:
                # Use call('remove') directly on binary resource for more stability
                resource.call('remove', {'.id': uid})
                deleted_count += 1
            except Exception as del_err:
                err_msg = str(del_err)
                logger.error(f"Failed to delete voucher {uid}: {err_msg}")
                
                # If we hit protocol desync or malformed sentence, stay calm and reconnect
                if "Malformed sentence" in err_msg or "!empty" in err_msg or "desync" in err_msg.lower():
                    logger.warning(f"Protocol desync detected during deletion of {uid}. Resetting connection...")
                    try:
                        resource = get_resource()
                        failed_count += 1 # Count this one as failed for now
                    except Exception as conn_err:
                        logger.error(f"Failed to reconnect after protocol error: {conn_err}")
                        break 
                else:
                    failed_count += 1
                    errors.append(f"{uid}: {err_msg}")
            
            # Throttling
            if deleted_count % 10 == 0:
                time.sleep(0.02)
            
        if connection:
            connection.disconnect()

        if failed_count > 0:
            logger.warning(f"Bulk delete partial completion. Deleted: {deleted_count}, Failed: {failed_count}. Errors: {errors[:5]}")

        hotspot_cache.invalidate(device_id, "users")
        hotspot_cache.request_refresh(device_id)
        return {"status": "success", "count": deleted_count, "failed": failed_count}
    except Exception as e:
        logger.error(f"Bulk Delete Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/{device_id}/logs")
async def get_hotspot_logs(device_id: str, db: AsyncSession = Depends(get_db), actor = Depends(get_authorized_actor)):
    if isinstance(actor, User) and actor.role == UserRole.SUPER_ADMIN:
        query = select(Device).where(Device.id == UUID(device_id))
    elif isinstance(actor, APIKey) and not actor.organization_id:
        query = select(Device).where(Device.id == UUID(device_id))
    else:
        query = select(Device).join(Site).where(Device.id == UUID(device_id), Site.organization_id == actor.organization_id)

    res = await db.execute(query)
    device = res.scalars().first()
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")

    # THE RULE: this read path never calls the router, not even on a cache
    # miss. A cold cache is a normal state, reported as an empty list with
    # HTTP 200 — never a router fallthrough, never a 500. Note the dataset
    # name is "log" (singular) — that is what the poller agent writes.
    rows, fetched_at = hotspot_cache.read_dataset(device_id, "log")

    # Guard the type before indexing/iterating: a corrupted cache value could
    # store rows as a dict/int/string instead of a list.
    if not isinstance(rows, list):
        logger.error(f"Hotspot logs cache rows not a list for device={device_id} dataset=log")
        return []

    try:
        # Filter for logs containing 'hotspot' topic
        hotspot_logs = [l for l in rows if 'hotspot' in l.get('topics', '').lower()]

        # Return last 100 logs, reversed (newest first)
        results = []
        for l in reversed(hotspot_logs[-100:]):
            # Extract time and make it clear
            # RouterOS usually provides 'time' as HH:MM:SS or MMM/DD HH:MM:SS
            raw_time = l.get('time', 'unknown')

            # Identify user if possible from message
            msg = l.get('message', '')
            user_info = "system"
            if '(' in msg and ')' in msg:
                # Often logs look like: user muhammad (10.5.5.10): logged in
                match = re.search(r'user\s+([^\s\(]+)', msg)
                if match:
                    user_info = match.group(1)

            results.append({
                "time": raw_time,
                "user_info": user_info,
                "message": msg
            })
    except (TypeError, ValueError, AttributeError) as e:
        logger.error(f"Hotspot logs cache row unparseable for device={device_id} dataset=log: {e}")
        return []

    return results

@router.get("/{device_id}/reports")
async def get_hotspot_reports(
    device_id: str,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    period: Optional[str] = None,
    purchase_type: str = "all",
    background_tasks: BackgroundTasks = None,
    db: AsyncSession = Depends(get_db),
    actor = Depends(get_authorized_actor)
):
    if isinstance(actor, User) and actor.role == UserRole.SUPER_ADMIN:
        query = select(Device).where(Device.id == UUID(device_id))
    elif isinstance(actor, APIKey) and not actor.organization_id:
        query = select(Device).where(Device.id == UUID(device_id))
    else:
        query = select(Device).join(Site).where(Device.id == UUID(device_id), Site.organization_id == actor.organization_id)

    res = await db.execute(query)
    device = res.scalars().first()
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")

    decrypt_device_secrets(device)

    # Try cache first (cache key includes filters)
    if purchase_type not in {"all", "online", "in_person"}:
        raise HTTPException(status_code=400, detail="Invalid purchase type")
    cache_params = f"{period or ''}:{start_date or ''}:{end_date or ''}:{purchase_type}"
    key = cache_key(device_id, f"reports:{cache_params}")
    cached = _redis_get(key)
    if cached:
        try:
            return json.loads(cached)
        except Exception as e:
            logger.warning(f"Failed to deserialize cached reports: {e}")

    try:
        # 1. Trigger sales sync in background (non-blocking)
        if background_tasks:
            background_tasks.add_task(sync_hotspot_sales, device, db)
        # If background_tasks is not available, skip sync to avoid blocking

        # 2. Query the persistent VoucherSale table
        from sqlalchemy import and_, func

        stmt = select(VoucherSale).where(VoucherSale.device_id == device.id)
        if purchase_type == "online":
            stmt = stmt.where(VoucherSale.comment.ilike("Modem Pay %"))
        elif purchase_type == "in_person":
            stmt = stmt.where(
                or_(VoucherSale.comment.is_(None), ~VoucherSale.comment.ilike("Modem Pay %"))
            )

        # Handle period presets
        from datetime import timedelta
        now = datetime.utcnow()
        if period == 'day':
            start_date = now.strftime('%Y-%m-%d')
        elif period == 'week':
            start_date = (now - timedelta(days=7)).strftime('%Y-%m-%d')
        elif period == 'month':
            start_date = now.replace(day=1).strftime('%Y-%m-%d')

        if start_date:
            try:
                start_dt = datetime.strptime(start_date, '%Y-%m-%d')
                stmt = stmt.where(VoucherSale.created_at >= start_dt)
            except: pass

        if end_date:
            try:
                # End date inclusive (until end of day)
                end_dt = datetime.strptime(end_date, '%Y-%m-%d').replace(hour=23, minute=59, second=59)
                stmt = stmt.where(VoucherSale.created_at <= end_dt)
            except: pass

        # Sort by most recent
        stmt = stmt.order_by(VoucherSale.created_at.desc())

        res = await db.execute(stmt)
        all_sales = res.scalars().all()

        report_data = []
        total_revenue = {} # Per currency
        total_sold = 0

        for sale in all_sales:
            total_sold += 1
            curr = sale.currency or "TZS"
            total_revenue[curr] = total_revenue.get(curr, 0) + sale.price

            report_data.append({
                "username": sale.username,
                "profile": sale.profile,
                "created_at": sale.created_at.strftime('%Y-%m-%d %H:%M:%S'),
                "uptime": sale.uptime,
                "bytes": sale.bytes_total,
                "price": sale.price,
                "currency": sale.currency,
                "comment": sale.comment,
                "purchase_type": "online" if (sale.comment or "").startswith("Modem Pay ") else "in_person"
            })

        # Aggregation by period (Mikhmon Style)
        daily_stats = {}
        for sale in all_sales:
            day_str = sale.created_at.strftime('%Y-%m-%d')
            if day_str not in daily_stats:
                daily_stats[day_str] = {"count": 0, "revenue": {}}

            daily_stats[day_str]["count"] += 1
            c = sale.currency or "TZS"
            daily_stats[day_str]["revenue"][c] = daily_stats[day_str]["revenue"].get(c, 0) + sale.price

        profile_stats = {}
        for sale in all_sales:
            p = sale.profile
            if p not in profile_stats:
                profile_stats[p] = {"count": 0, "revenue": {}}
            profile_stats[p]["count"] += 1
            c = sale.currency or "TZS"
            profile_stats[p]["revenue"][c] = profile_stats[p]["revenue"].get(c, 0) + sale.price

        result = {
            "status": "success",
            "period": period or f"{start_date} to {end_date}",
            "purchase_type": purchase_type,
            "total_sold": total_sold,
            "total_revenue": total_revenue,
            "data": report_data,
            "daily_stats": sorted([{"date": k, **v} for k, v in daily_stats.items()], key=lambda x: x['date'], reverse=True),
            "profile_stats": sorted([{"profile": k, **v} for k, v in profile_stats.items()], key=lambda x: x['count'], reverse=True)
        }

        _redis_setex(key, 60, json.dumps(result))
        return result
    except Exception as e:
        logger.error(f"Hotspot Report Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/{device_id}/users/export")
async def export_hotspot_users(
    device_id: str, 
    db: AsyncSession = Depends(get_db), 
    actor = Depends(get_authorized_actor)
):
    if isinstance(actor, User) and actor.role == UserRole.SUPER_ADMIN:
        query = select(Device).where(Device.id == UUID(device_id))
    elif isinstance(actor, APIKey) and not actor.organization_id:
        query = select(Device).where(Device.id == UUID(device_id))
    else:
        query = select(Device).join(Site).where(Device.id == UUID(device_id), Site.organization_id == actor.organization_id)
        
    res = await db.execute(query)
    device = res.scalars().first()
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")
    
    decrypt_device_secrets(device)
    
    try:
        port = getattr(device, 'ssh_port', 8728) or 8728
        connection = get_api_pool(device.ip_address, device.ssh_username or 'admin', device.ssh_password or 'admin', int(port))
        api = connection.get_api()
        users = api.get_resource('/ip/hotspot/user').get()
        connection.disconnect()
        
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(['Username', 'Password', 'Profile', 'Uptime', 'Bytes In', 'Bytes Out', 'Limit Uptime', 'Limit Bytes', 'Comment'])
        
        for u in users:
            writer.writerow([
                u.get('name'),
                u.get('password'),
                u.get('profile'),
                u.get('uptime'),
                u.get('bytes-in'),
                u.get('bytes-out'),
                u.get('limit-uptime'),
                u.get('limit-bytes-total'),
                u.get('comment')
            ])
            
        output.seek(0)
        return StreamingResponse(
            iter([output.getvalue()]),
            media_type="text/csv",
            headers={"Content-Disposition": f"attachment; filename=hotspot_users_{device_id}.csv"}
        )
    except Exception as e:
        logger.error(f"Export Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/record-sale")
async def record_hotspot_sale(
    sale: SaleRecord,
    db: AsyncSession = Depends(get_db)
):
    """
    Endpoint for MikroTik to report a sale in real-time.
    Called via /tool fetch or similar on login.
    """
    # Verify device exists
    stmt = select(Device).where(Device.id == sale.device_id)
    res = await db.execute(stmt)
    device = res.scalars().first()
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")

    # Check for existing record
    stmt = select(VoucherSale).where(
        VoucherSale.device_id == sale.device_id,
        VoucherSale.username == sale.username
    )
    res = await db.execute(stmt)
    existing = res.scalars().first()
    
    # Determine price and currency from profile pricing map or regex heuristic
    hs_settings = device.voucher_template or {}
    profile_pricing = hs_settings.get('profile_pricing', {})
    default_currency = hs_settings.get('default_currency', 'GMD')

    price = 0
    currency = default_currency

    profile_pricing_lower = {k.lower(): v for k, v in profile_pricing.items()}
    profile_key = (sale.profile or '').lower()
    if profile_key in profile_pricing_lower:
        entry = profile_pricing_lower[profile_key]
        price = entry['price']
        currency = entry['currency']
        logger.info(f"Record Sale: Device={device.name}, Profile='{sale.profile}', price={price} {currency} (from map)")
    else:
        match = re.search(r'(\d+)', sale.profile or '')
        if match:
            price = float(match.group(1))
            logger.info(f"Record Sale: Device={device.name}, Profile='{sale.profile}', price={price} (regex heuristic)")
        else:
            logger.warning(f"Record Sale: Price resolution failed for profile '{sale.profile}' on device {device.name}.")

    if existing:
        changed = False
        if existing.price == 0 and price > 0:
            existing.price = int(price)
            existing.currency = currency
            changed = True
        if not existing.profile and sale.profile:
            existing.profile = sale.profile
            changed = True
        if changed:
            await db.commit()
            logger.info(f"Record Sale: Backfilled existing record (username={sale.username}, price={price}, profile={sale.profile})")
        return {"status": "already_recorded"}

    sale_date = datetime.utcnow()

    new_sale = VoucherSale(
        device_id=sale.device_id,
        site_id=device.site_id,
        username=sale.username,
        profile=sale.profile,
        comment=sale.comment,
        uptime=sale.uptime,
        uptime_sec=parse_routeros_time(sale.uptime),
        bytes_total=sale.bytes,
        price=int(price),
        currency=currency,
        created_at=sale_date
    )

    db.add(new_sale)
    await db.commit()

    return {"status": "recorded", "id": str(new_sale.id)}
