import os
import time
import requests
import logging
import sys
from log_utils import post_agent_log
from llm_client import chat_completion

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)],
    force=True
)
logger = logging.getLogger("reporter-agent")

API_URL = os.getenv("API_URL", "http://backend:8000/api/v1")
API_KEY = os.getenv("NETGUARD_API_KEY")

if not API_KEY:
    logger.critical("FATAL: NETGUARD_API_KEY env var not set.")
    sys.exit(1)

def get_headers():
    return {"X-API-Key": API_KEY}

def get_resolved_alerts():
    """Fetch alerts with status resolved or auto_fixed."""
    alerts = []
    for status in ["resolved", "auto_fixed"]:
        try:
            r = requests.get(
                f"{API_URL}/monitoring/alerts",
                params={"status": status, "limit": 100},
                headers=get_headers(), timeout=10
            )
            if r.status_code == 200:
                alerts.extend(r.json())
        except Exception as e:
            logger.error(f"Failed to fetch {status} alerts: {e}")
    return alerts

def get_existing_incident_alert_ids():
    """Return set of alert_ids that already have incidents."""
    try:
        r = requests.get(f"{API_URL}/monitoring/incidents", headers=get_headers(), timeout=10)
        if r.status_code == 200:
            return {inc['alert_id'] for inc in r.json()}
    except Exception as e:
        logger.error(f"Failed to fetch incidents: {e}")
    return set()

def generate_summary_llm(alert):
    """Try LLM summary generation. Returns (summary, root_cause) or (None, None)."""
    if not (
        os.getenv("LLM_API_KEY")
        or os.getenv("GEMINI_API_KEY")
        or os.getenv("OPENAI_API_KEY")
        or os.getenv("KIMI_API_KEY")
    ):
        return None, None

    prompt = (
        f"Network alert resolved. Rule: {alert['rule_name']}. "
        f"Message: {alert['message']}. Status: {alert['status']}. "
        f"Provide a one-sentence summary and one-sentence root cause analysis. "
        f'Output JSON: {{"summary": "...", "root_cause": "..."}}'
    )

    try:
        response_text = chat_completion(prompt, response_format="json_object")
        if not response_text:
            return None, None

        import json
        data = json.loads(response_text)
        return data.get("summary"), data.get("root_cause")
    except Exception as e:
        logger.warning(f"LLM summary failed: {e}")

    return None, None

def generate_summary_template(alert):
    """Fallback template-based summary."""
    rule = alert['rule_name']
    status = alert['status']
    summary = f"{rule} alert was {status.replace('_', ' ')}. {alert['message']}"
    root_cause = f"Detected by automated monitoring rule '{rule}'."
    return summary, root_cause

def create_incident(alert_id, summary, root_cause):
    try:
        r = requests.post(
            f"{API_URL}/monitoring/incidents",
            json={"alert_id": alert_id, "summary": summary, "root_cause": root_cause},
            headers=get_headers(), timeout=10
        )
        if r.status_code in (200, 201):
            logger.info(f"Incident created for alert {alert_id}")
            return True
        elif r.status_code == 409:
            logger.debug(f"Incident already exists for alert {alert_id}")
        else:
            logger.error(f"Failed to create incident: {r.status_code} {r.text}")
    except Exception as e:
        logger.error(f"Incident create error: {e}")
    return False

def run_agent():
    logger.info("Starting Reporter Agent...")
    post_agent_log("reporter-agent", "INFO", "Reporter Agent started")

    while True:
        try:
            alerts = get_resolved_alerts()
            existing_ids = get_existing_incident_alert_ids()

            unreported = [a for a in alerts if str(a['id']) not in existing_ids]
            if unreported:
                logger.info(f"Generating incidents for {len(unreported)} unreported alerts")

            for alert in unreported:
                summary, root_cause = generate_summary_llm(alert)
                if not summary:
                    summary, root_cause = generate_summary_template(alert)

                created = create_incident(str(alert['id']), summary, root_cause)
                if created:
                    post_agent_log("reporter-agent", "INFO",
                                   f"Incident created for alert {alert['id']}: {alert['rule_name']}")

        except Exception as e:
            logger.exception(f"Reporter loop error: {e}")

        time.sleep(60)

if __name__ == "__main__":
    run_agent()
