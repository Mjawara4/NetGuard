from pydantic import BaseModel, UUID4, validator, Field
from typing import Optional, List
from datetime import datetime
import ipaddress

# Site Schemas
class SiteBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=255, description="Site name")
    location: Optional[str] = Field(None, max_length=500, description="Site location")
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
    name: str = Field(..., min_length=1, max_length=255, description="Device name")
    ip_address: str = Field(..., description="Device IP address")
    device_type: Optional[str] = Field("router", max_length=50)
    is_active: bool = True
    snmp_community: Optional[str] = Field(None, max_length=100)
    ssh_username: Optional[str] = Field(None, max_length=100)
    ssh_password: Optional[str] = Field(None, max_length=500)
    ssh_port: int = Field(22, ge=1, le=65535, description="SSH port number (1-65535)")
    
    @validator('ip_address')
    def validate_ip_address(cls, v):
        """Validate IP address format (IPv4 or IPv6)."""
        try:
            # version=4/6 is inferred, strict=False allows some leniency, 
            # but we want standard validation.
            ipaddress.ip_address(v) 
            return v
        except ValueError:
            raise ValueError(f"Invalid IP address format: {v}")
    
    @validator('name', 'ssh_username')
    def validate_string_length(cls, v):
        """Validate string fields are not too long."""
        if v and len(v) > 255:
            raise ValueError(f"Field too long (max 255 characters)")
        return v

class DeviceCreate(DeviceBase):
    site_id: UUID4

class DeviceResponse(BaseModel):
    """Device response - excludes sensitive fields."""
    id: UUID4
    name: str
    ip_address: str
    device_type: Optional[str] = "router"
    is_active: bool = True
    snmp_community: Optional[str] = None
    ssh_username: Optional[str] = None
    # ssh_password excluded - sensitive
    ssh_port: int = 22
    site_id: UUID4
    wg_ip_address: Optional[str] = None
    wg_public_key: Optional[str] = None
    # wg_private_key excluded - sensitive
    created_at: datetime
    
    class Config:
        from_attributes = True

class WireGuardProvisionResponse(BaseModel):
    device_id: UUID4
    wg_ip_address: str
    wg_public_key: str
    wg_private_key: str
    mikrotik_script: str

