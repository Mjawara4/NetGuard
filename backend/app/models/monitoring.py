from sqlalchemy import Column, String, Float, DateTime, ForeignKey, Enum, Text, Boolean
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
import uuid
import enum
from datetime import datetime
from app.core.database import Base

# Enums
class AlertSeverity(str, enum.Enum):
    CRITICAL = "critical"
    WARNING = "warning"
    INFO = "info"

class AlertStatus(str, enum.Enum):
    OPEN = "open"
    AUTO_FIXED = "auto_fixed"
    RESOLVED = "resolved"

class Metric(Base):
    __tablename__ = "metrics"
    
    # TimescaleDB usually recommends (time, device_id) as composite index/partition key
    # But we need a primary key for SQLAlchemy mostly. 
    # For Timescale, we will let 'time' be the partitioning column.
    
    time = Column(DateTime, primary_key=True, default=datetime.utcnow)
    device_id = Column(UUID(as_uuid=True), ForeignKey("devices.id"), primary_key=True)
    metric_type = Column(String, nullable=False) # cpu, memory, latency, packet_loss, interface_status
    value = Column(Float, nullable=False)
    unit = Column(String)
    meta_data = Column(JSONB, nullable=True) # Extra details
    
    device = relationship("Device", back_populates="metrics")

class Alert(Base):
    __tablename__ = "alerts"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    device_id = Column(UUID(as_uuid=True), ForeignKey("devices.id"), nullable=False)
    rule_name = Column(String, nullable=False)
    severity = Column(String, default=AlertSeverity.WARNING)
    status = Column(String, default=AlertStatus.OPEN)
    message = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    resolved_at = Column(DateTime, nullable=True)
    
    device = relationship("Device", back_populates="alerts")
    incident = relationship("Incident", uselist=False, back_populates="alert")
    auto_fix_actions = relationship("AutoFixAction", back_populates="alert")

class Incident(Base):
    __tablename__ = "incidents"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    alert_id = Column(UUID(as_uuid=True), ForeignKey("alerts.id"), unique=True)
    summary = Column(Text) # Human readable summary from ReporterAgent
    root_cause = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    alert = relationship("Alert", back_populates="incident")

class AutoFixAction(Base):
    __tablename__ = "auto_fix_actions"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    alert_id = Column(UUID(as_uuid=True), ForeignKey("alerts.id"), nullable=False)
    action_type = Column(String, nullable=False) # restart_service, reboot, etc
    status = Column(String) # pending, success, failed
    log_output = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    alert = relationship("Alert", back_populates="auto_fix_actions")

class AgentLog(Base):
    __tablename__ = "agent_logs"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    agent_name = Column(String, nullable=False)
    level = Column(String, default="INFO")
    message = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
