from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models import Alert, Incident
from app.core.database import AsyncSessionLocal
from datetime import datetime
import os
import logging

from app.core.llm_client import chat_completion

logger = logging.getLogger(__name__)


async def process_alert_grouping(alert_id: str):
    """
    Background task to group alerts into incidents.

    Current schema links one incident to one alert (Incident.alert_id is unique),
    so we create a single incident per alert and optionally ask the LLM to
    polish the summary/root_cause.
    """
    async with AsyncSessionLocal() as db:
        try:
            # Fetch the new alert, eager-loading its incident relationship so we
            # don't trigger lazy loads in an async context.
            result = await db.execute(
                select(Alert)
                .options(selectinload(Alert.incident))
                .where(Alert.id == alert_id)
            )
            alert = result.scalars().first()
            if not alert:
                return

            # Already linked to an incident (e.g. reporter-agent created one)
            if alert.incident:
                return

            # Create a new incident for this alert
            new_incident = Incident(
                alert_id=alert.id,
                summary=f"Incident: {alert.rule_name}",
                root_cause=f"Auto-created from alert: {alert.message}",
                created_at=datetime.utcnow(),
            )
            db.add(new_incident)
            await db.commit()

            # Ask AI to rename / summarize if we have any LLM key configured
            await rename_incident_with_ai(new_incident.id, db)

        except Exception as e:
            logger.error(f"Error in alert grouping: {e}")


async def rename_incident_with_ai(incident_id, db: AsyncSession):
    if not (
        os.getenv("OPENAI_API_KEY")
        or os.getenv("GEMINI_API_KEY")
        or os.getenv("KIMI_API_KEY")
    ):
        return

    # Fetch incident and its linked alert
    inc_res = await db.execute(
        select(Incident).options(selectinload(Incident.alert)).where(Incident.id == incident_id)
    )
    incident = inc_res.scalars().first()
    if not incident or not incident.alert:
        return

    alert = incident.alert
    prompt = f"""
    Analyze this network alert:
    - Rule: {alert.rule_name}
    - Message: {alert.message}
    - Severity: {alert.severity}
    - Created: {alert.created_at}

    Generate a concise, professional Incident Summary (max 5 words) and a 1-sentence Root Cause.
    Format: Summary | Root Cause
    """

    try:
        response_text = chat_completion(prompt)
        if response_text and "|" in response_text:
            summary, root_cause = response_text.split("|", 1)
            incident.summary = summary.strip()
            incident.root_cause = root_cause.strip()
            await db.commit()
    except Exception as e:
        logger.error(f"AI Incident Renaming Failed: {e}")
