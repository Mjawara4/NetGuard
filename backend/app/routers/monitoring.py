from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, Request
from app.core.config import settings
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from typing import List, Optional
from app.core.database import get_db
from app.models import Metric, Alert, Incident, AutoFixAction, AlertStatus, User, Device, Site, APIKey, UserRole
from app.schemas.monitoring import MetricCreate, MetricResponse, AlertResponse, IncidentResponse, AlertCreate, AlertUpdate, AutoFixActionCreate, AutoFixActionResponse, DashboardStatsResponse
from app.auth.deps import get_authorized_actor, get_current_user
from uuid import UUID
from datetime import datetime, timezone

router = APIRouter()
from app.core.limiter import limiter

@router.post("/metrics", response_model=MetricResponse)
async def create_metric(metric: MetricCreate, db: AsyncSession = Depends(get_db), actor = Depends(get_authorized_actor)):
    # This endpoint is for Agents to push metrics
    # In real world, use a faster ingestion path (Kafka or direct DB insert)
    import logging
    logger = logging.getLogger(__name__)
    
    try:
        # Verify device exists and belongs to actor's organization (if restricted)
        from app.models import Device, Site
        if isinstance(actor, User) and actor.role == UserRole.SUPER_ADMIN:
            dev_query = select(Device).where(Device.id == metric.device_id)
        elif isinstance(actor, APIKey) and not actor.organization_id:
            dev_query = select(Device).where(Device.id == metric.device_id)
        else:
            dev_query = select(Device).join(Site).where(
                Device.id == metric.device_id,
                Site.organization_id == actor.organization_id
            )
        
        dev_result = await db.execute(dev_query)
        device = dev_result.scalars().first()
        if not device:
            raise HTTPException(status_code=404, detail="Device not found or access denied")
        
        new_metric = Metric(**metric.dict())
        db.add(new_metric)
        await db.commit()
        await db.refresh(new_metric)
        return new_metric
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating metric: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to create metric")

@router.get("/metrics/latest", response_model=List[MetricResponse])
@limiter.limit("100/minute")
async def get_latest_metrics(request: Request, device_id: str, metric_type: Optional[str] = None, limit: int = 20, db: AsyncSession = Depends(get_db), actor = Depends(get_authorized_actor)):
    from uuid import UUID
    
    # Verify ownership
    if isinstance(actor, User) and actor.role == UserRole.SUPER_ADMIN:
         dev_query = select(Device).where(Device.id == UUID(device_id))
    elif isinstance(actor, APIKey) and not actor.organization_id:
         dev_query = select(Device).where(Device.id == UUID(device_id))
    else:
         dev_query = select(Device).join(Site).where(Device.id == UUID(device_id), Site.organization_id == actor.organization_id)
    
    dev_res = await db.execute(dev_query)
    if not dev_res.scalars().first():
         raise HTTPException(status_code=404, detail="Device not found")
         
    query = select(Metric).where(Metric.device_id == UUID(device_id))
    
    if metric_type:
        query = query.where(Metric.metric_type == metric_type)
        
    result = await db.execute(query.order_by(desc(Metric.time)).limit(limit))
    return result.scalars().all()

