from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, Request
from app.core.config import settings
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc, func
from typing import List, Optional
import os
import json
import redis
from app.core.database import get_db
from app.models import Metric, Alert, Incident, AutoFixAction, AlertStatus, User, Device, Site, APIKey, UserRole
from app.schemas.monitoring import MetricCreate, MetricResponse, AlertResponse, IncidentResponse, AlertCreate, AlertUpdate, AutoFixActionCreate, AutoFixActionResponse, DashboardStatsResponse
from app.auth.deps import get_authorized_actor, get_current_user
from uuid import UUID
from datetime import datetime, timezone

router = APIRouter()
from app.core.limiter import limiter

# Redis client for caching dashboard stats
try:
    redis_client = redis.Redis(
        host=os.getenv("REDIS_HOST", "redis"),
        port=6379,
        db=0,
        decode_responses=True
    )
    redis_client.ping()
except Exception:
    redis_client = None
    import logging
    logging.getLogger(__name__).warning("Redis unavailable; dashboard caching disabled.")

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

@router.post("/metrics/batch", response_model=dict)
async def create_metrics_batch(batch: List[MetricCreate], db: AsyncSession = Depends(get_db), actor = Depends(get_authorized_actor)):
    import logging
    logger = logging.getLogger(__name__)

    if not batch:
        return {"created": 0}

    try:
        # Collect unique device IDs from batch
        device_ids = {m.device_id for m in batch}

        # Verify all devices exist and belong to actor's organization in one query
        if isinstance(actor, User) and actor.role == UserRole.SUPER_ADMIN:
            dev_query = select(Device).where(Device.id.in_(device_ids))
        elif isinstance(actor, APIKey) and not actor.organization_id:
            dev_query = select(Device).where(Device.id.in_(device_ids))
        else:
            dev_query = select(Device).join(Site).where(
                Device.id.in_(device_ids),
                Site.organization_id == actor.organization_id
            )

        dev_result = await db.execute(dev_query)
        valid_device_ids = {d.id for d in dev_result.scalars().all()}

        if not valid_device_ids:
            raise HTTPException(status_code=404, detail="No valid devices found for provided metrics")

        # Filter metrics to only valid devices (skip invalid silently to avoid blocking whole batch)
        valid_metrics = [m for m in batch if m.device_id in valid_device_ids]
        skipped = len(batch) - len(valid_metrics)
        if skipped > 0:
            logger.warning(f"Batch metrics: skipped {skipped} metrics for unauthorized/missing devices")

        # Insert all valid metrics in one transaction
        for metric in valid_metrics:
            db.add(Metric(**metric.dict()))

        await db.commit()
        return {"created": len(valid_metrics), "skipped": skipped}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating batch metrics: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to create batch metrics")

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
        stmt = select(Alert).where(Alert.status != AlertStatus.ARCHIVED).order_by(desc(Alert.created_at)).offset(skip).limit(limit)
    elif isinstance(actor, APIKey) and not actor.organization_id:
        stmt = select(Alert).where(Alert.status != AlertStatus.ARCHIVED).order_by(desc(Alert.created_at)).offset(skip).limit(limit)
    else:
        stmt = select(Alert).join(Device).join(Site).where(Site.organization_id == actor.organization_id, Alert.status != AlertStatus.ARCHIVED).order_by(desc(Alert.created_at)).offset(skip).limit(limit)
    
    result = await db.execute(stmt)
    return result.scalars().all()

@router.post("/alerts", response_model=AlertResponse)
async def create_alert(alert: AlertCreate, background_tasks: BackgroundTasks, db: AsyncSession = Depends(get_db), actor = Depends(get_authorized_actor)):
    new_alert = Alert(**alert.dict())
    db.add(new_alert)
    await db.commit()
    await db.refresh(new_alert)
    
    # Trigger Intelligent Grouping
    from app.services.alert_grouping import process_alert_grouping
    background_tasks.add_task(process_alert_grouping, str(new_alert.id))
    
    return new_alert

