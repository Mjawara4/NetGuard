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
    length: Optional[int] = 4
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
        user = resource.get(name=username)
        if not user:
             connection.disconnect()
             raise HTTPException(status_code=404, detail="User not found")
             
        resource.remove(id=user[0]['.id'])
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
        
        for p in profiles:
            p['active_users'] = profile_counts.get(p.get('name'), 0)

        connection.disconnect()
        return profiles
    except Exception as e:
        logger.error(f"Hotspot Profiles Error: {e}")
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
        connection.disconnect()
        
        return [HotspotActive(
            id=a.get('.id') or a.get('id'),
            user=a.get('user'),
            address=a.get('address'),
            uptime=a.get('uptime'),
            bytes_in=int(a.get('bytes-in', 0)),
            bytes_out=int(a.get('bytes-out', 0)),
            mac_address=a.get('mac-address')
        ) for a in active]
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
                    # 8 random numbers
                    username = ''.join(random.choices(string.digits, k=8))
                    password = username
                else:
                    # Default: 4 random lowercase letters + 4 random numbers
                    letters = ''.join(random.choices(string.ascii_lowercase, k=4))
                    numbers = ''.join(random.choices(string.digits, k=4))
                    username = f"{letters}{numbers}"
                    password = username # Same as username
            else:
                suffix = ''.join(random.choices(string.digits, k=batch.length))
                username = f"{batch.prefix}{suffix}"
                password = ''.join(random.choices(string.digits, k=4)) # Simple 4 digit password
            
            try:
                params = {
                    'name': username,
                    'password': password,
                    'profile': batch.profile or 'default',
                    'comment': f"Batch-{batch.prefix or 'auto'}"
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
        
        for u in users:
            should_delete = False
            if comment and u.get('comment') == comment:
                should_delete = True
            
            if expired:
                uptime = u.get('uptime', '0s')
                limit_uptime = u.get('limit-uptime')
                bytes_out = int(u.get('bytes-out', 0))
                bytes_in = int(u.get('bytes-in', 0))
                total_bytes = bytes_out + bytes_in
                limit_bytes = int(u.get('limit-bytes-total', 0))
                
                # Simple heuristic for "expired":
                # 1. If reached uptime limit
                # 2. If reached data limit
                if limit_uptime and uptime == limit_uptime:
                    should_delete = True
                if limit_bytes > 0 and total_bytes >= limit_bytes:
                    should_delete = True
            
            if should_delete:
                to_delete.append(u.get('.id') or u.get('id'))
        
        for uid in to_delete:
            resource.remove(id=uid)
            
        connection.disconnect()
        return {"status": "success", "count": len(to_delete)}
    except Exception as e:
        logger.error(f"Bulk Delete Error: {e}")
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
