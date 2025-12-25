from pydantic import BaseModel, UUID4
from typing import Optional, List
from datetime import datetime

# Site Schemas
class SiteBase(BaseModel):
    name: str
    location: Optional[str] = None
    auto_fix_enabled: bool = False

class SiteCreate(SiteBase):
    organization_id: Optional[UUID4] = None

class SiteResponse(SiteBase):
    id: UUID4
    organization_id: UUID4
    created_at: datetime
    
    class Config:
        from_attributes = True

# Device Schemas
class DeviceBase(BaseModel):
    name: str
    ip_address: str
    device_type: Optional[str] = "router"
    is_active: bool = True
    snmp_community: Optional[str] = "public"
    ssh_username: Optional[str] = None
    ssh_password: Optional[str] = None
    ssh_port: int = 22

class DeviceCreate(DeviceBase):
    site_id: UUID4

class DeviceResponse(DeviceBase):
    id: UUID4
    site_id: UUID4
    created_at: datetime
    
    class Config:
        from_attributes = True