@router.get("/metrics/history", response_model=List[MetricResponse])
@limiter.limit("50/minute")
async def get_historical_metrics(request: Request, device_id: str, start_time: str, end_time: str = None, metric_type: Optional[str] = None, db: AsyncSession = Depends(get_db), actor = Depends(get_authorized_actor)):
    from uuid import UUID
    from datetime import datetime
    import traceback
    
    # Verify ownership
    if isinstance(actor, User) and actor.role == UserRole.SUPER_ADMIN:
         dev_query = select(Device).where(Device.id == UUID(device_id))
    elif isinstance(actor, APIKey) and not actor.organization_id:
         dev_query = select(Device).where(Device.id == UUID(device_id))
    else:
         dev_query = select(Device).join(Site).where(Device.id == UUID(device_id), Site.organization_id == actor.organization_id)
    
    dev_res = await db.execute(dev_query)
    if not dev_res.scalars().first():
         raise HTTPException(status_code=404, detail="Device not found")
    
    try:
        query = select(Metric).where(Metric.device_id == UUID(device_id))
        
        # Handle JS toISOString which might end in Z. Python 3.11 handles Z, but let's be safe.
        if start_time.endswith('Z'):
            start_time = start_time[:-1] + '+00:00'
        start = datetime.fromisoformat(start_time)
        # Ensure start is naive UTC if it has tzinfo
        if start.tzinfo is not None:
            start = start.astimezone(timezone.utc).replace(tzinfo=None)
            
        query = query.where(Metric.time >= start)
        
        if end_time:
             if end_time.endswith('Z'):
                end_time = end_time[:-1] + '+00:00'
             end = datetime.fromisoformat(end_time)
             if end.tzinfo is not None:
                end = end.astimezone(timezone.utc).replace(tzinfo=None)
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
async def get_alerts(skip: int = 0, limit: int = 50, db: AsyncSession = Depends(get_db), actor = Depends(get_authorized_actor)):
    if isinstance(actor, User) and actor.role == UserRole.SUPER_ADMIN:
        stmt = select(Alert).order_by(desc(Alert.created_at)).offset(skip).limit(limit)
    elif isinstance(actor, APIKey) and not actor.organization_id:
        stmt = select(Alert).order_by(desc(Alert.created_at)).offset(skip).limit(limit)
    else:
        stmt = select(Alert).join(Device).join(Site).where(Site.organization_id == actor.organization_id).order_by(desc(Alert.created_at)).offset(skip).limit(limit)
    
    result = await db.execute(stmt)
    return result.scalars().all()

@router.post("/alerts", response_model=AlertResponse)
async def create_alert(alert: AlertCreate, db: AsyncSession = Depends(get_db), actor = Depends(get_authorized_actor)):
    new_alert = Alert(**alert.dict())
    db.add(new_alert)
    await db.commit()
    await db.refresh(new_alert)
    return new_alert

@router.get("/incidents", response_model=List[IncidentResponse])
async def get_incidents(db: AsyncSession = Depends(get_db), actor = Depends(get_authorized_actor)):
    if isinstance(actor, User) and actor.role == UserRole.SUPER_ADMIN:
        stmt = select(Incident).order_by(desc(Incident.created_at))
    elif isinstance(actor, APIKey) and not actor.organization_id:
        stmt = select(Incident).order_by(desc(Incident.created_at))
    else:
        stmt = select(Incident).join(Alert).join(Device).join(Site).where(Site.organization_id == actor.organization_id).order_by(desc(Incident.created_at))
    
    result = await db.execute(stmt)
    return result.scalars().all()

@router.patch("/alerts/{alert_id}", response_model=AlertResponse)
async def update_alert(alert_id: str, update: AlertUpdate, db: AsyncSession = Depends(get_db), actor = Depends(get_authorized_actor)):
    # Verify ownership via device -> site
    if isinstance(actor, User) and actor.role == UserRole.SUPER_ADMIN:
        stmt = select(Alert).where(Alert.id == UUID(alert_id))
    elif isinstance(actor, APIKey) and not actor.organization_id:
        stmt = select(Alert).where(Alert.id == UUID(alert_id))
    else:
        stmt = select(Alert).join(Device).join(Site).where(Alert.id == UUID(alert_id), Site.organization_id == actor.organization_id)
    
    result = await db.execute(stmt)
    alert_obj = result.scalars().first()
    
    if not alert_obj:
        raise HTTPException(status_code=404, detail="Alert not found")
        
    alert_obj.status = update.status
    if update.status in [AlertStatus.RESOLVED, AlertStatus.AUTO_FIXED]:
        alert_obj.resolved_at = datetime.utcnow()
        
    await db.commit()
    await db.refresh(alert_obj)
    return alert_obj