@router.post("/alerts/clear", response_model=dict)
async def clear_alerts(db: AsyncSession = Depends(get_db), actor = Depends(get_authorized_actor)):
    """
    Archives all currently visible alerts (Open/Resolved) for the organization.
    They will no longer appear in the main list.
    """
    if isinstance(actor, User) and actor.role == UserRole.SUPER_ADMIN:
        stmt = select(Alert).where(Alert.status != AlertStatus.ARCHIVED)
    elif isinstance(actor, APIKey) and not actor.organization_id:
        stmt = select(Alert).where(Alert.status != AlertStatus.ARCHIVED)
    else:
        stmt = select(Alert).join(Device).join(Site).where(
            Site.organization_id == actor.organization_id,
            Alert.status != AlertStatus.ARCHIVED
        )
    
    result = await db.execute(stmt)
    alerts = result.scalars().all()
    
    count = 0
    for alert in alerts:
        alert.status = AlertStatus.ARCHIVED
        count += 1
        
    await db.commit()
    return {"status": "success", "cleared_count": count}

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
    import logging
    logger = logging.getLogger(__name__)

    # Cache key based on actor identity
    cache_key = f"dashboard:stats:{getattr(actor, 'id', 'api')}"
    if redis_client:
        try:
            cached = redis_client.get(cache_key)
            if cached:
                return json.loads(cached)
        except Exception:
            pass

    # 1. Get active router IDs for this actor in one query
    if isinstance(actor, User) and actor.role == UserRole.SUPER_ADMIN:
        router_query = select(Device.id).where(Device.device_type == 'router', Device.is_active == True)
    elif isinstance(actor, APIKey) and not actor.organization_id:
        router_query = select(Device.id).where(Device.device_type == 'router', Device.is_active == True)
    else:
        router_query = select(Device.id).join(Site).where(
            Device.device_type == 'router',
            Device.is_active == True,
            Site.organization_id == actor.organization_id
        )

    routers_res = await db.execute(router_query)
    router_ids = [r[0] for r in routers_res.all()]
    total_routers = len(router_ids)

    online_routers = 0
    active_users_count = 0
    all_hotspot_users = []

    if router_ids:
        # 2. Single query to get latest metric per router per type using window function
        metric_types = ['status', 'hotspot_users', 'hotspot_traffic']
        subq = select(
            Metric,
            func.row_number().over(
                partition_by=[Metric.device_id, Metric.metric_type],
                order_by=desc(Metric.time)
            ).label("rn")
        ).where(
            Metric.device_id.in_(router_ids),
            Metric.metric_type.in_(metric_types)
        ).subquery()

        latest_query = select(subq).where(subq.c.rn == 1)
        metrics_res = await db.execute(latest_query)
        rows = metrics_res.mappings().all()

        # Index results by device_id -> metric_type
        metrics_by_device = {}
        for row in rows:
            did = row['device_id']
            mtype = row['metric_type']
            metrics_by_device.setdefault(did, {})[mtype] = row

        for rid in router_ids:
            dev_metrics = metrics_by_device.get(rid, {})

            status_m = dev_metrics.get('status')
            if status_m and status_m['value'] == 1.0:
                online_routers += 1

            users_m = dev_metrics.get('hotspot_users')
            if users_m:
                active_users_count += int(users_m['value'])

            traffic_m = dev_metrics.get('hotspot_traffic')
            if traffic_m and traffic_m['meta_data'] and 'users' in traffic_m['meta_data']:
                for u in traffic_m['meta_data']['users']:
                    total = u.get('bytes_in', 0) + u.get('bytes_out', 0)
                    all_hotspot_users.append({
                        'user': u.get('user'),
                        'ip': u.get('ip'),
                        'mac': u.get('mac'),
                        'bytes_in': u.get('bytes_in', 0),
                        'bytes_out': u.get('bytes_out', 0),
                        'total_bytes': total
                    })

    all_hotspot_users.sort(key=lambda x: x['total_bytes'], reverse=True)
    top_consumption = all_hotspot_users[:50]

    health_percentage = 100.0
    if total_routers > 0:
        health_percentage = (online_routers / total_routers) * 100.0

    response = {
        "system_health": round(health_percentage, 1),
        "active_users": active_users_count,
        "top_consumption": top_consumption
    }

    if redis_client:
        try:
            redis_client.setex(cache_key, 30, json.dumps(response))
        except Exception:
            pass

    return response
