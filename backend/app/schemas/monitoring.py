from pydantic import BaseModel, UUID4, Field
from typing import Optional, Any, Dict, List
from datetime import datetime
from app.models.monitoring import AlertSeverity, AlertStatus

# Metric
class MetricCreate(BaseModel):
    device_id: UUID4
    metric_type: str
    value: float
    unit: Optional[str] = None
    meta_data: Optional[Dict[str, Any]] = None
    time: Optional[datetime] = None # Optional, defaults to now

class MetricResponse(MetricCreate):
    time: datetime
    class Config:
        from_attributes = True

# Alert
class AlertBase(BaseModel):
    rule_name: str
    severity: AlertSeverity
    message: str

class AlertCreate(AlertBase):
    device_id: UUID4

class AlertResponse(AlertBase):
    id: UUID4
    device_id: UUID4
    status: AlertStatus
    created_at: datetime
    resolved_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True

# Incident
class IncidentResponse(BaseModel):
    id: UUID4
    alert_id: UUID4
    summary: Optional[str]
    root_cause: Optional[str]
    created_at: datetime
    
    class Config:
        from_attributes = True
