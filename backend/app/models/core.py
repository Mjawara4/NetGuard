from sqlalchemy import Column, String, Boolean, DateTime, ForeignKey, Enum, Integer, event, BigInteger, Text

from sqlalchemy.dialects.postgresql import UUID, JSONB
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

    # Portal payments (Modem Pay). Each org uses its OWN account, so money routes
    # straight to them; NetGuard holds none. The two secrets are encrypted at rest
    # (Fernet, same as device secrets) and never returned in plaintext by any API.
    modempay_secret_key = Column(Text, nullable=True)
    modempay_webhook_secret = Column(Text, nullable=True)
    # Off until an org deliberately configures payments.
    payments_enabled = Column(Boolean, default=False, nullable=False, server_default="false")

    users = relationship("User", back_populates="organization")
    sites = relationship("Site", back_populates="organization")


class PaymentIntent(Base):
    """A ledger row per Modem Pay payment, keyed by the Modem Pay charge id.

    The charge id is the idempotency key: a replayed webhook for a charge already
    fulfilled finds its row here and grants nothing more. Also the audit trail for
    reconciliation (what was paid, for which router/plan, and the voucher granted).
    """
    __tablename__ = "payment_intents"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    device_id = Column(UUID(as_uuid=True), ForeignKey("devices.id"), nullable=False)
    charge_id = Column(String, unique=True, nullable=True)  # set once Modem Pay assigns it
    plan = Column(String, nullable=False)                   # the hotspot profile name
    amount = Column(BigInteger, nullable=False)             # minor units as paid
    currency = Column(String, nullable=False, default="GMD")
    status = Column(String, nullable=False, default="created")  # created|paid|fulfilled|failed
    voucher_username = Column(String, nullable=True)        # the code granted on fulfilment
    customer_mac = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

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
    # Set when the owner removes a router that has taken payments. The row and
    # its history stay; it is left out of every device list.
    archived_at = Column(DateTime, nullable=True)
    
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

class VoucherSale(Base):
    __tablename__ = "hotspot_sales"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    device_id = Column(UUID(as_uuid=True), ForeignKey("devices.id"), nullable=False)
    site_id = Column(UUID(as_uuid=True), ForeignKey("sites.id"), nullable=False)
    username = Column(String, nullable=False, index=True)
    profile = Column(String, nullable=False)
    comment = Column(String)
    uptime = Column(String) # For display
    uptime_sec = Column(Integer, default=0) # For calculations
    bytes_total = Column(BigInteger, default=0)
    price = Column(BigInteger, default=0)

    currency = Column(String, default="TZS")
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    
    # Optional: track if this was synced from a specific fetch
    sync_id = Column(String, nullable=True)

    device = relationship("Device")
    site = relationship("Site")

class VoucherBatch(Base):
    __tablename__ = "voucher_batches"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    device_id = Column(UUID(as_uuid=True), ForeignKey("devices.id"), nullable=False)
    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False)
    batch_name = Column(String, nullable=False)  # e.g. "Batch-user | 2024-01-01 10:00:00"
    prefix = Column(String, nullable=False)
    profile = Column(String, nullable=False)
    time_limit = Column(String, nullable=True)
    data_limit = Column(String, nullable=True)
    count = Column(Integer, nullable=False)
    vouchers = Column(JSONB, nullable=False, default=list)  # [{"username": "...", "password": "..."}, ...]
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    status = Column(String, nullable=True)

    device = relationship("Device")
    organization = relationship("Organization")
