from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from app.models import Alert, Incident, AlertStatus
from app.core.database import SessionLocal
from datetime import datetime, timedelta
import os
import openai
import logging

logger = logging.getLogger(__name__)

LLM_PROVIDER = os.getenv("LLM_PROVIDER", "openai").lower()
LLM_API_KEY = os.getenv("GEMINI_API_KEY") if LLM_PROVIDER == "gemini" else os.getenv("OPENAI_API_KEY")

async def process_alert_grouping(alert_id: str):
    """
    Background task to group alerts into incidents.
    """
    async with SessionLocal() as db:
        try:
            # 1. Fetch the new alert
            result = await db.execute(select(Alert).where(Alert.id == alert_id))
            alert = result.scalars().first()
            if not alert:
                return

            # 2. Find recent open incidents (last 2 hours)
            # Simple heuristic: Same device or same site + temporal proximity
            # For MVP: Just check if there is an open incident for this device created < 2 hours ago
            
            # Check if alert is already linked
            if alert.incident:
                return

            # Find existing active incident for this device
            inc_res = await db.execute(
                select(Incident)
                .join(Alert)
                .where(
                    Alert.device_id == alert.device_id,
                    Incident.status == 'OPEN',
                    Incident.created_at > datetime.utcnow() - timedelta(hours=2)
                )
                .order_by(desc(Incident.created_at))
            )
            existing_incident = inc_res.scalars().first()

            if existing_incident:
                # Link to existing
                alert.incident = existing_incident
                await db.commit()
                # Optionally rename incident if it grows
            else:
                # Create NEW Incident
                new_incident = Incident(
                    status='OPEN',
                    severity=alert.severity,
                    name=f"Incident: {alert.rule_name}", # Temporary name
                    description=f"Auto-created from alert: {alert.message}"
                )
                db.add(new_incident)
                await db.flush() # Get ID
                
                alert.incident = new_incident
                await db.commit()
                existing_incident = new_incident

            # 3. AI Renaming (Async)
            # If incident has > 2 alerts, ask AI to summarize
            await rename_incident_with_ai(existing_incident.id, db)

        except Exception as e:
            logger.error(f"Error in alert grouping: {e}")

async def rename_incident_with_ai(incident_id, db: AsyncSession):
    if not LLM_API_KEY:
        return

    # Fetch incident and alerts
    inc_res = await db.execute(select(Incident).where(Incident.id == incident_id))
    incident = inc_res.scalars().first()
    
    # Get alerts
    alerts_res = await db.execute(select(Alert).where(Alert.incident_id == incident_id))
    alerts = alerts_res.scalars().all()
    
    if len(alerts) < 2:
        return # Not enough context yet

    alerts_summary = "\n".join([f"- {a.rule_name}: {a.message} ({a.created_at})" for a in alerts])

    prompt = f"""
    Analyze these network alerts grouped into an incident:
    {alerts_summary}
    
    Generate a concise, professional Incident Title (max 5 words) and a 1-sentence Description.
    Format: Title | Description
    """
    
    try:
        response_text = ""
        if LLM_PROVIDER == "gemini":
            from google import genai
            client = genai.Client(api_key=LLM_API_KEY)
            resp = client.models.generate_content(
                model='gemini-3-flash',
                contents=prompt
            )
            response_text = resp.text
            
        elif LLM_PROVIDER == "openai":
            client = openai.OpenAI(api_key=LLM_API_KEY)
            completion = client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[{"role": "user", "content": prompt}]
            )
            response_text = completion.choices[0].message.content

        if "|" in response_text:
            title, desc = response_text.split("|", 1)
            incident.name = title.strip()
            incident.description = desc.strip()
            await db.commit()
            
    except Exception as e:
        logger.error(f"AI Incident Renaming Failed: {e}")
