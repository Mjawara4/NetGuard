from pydantic import BaseModel, UUID4, Field, validator
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

    @validator('value')
    def validate_metric_value(cls, v, values):
        """Validate metric values for known types."""
        metric_type = values.get('metric_type')
        if metric_type in ['cpu_usage', 'memory_usage']:
            if not (0 <= v <= 100):
                raise ValueError(f"{metric_type} must be between 0 and 100")
        return v

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

class AlertUpdate(BaseModel):
    status: AlertStatus
    resolution_summary: Optional[str] = None

# AutoFixAction
class AutoFixActionCreate(BaseModel):
    action_type: str
    status: str
    log_output: Optional[str] = None

class AutoFixActionResponse(AutoFixActionCreate):
    id: UUID4
    alert_id: UUID4
    created_at: datetime
    
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

# Dashboard Stats
class HotspotUser(BaseModel):
    user: Optional[str] = None
    ip: Optional[str] = None
    mac: Optional[str] = None
    bytes_in: int = 0
    bytes_out: int = 0
    total_bytes: int = 0

class DashboardStatsResponse(BaseModel):
    system_health: float # Percentage
    active_users: int
    top_consumption: List[HotspotUser]
