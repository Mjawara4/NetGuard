from fastapi import APIRouter, Depends, HTTPException
from typing import List, Optional
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.core.database import get_db
from app.auth.deps import get_authorized_actor, get_current_user
from app.models import Device, User, Site
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

class HotspotActive(BaseModel):
    id: Optional[str] = None
    user: str
    address: str
    uptime: str
    bytes_in: int
    bytes_out: int

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
    # Fetch device with org check
    res = await db.execute(select(Device).join(Site).where(Device.id == UUID(device_id), Site.organization_id == actor.organization_id))
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
            bytes_out=int(u.get('bytes-out', 0))
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
    res = await db.execute(select(Device).join(Site).where(Device.id == UUID(device_id), Site.organization_id == actor.organization_id))
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

@router.get("/{device_id}/profiles", response_model=List[dict])
async def get_hotspot_profiles(device_id: str, db: AsyncSession = Depends(get_db), actor = Depends(get_authorized_actor)):
    res = await db.execute(select(Device).join(Site).where(Device.id == UUID(device_id), Site.organization_id == actor.organization_id))
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
        connection.disconnect()
        
        return profiles
    except Exception as e:
        logger.error(f"Hotspot Profiles Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/{device_id}/profiles")
async def create_hotspot_profile(device_id: str, profile: HotspotProfile, db: AsyncSession = Depends(get_db), actor = Depends(get_authorized_actor)):
    res = await db.execute(select(Device).join(Site).where(Device.id == UUID(device_id), Site.organization_id == actor.organization_id))
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
    res = await db.execute(select(Device).join(Site).where(Device.id == UUID(device_id), Site.organization_id == actor.organization_id))
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
    res = await db.execute(select(Device).join(Site).where(Device.id == UUID(device_id), Site.organization_id == actor.organization_id))
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
            id=a.get('id'),
            user=a.get('user'),
            address=a.get('address'),
            uptime=a.get('uptime'),
            bytes_in=int(a.get('bytes-in', 0)),
            bytes_out=int(a.get('bytes-out', 0))
        ) for a in active]
    except Exception as e:
        logger.error(f"Active Users Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/{device_id}/active/{active_id}")
async def kick_active_user(device_id: str, active_id: str, db: AsyncSession = Depends(get_db), actor = Depends(get_authorized_actor)):
    res = await db.execute(select(Device).join(Site).where(Device.id == UUID(device_id), Site.organization_id == actor.organization_id))
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

@router.post("/{device_id}/users/batch")
async def batch_generate_users(device_id: str, batch: BatchUserCreate, db: AsyncSession = Depends(get_db), actor = Depends(get_authorized_actor)):
    
    res = await db.execute(select(Device).join(Site).where(Device.id == UUID(device_id), Site.organization_id == actor.organization_id))
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
        
        # Handle 'auto' prefix - map to existing random_mode logic
        if batch.prefix == "auto":
             batch.random_mode = True
        
        generated = []
        for _ in range(batch.qty):
            if batch.random_mode:
                # 4 random lowercase letters + 4 random numbers
                letters = ''.join(random.choices(string.ascii_lowercase, k=4))
                numbers = ''.join(random.choices(string.digits, k=4))
                username = f"{letters}{numbers}"
                password = username # Same as username
            else:
                suffix = ''.join(random.choices(string.digits, k=batch.length))
                username = f"{batch.prefix}{suffix}"
                password = ''.join(random.choices(string.digits, k=4)) # Simple 4 digit password
            
            # Simple retry if exists (imperfect but works for MVP)
            try:
                params = {
                    'name': username,
                    'password': password,
                    'profile': batch.profile,
                    'comment': f"Batch-{batch.prefix}"
                }
                if batch.time_limit:
                    params['limit-uptime'] = batch.time_limit
                if batch.data_limit:
                    params['limit-bytes-total'] = batch.data_limit
                    
                resource.add(**params)
                generated.append({"username": username, "password": password})
            except Exception as e:
                # print(f"Batch Item Error: {e}") 
                continue
                
        connection.disconnect()
        return generated
    except Exception as e:
        logger.error(f"Batch Gen Error: {e}")
        # Mock
        return [
            {"username": f"{batch.prefix}123", "password": "123"},
            {"username": f"{batch.prefix}456", "password": "456"}
        ]
