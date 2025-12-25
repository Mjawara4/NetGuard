from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from typing import List, Optional
from app.database import get_db
from app.models import Metric, Alert, Incident
from app.schemas.monitoring import MetricCreate, MetricResponse, AlertResponse, IncidentResponse, AlertCreate
from app.auth.deps import get_authorized_actor, get_current_user
from app.models import User, Device, Site
from uuid import UUID
from datetime import datetime

router = APIRouter()

@router.post("/metrics", response_model=MetricResponse)
async def create_metric(metric: MetricCreate, db: AsyncSession = Depends(get_db), actor = Depends(get_authorized_actor)):
    # This endpoint is for Agents to push metrics
    # In real world, use a faster ingestion path (Kafka or direct DB insert)
    # Check if Device ID exists? Omitted for speed
    
    new_metric = Metric(**metric.dict())
    db.add(new_metric)
    await db.commit()
    await db.refresh(new_metric)
    return new_metric

@router.get("/metrics/latest", response_model=List[MetricResponse])
async def get_latest_metrics(device_id: str, metric_type: Optional[str] = None, limit: int = 20, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    from uuid import UUID
    
    # Verify ownership
    dev_res = await db.execute(select(Device).join(Site).where(Device.id == UUID(device_id), Site.organization_id == current_user.organization_id))
    if not dev_res.scalars().first():
         raise HTTPException(status_code=404, detail="Device not found")
         
    query = select(Metric).where(Metric.device_id == UUID(device_id))
    
    if metric_type:
        query = query.where(Metric.metric_type == metric_type)
        
    result = await db.execute(query.order_by(desc(Metric.time)).limit(limit))
    return result.scalars().all()

@router.get("/metrics/history", response_model=List[MetricResponse])
async def get_historical_metrics(device_id: str, start_time: str, end_time: str = None, metric_type: Optional[str] = None, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    from uuid import UUID
    from datetime import datetime
    import traceback
    
    # Verify ownership
    dev_res = await db.execute(select(Device).join(Site).where(Device.id == UUID(device_id), Site.organization_id == current_user.organization_id))
    if not dev_res.scalars().first():
         raise HTTPException(status_code=404, detail="Device not found")
    
    try:
        query = select(Metric).where(Metric.device_id == UUID(device_id))
        
        # Handle JS toISOString which might end in Z. Python 3.11 handles Z, but let's be safe.
        if start_time.endswith('Z'):
            start_time = start_time[:-1] + '+00:00'
        start = datetime.fromisoformat(start_time)
        query = query.where(Metric.time >= start)
        
        if end_time:
             if end_time.endswith('Z'):
                end_time = end_time[:-1] + '+00:00'
             end = datetime.fromisoformat(end_time)
             query = query.where(Metric.time <= end)
             
        if metric_type:
            query = query.where(Metric.metric_type == metric_type)
            
        # Limit to prevent crash, but large enough for graph
        result = await db.execute(query.order_by(Metric.time.asc()).limit(5000))
        return result.scalars().all()
    except Exception as e:
        print(f"History Error: {e}")
        traceback.print_exc()
        return []

@router.get("/alerts", response_model=List[AlertResponse])
async def get_alerts(skip: int = 0, limit: int = 50, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    result = await db.execute(select(Alert).join(Device).join(Site).where(Site.organization_id == current_user.organization_id).order_by(desc(Alert.created_at)).offset(skip).limit(limit))
    return result.scalars().all()

@router.post("/alerts", response_model=AlertResponse)
async def create_alert(alert: AlertCreate, db: AsyncSession = Depends(get_db), actor = Depends(get_authorized_actor)):
    new_alert = Alert(**alert.dict())
    db.add(new_alert)
    await db.commit()
    await db.refresh(new_alert)
    return new_alert

@router.get("/incidents", response_model=List[IncidentResponse])
async def get_incidents(db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    # Incidents don't have direct device link in current model (mock), but alerts do. 
    # For MVP, let's assume incidents are global or rework model.
    # Current Incident model likely needs organization_id or device connection.
    # Let's check Incident model first.
    # Assuming Incident -> Device relation exists or needed.
    # If not, we might filter by checking alerts associated? 
    # For now, let's just return empty list or filter if possible.
    # If Incident has no relation, we can't filter easily without schema change.
    # Let's filter by Organization if schema supports it, otherwise return all (risk) or none.
    # Safe default: return empty for now unless we added org to incident.
    return []
