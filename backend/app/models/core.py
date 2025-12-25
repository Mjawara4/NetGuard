from sqlalchemy import Column, String, Boolean, DateTime, ForeignKey, Enum, Integer
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
import uuid
import enum
from datetime import datetime
from app.database import Base

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

    # Store secrets securely in real world, this is MVP
    created_at = Column(DateTime, default=datetime.utcnow)
    
    site = relationship("Site", back_populates="devices")
    metrics = relationship("Metric", back_populates="device")
    alerts = relationship("Alert", back_populates="device")
