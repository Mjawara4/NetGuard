from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List
from app.database import get_db
from app.auth.deps import get_current_user, get_authorized_actor
from app.models import Device, Site, User
from app.schemas.inventory import DeviceCreate, DeviceResponse, SiteCreate, SiteResponse

router = APIRouter()

@router.post("/sites", response_model=SiteResponse)
async def create_site(site: SiteCreate, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    # Permission check: Ensure user belongs to an org
    if not current_user.organization_id:
         raise HTTPException(status_code=403, detail="User does not belong to an organization")
         
    site_data = site.dict(exclude={'organization_id'})
    new_site = Site(**site_data, organization_id=current_user.organization_id)
    db.add(new_site)
    await db.commit()
    await db.refresh(new_site)
    return new_site

@router.get("/sites", response_model=List[SiteResponse])
async def get_sites(db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    # Filter by user's org
    if current_user.organization_id:
        result = await db.execute(select(Site).where(Site.organization_id == current_user.organization_id))
    else:
        # Super admin sees all? or none? For now all
        result = await db.execute(select(Site))
    return result.scalars().all()

@router.post("/devices", response_model=DeviceResponse)
async def create_device(device: DeviceCreate, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    # Verify Site belongs to User's Org
    site_res = await db.execute(select(Site).where(Site.id == device.site_id, Site.organization_id == current_user.organization_id))
    if not site_res.scalars().first():
        raise HTTPException(status_code=404, detail="Site not found or access denied")

    new_device = Device(**device.dict())
    db.add(new_device)
    await db.commit()
    await db.refresh(new_device)
    return new_device

@router.get("/devices", response_model=List[DeviceResponse])
async def get_devices(db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    # Filter by user's org via Site
    if current_user.organization_id:
        result = await db.execute(select(Device).join(Site).where(Site.organization_id == current_user.organization_id))
        return result.scalars().all()
    else:
        # Fallback or Super Admin
        result = await db.execute(select(Device))
        return result.scalars().all()

@router.delete("/devices/{device_id}", status_code=204)
async def delete_device(device_id: str, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    from uuid import UUID
    from sqlalchemy import delete
    from app.models import Metric, Alert
    
    # Check existence and ownership
    result = await db.execute(select(Device).join(Site).where(Device.id == UUID(device_id), Site.organization_id == current_user.organization_id))
    device = result.scalars().first()
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")
        
    # Cascade delete (Manual for MVP)
    # Delete metrics
    await db.execute(delete(Metric).where(Metric.device_id == UUID(device_id)))
    # Delete alerts
    await db.execute(delete(Alert).where(Alert.device_id == UUID(device_id)))
    
    # Delete device
    await db.delete(device)
    await db.commit()
    return

@router.put("/devices/{device_id}", response_model=DeviceResponse)
async def update_device(device_id: str, device_update: DeviceCreate, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    from uuid import UUID
    # Verify ownership
    result = await db.execute(select(Device).join(Site).where(Device.id == UUID(device_id), Site.organization_id == current_user.organization_id))
    device = result.scalars().first()
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")
        
    # Update fields
    for key, value in device_update.dict(exclude_unset=True).items():
        setattr(device, key, value)
        
    await db.commit()
    await db.refresh(device)
    return device
