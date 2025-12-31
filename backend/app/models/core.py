from sqlalchemy import Column, String, Boolean, DateTime, ForeignKey, Enum, Integer, event
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
import uuid
import enum
from datetime import datetime
from app.core.database import Base
from app.utils.encryption import encrypt_value, decrypt_value

class UserRole(str, enum.Enum):
    SUPER_ADMIN = "super_admin"
    ORG_ADMIN = "org_admin"
    NETWORK_AGENT = "network_agent"
    VIEWER = "viewer"

class Organization(Base):
    __tablename__ = "organizations"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    users = relationship("User", back_populates="organization")
    sites = relationship("Site", back_populates="organization")

class User(Base):
    __tablename__ = "users"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    full_name = Column(String)
    role = Column(String, default=UserRole.VIEWER) # Storing enum as string for simplicity
    is_active = Column(Boolean, default=True)
    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=True) # Super admin might not have org
    created_at = Column(DateTime, default=datetime.utcnow)
    
    organization = relationship("Organization", back_populates="users")

class Site(Base):
    __tablename__ = "sites"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String, nullable=False)
    location = Column(String)
    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False)
    auto_fix_enabled = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    organization = relationship("Organization", back_populates="sites")
    devices = relationship("Device", back_populates="site")

class Device(Base):
    __tablename__ = "devices"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String, nullable=False)
    ip_address = Column(String, nullable=False)
    device_type = Column(String) # router, switch, server, etc
    site_id = Column(UUID(as_uuid=True), ForeignKey("sites.id"), nullable=False)
    is_active = Column(Boolean, default=True)
    snmp_community = Column(String, nullable=True)
    ssh_username = Column(String, nullable=True)
    ssh_password = Column(String, nullable=True) # Store securely in production!
    ssh_port = Column(Integer, default=22)
    
    # WireGuard fields
    wg_public_key = Column(String, nullable=True)
    wg_ip_address = Column(String, nullable=True)
    wg_private_key = Column(String, nullable=True)

    # Hotspot Configuration
    from sqlalchemy.dialects.postgresql import JSON
    voucher_template = Column(JSON, nullable=True)

    # Store secrets securely in real world, this is MVP
    created_at = Column(DateTime, default=datetime.utcnow)
    
    site = relationship("Site", back_populates="devices")
    metrics = relationship("Metric", back_populates="device")
    alerts = relationship("Alert", back_populates="device")

# SQLAlchemy events for encryption/decryption
@event.listens_for(Device, "before_insert", propagate=True)
@event.listens_for(Device, "before_update", propagate=True)
def encrypt_device_secrets(mapper, connection, target):
    """Encrypt sensitive fields before insert/update."""
    if target.ssh_password:
        # Only encrypt if not already encrypted (dual-write mode)
        # Check if it looks encrypted (heuristic)
        if not target.ssh_password.startswith("gAAAAAB"):  # Fernet encrypted values start with this
            target.ssh_password = encrypt_value(target.ssh_password)
    
    if target.wg_private_key:
        # Only encrypt if not already encrypted
        if not target.wg_private_key.startswith("gAAAAAB"):
            target.wg_private_key = encrypt_value(target.wg_private_key)

# Note: SQLAlchemy's "load" event doesn't work reliably with async sessions.
# Instead, we use a helper function decrypt_device_secrets() that must be called
# manually after loading a device from the database.

def decrypt_device_secrets(device: "Device") -> "Device":
    """
    Decrypt sensitive fields on a Device instance.
    This must be called manually after loading a device from the database
    because SQLAlchemy's load event doesn't work with async sessions.
    
    Args:
        device: Device instance with potentially encrypted fields
        
    Returns:
        Device instance with decrypted fields (same instance, modified in place)
    """
    if device.ssh_password:
        device.ssh_password = decrypt_value(device.ssh_password)
    
    if device.wg_private_key:
        device.wg_private_key = decrypt_value(device.wg_private_key)
    
    return device
