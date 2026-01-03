from fastapi import APIRouter, Depends, HTTPException, Security
from fastapi.responses import StreamingResponse
import io
import csv
from typing import List, Optional
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.core.database import get_db
from app.auth.deps import get_authorized_actor, get_current_user
from app.models import Device, User, Site, APIKey, UserRole
from app.models.core import decrypt_device_secrets
import routeros_api
from uuid import UUID
from datetime import datetime
import time
import random
import string
import logging

logger = logging.getLogger(__name__)

router = APIRouter()

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

def get_api_pool(ip, username, password, port=8728):
    connection = routeros_api.RouterOsApiPool(
        ip, 
        username=username, 
        password=password,
        port=port,
        plaintext_login=True,
        use_ssl=False
    )
    return connection

@router.get("/{device_id}/users", response_model=List[HotspotUser])
async def get_hotspot_users(device_id: str, db: AsyncSession = Depends(get_db), actor = Depends(get_authorized_actor)):
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
    
    # Decrypt device secrets (required for async SQLAlchemy)
    decrypt_device_secrets(device)
        
    try:
        # Heuristic: If port is 22 (SSH), use 8728 (API) for RouterOS API connections
        db_port = getattr(device, 'ssh_port', 8728) or 8728
        port = 8728 if int(db_port) == 22 else db_port
        
        connection = get_api_pool(device.ip_address, device.ssh_username or 'admin', device.ssh_password or 'admin', int(port))
        api = connection.get_api()
        
        users = api.get_resource('/ip/hotspot/user').get()
        connection.disconnect()
        
        return [HotspotUser(
            name=u.get('name'), 
            password=u.get('password'), 
            profile=u.get('profile'),
            uptime=u.get('uptime'),
            bytes_in=int(u.get('bytes-in', 0)),
            bytes_out=int(u.get('bytes-out', 0)),
            limit_uptime=u.get('limit-uptime'),
            limit_bytes_total=int(u.get('limit-bytes-total')) if u.get('limit-bytes-total') else None,
            comment=u.get('comment')
        ) for u in users]
        
    except Exception as e:
        logger.error(f"Hotspot API Error: {e}")
        error_msg = str(e)
        if "Authentication failed" in error_msg:
             raise HTTPException(status_code=401, detail="Router Authentication Failed. Check username/password.")
        if "timed out" in error_msg or "time out" in error_msg:
             raise HTTPException(status_code=504, detail="Router Connection Timed Out. Check VPN status and IP.")
        raise HTTPException(status_code=500, detail=f"Router Error: {error_msg}")


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
        return {"status": "success"}
    except Exception as e:
        logger.error(f"Delete User Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/{device_id}/profiles", response_model=List[dict])