@router.post("/alerts/{alert_id}/fix-actions", response_model=AutoFixActionResponse)
async def create_fix_action(alert_id: str, action: AutoFixActionCreate, db: AsyncSession = Depends(get_db), actor = Depends(get_authorized_actor)):
    # Verify alert ownership
    if isinstance(actor, User) and actor.role == UserRole.SUPER_ADMIN:
        stmt = select(Alert).where(Alert.id == UUID(alert_id))
    elif isinstance(actor, APIKey) and not actor.organization_id:
        stmt = select(Alert).where(Alert.id == UUID(alert_id))
    else:
        stmt = select(Alert).join(Device).join(Site).where(Alert.id == UUID(alert_id), Site.organization_id == actor.organization_id)
        
    result = await db.execute(stmt)
    alert_obj = result.scalars().first()
    
    if not alert_obj:
        raise HTTPException(status_code=404, detail="Alert not found")
        
    new_action = AutoFixAction(
        alert_id=UUID(alert_id),
        action_type=action.action_type,
        status=action.status,
        log_output=action.log_output
    )
    db.add(new_action)
    await db.commit()
    await db.refresh(new_action)
    return new_action

@router.get("/dashboard-stats", response_model=DashboardStatsResponse)
@limiter.limit("60/minute")
async def get_dashboard_stats(request: Request, db: AsyncSession = Depends(get_db), actor = Depends(get_authorized_actor)):
    from sqlalchemy import func
    import logging
    logger = logging.getLogger(__name__)

    # 1. System Health (Online Routers %)
    # Logic: Get all active routers for org.
    # Get latest 'status' metric for each.
    # Calculate % of routers where status == 1.0
    
    # Get all active routers for org.
    if isinstance(actor, User) and actor.role == UserRole.SUPER_ADMIN:
        base_query = select(Device).where(Device.device_type == 'router', Device.is_active == True)
    elif isinstance(actor, APIKey) and not actor.organization_id:
        base_query = select(Device).where(Device.device_type == 'router', Device.is_active == True)
    else:
        base_query = select(Device).join(Site).where(
            Device.device_type == 'router',
            Device.is_active == True,
            Site.organization_id == actor.organization_id
        )
    
    routers_res = await db.execute(base_query)
    routers = routers_res.scalars().all()
    
    total_routers = len(routers)
    online_routers = 0
    
    active_users_count = 0
    all_hotspot_users = []
    
    for router in routers:
        # Check Up Status
        # Get latest uptime_status or status
        status_res = await db.execute(
            select(Metric).where(
                Metric.device_id == router.id,
                Metric.metric_type == 'status' 
            ).order_by(desc(Metric.time)).limit(1)
        )
        status_metric = status_res.scalars().first()
        if status_metric and status_metric.value == 1.0:
            online_routers += 1
            
        # 2. Active Users (Sum of 'hotspot_users')
        users_res = await db.execute(
            select(Metric).where(
                Metric.device_id == router.id,
                Metric.metric_type == 'hotspot_users'
            ).order_by(desc(Metric.time)).limit(1)
        )
        users_metric = users_res.scalars().first()
        if users_metric:
            active_users_count += int(users_metric.value)
            
        # 3. Top Consumption (Aggregate from 'hotspot_traffic')
        traffic_res = await db.execute(
            select(Metric).where(
                Metric.device_id == router.id,
                Metric.metric_type == 'hotspot_traffic'
            ).order_by(desc(Metric.time)).limit(1)
        )
        traffic_metric = traffic_res.scalars().first()
        if traffic_metric and traffic_metric.meta_data and 'users' in traffic_metric.meta_data:
            # Parse users from metadata
            raw_users = traffic_metric.meta_data['users']
            for u in raw_users:
                # Convert to schema format
                total = u.get('bytes_in', 0) + u.get('bytes_out', 0)
                all_hotspot_users.append({
                    'user': u.get('user'),
                    'ip': u.get('ip'),
                    'mac': u.get('mac'),
                    'bytes_in': u.get('bytes_in', 0),
                    'bytes_out': u.get('bytes_out', 0),
                    'total_bytes': total
                })

    # Sort all users by total bytes desc
    all_hotspot_users.sort(key=lambda x: x['total_bytes'], reverse=True)
    top_consumption = all_hotspot_users[:50] # Return top 50 global

    health_percentage = 100.0
    if total_routers > 0:
        health_percentage = (online_routers / total_routers) * 100.0
    
    return {
        "system_health": round(health_percentage, 1),
        "active_users": active_users_count,
        "top_consumption": top_consumption
    }
