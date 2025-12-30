import time
import requests
import os
import json
from retry_utils import retry_with_backoff

API_URL = os.getenv("API_URL", "http://backend:8000/api/v1")

API_KEY = os.getenv("NETGUARD_API_KEY")

import logging
import sys

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)],
    force=True
)
logger = logging.getLogger("diagnoser-agent")

API_URL = os.getenv("API_URL", "http://backend:8000/api/v1")

API_KEY = os.getenv("NETGUARD_API_KEY")

if not API_KEY:
    logger.critical("FATAL: NETGUARD_API_KEY env var not set.")
    sys.exit(1)

def get_headers():
    return {"X-API-Key": API_KEY}

# Mocked analysis
def analyze_metrics():
    # In real world: Query TimescaleDB for last 1 min metrics
    # Here: We will just alert on random devices if we assume we have access to them?
    # Better: The API should expose "devices with issues".
    # For MVP: I will just Create Alerts for devices that I know exist.
    
    try:
        # Get devices with retry
        try:
            resp = requests.get(
                f"{API_URL}/inventory/devices",
                headers=get_headers(),
                timeout=10
            )
            resp.raise_for_status()
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to fetch devices: {e}")
            return
        devices = resp.json()
        
        for device in devices:
            # Query latest status metric
            try:
                m_resp = requests.get(
                    f"{API_URL}/monitoring/metrics/latest?device_id={device['id']}&metric_type=uptime_status&limit=1",
                    headers=get_headers(),
                    timeout=10
                )
                if m_resp.status_code == 200:
                    metrics = m_resp.json()
                    if metrics and len(metrics) > 0:
                        latest_status = metrics[0]['value']
                        
                        # Check if offline
                        if latest_status == 0.0:
                             # CHECK IF ALERT ALREADY EXISTS
                             existing = requests.get(
                                 f"{API_URL}/monitoring/alerts?device_id={device['id']}",
                                 headers=get_headers(),
                                 timeout=10
                             )
                             already_alerted = False
                             if existing.status_code == 200:
                                 for a in existing.json():
                                     if a['rule_name'] == 'Device Offline' and a['status'] == 'open':
                                         already_alerted = True
                                         break
                             
                             if not already_alerted:
                                 alert_payload = {
                                     "device_id": device['id'],
                                     "rule_name": "Device Offline",
                                     "severity": "critical",
                                     "message": f"Device {device['name']} is not responding to ping.",
                                     "status": "open"
                                 }
                                 requests.post(
                                     f"{API_URL}/monitoring/alerts",
                                     json=alert_payload,
                                     headers=get_headers(),
                                     timeout=10
                                 )
                                 logger.warning(f"Created alert (OFFLINE) for {device['name']}")
                             
            except Exception as e_status:
                 logger.error(f"Status check failed: {e_status}")

            # CPU Check
            try:
                c_resp = requests.get(
                    f"{API_URL}/monitoring/metrics/latest?device_id={device['id']}&metric_type=cpu_usage&limit=1",
                    headers=get_headers(),
                    timeout=10
                )
                if c_resp.status_code == 200:
                    metrics = c_resp.json()
                    if metrics and len(metrics) > 0:
                        cpu = metrics[0]['value']
                        if cpu > 80:
                             alert_payload = {
                                 "device_id": device['id'],
                                 "rule_name": "High CPU",
                                 "severity": "critical",
                                 "message": f"High CPU usage detected: {cpu}%",
                                 "status": "open"
                             }
                             requests.post(f"{API_URL}/monitoring/alerts", json=alert_payload, headers=get_headers())
                             logger.warning(f"Created alert (HIGH CPU) for {device['name']}")
            except Exception as e_cpu:
                 logger.error(f"CPU check failed: {e_cpu}")
            except Exception as e_inner:
                logger.error(f"Error checking device {device['name']}: {e_inner}")
                  
    except Exception as e:
        logger.exception(f"Diagnoser error: {e}")

def run_agent():
    logger.info("Starting Diagnoser Agent...")
    # Login removed
    pass
        
    while True:
        analyze_metrics()
        logger.info("Diagnosis cycle complete.")
        time.sleep(5)

if __name__ == "__main__":
    run_agent()