async def get_hotspot_profiles(device_id: str, db: AsyncSession = Depends(get_db), actor = Depends(get_authorized_actor)):
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
        
        profiles = api.get_resource('/ip/hotspot/user/profile').get()
        active = api.get_resource('/ip/hotspot/active').get()
        
        # Calculate active users per profile
        active_per_profile = {}
        for a in active:
            # Active sessions don't explicitly show profile, we need to match user to profile
            # However, for simplicity and performance, most MikroTik admins name users after profiles or used fixed profiles.
            # A more robust way is to fetch users and join, but let's try a heuristic or just return the base stats first.
            pass

        # Let's just return the profiles for now, but enriched if we can.
        # Enriched Profiles with user counts:
        users = api.get_resource('/ip/hotspot/user').get()
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
        default_currency = settings.get('default_currency', 'TZS')
        
        for p in profiles:
            p_name = p.get('name')
            p['active_users'] = profile_counts.get(p_name, 0)
            
            pricing = profile_pricing.get(p_name, {})
            p['custom_price'] = pricing.get('price', 0)
            p['custom_currency'] = pricing.get('currency', default_currency)

        connection.disconnect()
        return profiles
    except Exception as e:
        logger.error(f"Hotspot Profiles Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

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
        # Update local database instead of MikroTik (RouterOS might not support comments on profiles via API)
        import copy
        hs_settings = copy.deepcopy(device.voucher_template) or {}
        if 'profile_pricing' not in hs_settings:
            hs_settings['profile_pricing'] = {}
            
        # Update specific profile pricing
        hs_settings['profile_pricing'][profile_name] = {
            "price": settings.price,
            "currency": settings.currency
        }
        
        # Also update global default currency if provided
        if settings.currency:
            hs_settings['default_currency'] = settings.currency

        device.voucher_template = hs_settings
        db.add(device)
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
    
    decrypt_device_secrets(device)
         
    try:
        port = getattr(device, 'ssh_port', 8728) or 8728
        connection = get_api_pool(device.ip_address, device.ssh_username or 'admin', device.ssh_password or 'admin', int(port))
        api = connection.get_api()
        
        active_resource = api.get_resource('/ip/hotspot/active')
        user_resource = api.get_resource('/ip/hotspot/user')
        
        active_sessions = active_resource.get()
        total_users = user_resource.get()
        
        total_bytes_in = sum(int(a.get('bytes-in', 0)) for a in active_sessions)
        total_bytes_out = sum(int(a.get('bytes-out', 0)) for a in active_sessions)
        
        # Profile Distribution
        profile_dist = {}
        for u in total_users:
            p = u.get('profile', 'default')
            profile_dist[p] = profile_dist.get(p, 0) + 1
            
        connection.disconnect()
        
        return {
            "active_count": len(active_sessions),
            "total_vouchers": len(total_users),
            "total_data_mb": round((total_bytes_in + total_bytes_out) / 1024 / 1024, 2),
            "profile_distribution": [{"name": k, "value": v} for k, v in profile_dist.items()]
        }
    except Exception as e:
        logger.error(f"Hotspot Summary Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

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
    
    decrypt_device_secrets(device)
         
    try:
        port = getattr(device, 'ssh_port', 8728) or 8728
        connection = get_api_pool(device.ip_address, device.ssh_username or 'admin', device.ssh_password or 'admin', int(port))
        api = connection.get_api()
        
        resource = api.get_resource('/system/resource')
        info = resource.get()[0]
        
        connection.disconnect()
        
        return {
            "cpu_load": info.get('cpu-load'),
            "free_memory": int(info.get('free-memory', 0)) / 1024 / 1024,
            "total_memory": int(info.get('total-memory', 0)) / 1024 / 1024,
            "uptime": info.get('uptime'),
            "version": info.get('version'),
            "board_name": info.get('board-name')
        }
    except Exception as e:
        logger.error(f"Router System Info Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

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
        return {"status": "success"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/{device_id}/active", response_model=List[HotspotActive])
async def get_active_users(device_id: str, db: AsyncSession = Depends(get_db), actor = Depends(get_authorized_actor)):
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
        active = api.get_resource('/ip/hotspot/active').get()
        users = api.get_resource('/ip/hotspot/user').get()
        connection.disconnect()
        
        user_limits = {u.get('name'): u.get('limit-uptime') for u in users if u.get('limit-uptime')}
        
        results = []
        for a in active:
            username = a.get('user')
            uptime_str = a.get('uptime', '0s')
            limit_str = user_limits.get(username)
            
            remaining = "UNLIM"
            if limit_str:
                uptime_sec = parse_routeros_time(uptime_str)
                limit_sec = parse_routeros_time(limit_str)
                rem_sec = max(0, limit_sec - uptime_sec)
                remaining = format_routeros_time(rem_sec)

            results.append(HotspotActive(
                id=a.get('.id') or a.get('id'),
                user=username,
                address=a.get('address'),
                uptime=uptime_str,
                bytes_in=int(a.get('bytes-in', 0)),
                bytes_out=int(a.get('bytes-out', 0)),
                mac_address=a.get('mac-address'),
                remaining_time=remaining
            ))
        return results
    except Exception as e:
        logger.error(f"Active Users Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

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
        return {"status": "success"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))



class VoucherTemplate(BaseModel):
    header_text: Optional[str] = "Wi-Fi Voucher"
    footer_text: Optional[str] = "Thank you for visiting!"
    logo_url: Optional[str] = None
    color_primary: Optional[str] = "#2563EB"
    profile_pricing: Optional[dict] = {}
    default_currency: Optional[str] = "TZS"

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
    
    device.voucher_template = template.dict()
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

@router.post("/{device_id}/users/batch")
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
    
    # Decrypt device secrets (required for async SQLAlchemy)
    decrypt_device_secrets(device)
        
    try:
        port = getattr(device, 'ssh_port', 8728) or 8728
        connection = get_api_pool(device.ip_address, device.ssh_username or 'admin', device.ssh_password or 'admin', int(port))
        api = connection.get_api()
        resource = api.get_resource('/ip/hotspot/user')
        
        generated = []
        max_attempts = batch.qty * 3 # Allow for more collisions
        attempts = 0
        
        logger.info(f"Starting batch generation: qty={batch.qty}, random={batch.random_mode}, format={batch.format}")
        
        while len(generated) < batch.qty and attempts < max_attempts:
            attempts += 1
            if batch.random_mode:
                if batch.format == "numeric":
                    # numeric mode with variable length
                    length = batch.length if batch.length else 8
                    username = ''.join(random.choices(string.digits, k=length))
                    password = username
                else:
                    # alphanumeric mode: split length between letters and numbers
                    # default length 8 if not specified
                    length = batch.length if batch.length else 8
                    num_len = length // 2
                    char_len = length - num_len
                    
                    letters = ''.join(random.choices(string.ascii_lowercase, k=char_len))
                    numbers = ''.join(random.choices(string.digits, k=num_len))
                    username = f"{letters}{numbers}"
                    password = username # Same as username
            else:
                suffix_len = batch.length if batch.length else 4
                suffix = ''.join(random.choices(string.digits, k=suffix_len))
                username = f"{batch.prefix}{suffix}"
                password = ''.join(random.choices(string.digits, k=4)) # Simple 4 digit password
            
            try:
                params = {
                    'name': username,
                    'password': password,
                    'profile': batch.profile or 'default',
                    'comment': f"Batch-{batch.prefix or 'auto'} | {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
                }
                if batch.time_limit:
                    params['limit-uptime'] = batch.time_limit
                if batch.data_limit:
                    params['limit-bytes-total'] = batch.data_limit
                    
                resource.add(**params)
                generated.append({"username": username, "password": password})
            except Exception as e:
                # Likely "user already exists", continue to next attempt
                if "already exists" not in str(e).lower():
                    logger.warning(f"Batch item error (Attempt {attempts}/{max_attempts}): {e}")
                continue
                
        logger.info(f"Batch generation complete: {len(generated)}/{batch.qty} created in {attempts} attempts")
        connection.disconnect()
        return generated
    except Exception as e:
        logger.error(f"Batch Gen Error: {e}", exc_info=True)
        if 'connection' in locals() and connection:
            connection.disconnect()
        raise HTTPException(status_code=500, detail=f"Failed to generate vouchers: {str(e)}")
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
            # Close existing if it exists
            nonlocal connection, api, resource
            if connection:
                try:
                    connection.disconnect()
                except:
                    pass
            
            # Re-establish
            port = getattr(device, 'ssh_port', 8728) or 8728
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
    
    decrypt_device_secrets(device)
         
    try:
        port = getattr(device, 'ssh_port', 8728) or 8728
        connection = get_api_pool(device.ip_address, device.ssh_username or 'admin', device.ssh_password or 'admin', int(port))
        api = connection.get_api()
        
        # Fetch recent logs (last 500 to ensure we find enough hotspot entries)
        log_resource = api.get_resource('/log')
        all_logs = log_resource.get()
        
        connection.disconnect()
        
        # Filter for logs containing 'hotspot' topic
        hotspot_logs = [l for l in all_logs if 'hotspot' in l.get('topics', '').lower()]
        
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
                import re
                match = re.search(r'user\s+([^\s\(]+)', msg)
                if match:
                    user_info = match.group(1)
            
            results.append({
                "time": raw_time,
                "user_info": user_info,
                "message": msg
            })
        return results
    except Exception as e:
        logger.error(f"Router Logs Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/{device_id}/reports")
async def get_hotspot_reports(
    device_id: str, 
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    period: Optional[str] = None,
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
        
        # Fetch all users and profiles to get pricing
        users_resource = api.get_resource('/ip/hotspot/user')
        profiles_resource = api.get_resource('/ip/hotspot/user/profile')
        
        users = users_resource.get()
        profiles = profiles_resource.get()
        connection.disconnect()
        
        # Build price map from local settings
        hs_settings = device.voucher_template or {}
        profile_pricing = hs_settings.get('profile_pricing', {})
        default_currency = hs_settings.get('default_currency', 'TZS')
        
        # Map profiles for fallback heuristics if no local price set
        profiles_map = {p.get('name'): p for p in profiles}
        
        def get_price_for_profile(p_name):
            if p_name in profile_pricing:
                return profile_pricing[p_name]['price'], profile_pricing[p_name]['currency']
            
            # Fallback to name heuristic
            import re
            match = re.search(r'(\d+)$', p_name or '')
            if match:
                return float(match.group(1)), default_currency
            return 0, default_currency

        # Filter for sold vouchers (uptime > 0)
        report_data = []
        total_revenue = {} # Store per currency
        total_sold = 0
        
        # Handle period presets
        from datetime import timedelta
        now = datetime.now()
        if period == 'day':
            start_date = now.strftime('%Y-%m-%d')
            end_date = None
        elif period == 'week':
            start_date = (now - timedelta(days=7)).strftime('%Y-%m-%d')
            end_date = None
        elif period == 'month':
            start_date = now.replace(day=1).strftime('%Y-%m-%d')
            end_date = None

        if start_date or end_date or period:
            logger.info(f"Filtering reports: period={period}, start={start_date}, end={end_date}")

        start_dt = datetime.strptime(start_date, '%Y-%m-%d') if start_date else None
        end_dt = datetime.strptime(end_date, '%Y-%m-%d').replace(hour=23, minute=59, second=59) if end_date else None

        def parse_comment_date(comment):
            if ' | ' in comment:
                try:
                    date_part = comment.split(' | ')[-1]
                    return datetime.strptime(date_part, '%Y-%m-%d %H:%M:%S')
                except: pass
            return None

        for u in users:
            uptime = u.get('uptime', '0s')
            if uptime != '0s':
                comment = u.get('comment', '')
                created_at = parse_comment_date(comment)
                
                # Check date filters
                if start_dt and created_at and created_at < start_dt:
                    continue
                if end_dt and created_at and created_at > end_dt:
                    continue
                
                # Fallback for legacy vouchers (no timestamp)
                if (start_dt or end_dt) and not created_at:
                    # Robust check: If the range includes TODAY, include legacy vouchers as "Recently Used"
                    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
                    today_end = now.replace(hour=23, minute=59, second=59, microsecond=999999)
                    
                    in_range = True
                    if start_dt and today_end < start_dt: in_range = False
                    if end_dt and today_start > end_dt: in_range = False
                    
                    if in_range:
                        pass
                    else:
                        continue

                price, curr = get_price_for_profile(u.get('profile'))
                
                total_revenue[curr] = total_revenue.get(curr, 0) + price
                total_sold += 1
                
                report_data.append({
                    "date": created_at.strftime('%Y-%m-%d %H:%M') if created_at else "Recently Used",
                    "timestamp": created_at.timestamp() if created_at else float('inf'), # Put legacy at top
                    "user": u.get('name'),
                    "profile": u.get('profile'),
                    "price": price,
                    "currency": curr,
                    "comment": comment
                })
        
        # Sort by timestamp descending (newest first)
        # float('inf') for legacy ensures they stay at the top as "Recently Used"
        report_data.sort(key=lambda x: x.get('timestamp', 0), reverse=True)
        
        # Clean up internal timestamp before returning
        for r in report_data:
            r.pop('timestamp', None)
        
        return {
            "summary": {
                "total_revenue": total_revenue, # dictionary of curr: amount
                "total_sold": total_sold,
            },
            "records": report_data
        }
    except Exception as e:
        logger.error(f"Router Reports Error: {e}")
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
