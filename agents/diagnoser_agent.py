import time
import requests
import os
import logging
import sys

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)],
    force=True
)
logger = logging.getLogger("diagnoser-agent")

API_URL = os.getenv("API_URL", "http://backend:8000/api/v1")
API_KEY = os.getenv("NETGUARD_API_KEY")
CPU_THRESHOLD = float(os.getenv("CPU_THRESHOLD", "80"))
MEMORY_THRESHOLD = float(os.getenv("MEMORY_THRESHOLD", "85"))
HOTSPOT_USER_THRESHOLD = int(os.getenv("HOTSPOT_USER_THRESHOLD", "80"))
WG_OFFLINE_THRESHOLD = int(os.getenv("WG_OFFLINE_THRESHOLD", "180"))
WG_ONLINE_THRESHOLD = int(os.getenv("WG_ONLINE_THRESHOLD", "60"))

if not API_KEY:
    logger.critical("FATAL: NETGUARD_API_KEY env var not set.")
    sys.exit(1)

def get_headers():
    return {"X-API-Key": API_KEY}

def get_latest_metric(device_id, metric_type):
    try:
        r = requests.get(
            f"{API_URL}/monitoring/metrics/latest",
            params={"device_id": device_id, "metric_type": metric_type, "limit": 1},
            headers=get_headers(), timeout=10
        )
        if r.status_code == 200:
            data = r.json()
            if data:
                return float(data[0]['value'])
    except Exception as e:
        logger.error(f"Metric fetch failed ({metric_type}): {e}")
    return None

def get_open_alerts(device_id):
    """Fetch all open alerts for a device, return as list."""
    try:
        r = requests.get(
            f"{API_URL}/monitoring/alerts",
            params={"device_id": device_id, "status": "open"},
            headers=get_headers(), timeout=10
        )
        if r.status_code == 200:
            return r.json()
    except Exception as e:
        logger.error(f"Alert fetch failed: {e}")
    return []

def has_open_alert(open_alerts, rule_name):
    return any(a['rule_name'] == rule_name for a in open_alerts)

def find_open_alert_id(open_alerts, rule_name):
    for a in open_alerts:
        if a['rule_name'] == rule_name:
            return a['id']
    return None

def create_alert(device_id, rule_name, severity, message):
    try:
        r = requests.post(
            f"{API_URL}/monitoring/alerts",
            json={"device_id": device_id, "rule_name": rule_name, "severity": severity, "message": message},
            headers=get_headers(), timeout=10
        )
        if r.status_code in (200, 201):
            logger.warning(f"Alert created [{severity.upper()}] {rule_name}: {message}")
        else:
            logger.error(f"Failed to create alert: {r.status_code} {r.text}")
    except Exception as e:
        logger.error(f"Alert create error: {e}")

def resolve_alert(alert_id, rule_name):
    try:
        requests.patch(
            f"{API_URL}/monitoring/alerts/{alert_id}",
            json={"status": "resolved", "resolution_summary": f"Auto-resolved: condition cleared"},
            headers=get_headers(), timeout=10
        )
        logger.info(f"Auto-resolved alert: {rule_name} ({alert_id})")
    except Exception as e:
        logger.error(f"Alert resolve error: {e}")

def analyze_metrics():
    try:
        resp = requests.get(f"{API_URL}/inventory/devices", headers=get_headers(), timeout=10)
        resp.raise_for_status()
        devices = resp.json()
    except Exception as e:
        logger.error(f"Failed to fetch devices: {e}")
        return

    for device in devices:
        device_id = device['id']
        name = device['name']
        open_alerts = get_open_alerts(device_id)

        # --- AUTO-RESOLVE PASS ---
        uptime = get_latest_metric(device_id, 'uptime_status')
        if uptime == 1.0:
            alert_id = find_open_alert_id(open_alerts, 'Device Offline')
            if alert_id:
                resolve_alert(alert_id, 'Device Offline')
                open_alerts = [a for a in open_alerts if a['id'] != alert_id]

        wg_age = get_latest_metric(device_id, 'wg_handshake_age')
        if wg_age is not None and wg_age < WG_ONLINE_THRESHOLD:
            alert_id = find_open_alert_id(open_alerts, 'WireGuard Peer Offline')
            if alert_id:
                resolve_alert(alert_id, 'WireGuard Peer Offline')
                open_alerts = [a for a in open_alerts if a['id'] != alert_id]

        # --- OFFLINE CHECK ---
        try:
            if uptime == 0.0:
                if not has_open_alert(open_alerts, 'Device Offline'):
                    create_alert(device_id, 'Device Offline', 'critical',
                                 f"Device {name} is not responding to ping.")
                continue  # skip other checks if offline
        except Exception as e:
            logger.error(f"Offline check error for {name}: {e}")

        # --- CPU CHECK ---
        try:
            cpu = get_latest_metric(device_id, 'cpu_usage')
            if cpu is not None and cpu > CPU_THRESHOLD:
                if not has_open_alert(open_alerts, 'High CPU'):
                    create_alert(device_id, 'High CPU', 'critical',
                                 f"High CPU usage detected on {name}: {cpu:.1f}%")
        except Exception as e:
            logger.error(f"CPU check error for {name}: {e}")

        # --- MEMORY CHECK ---
        try:
            mem = get_latest_metric(device_id, 'memory_usage')
            if mem is not None and mem > MEMORY_THRESHOLD:
                if not has_open_alert(open_alerts, 'High Memory Usage'):
                    create_alert(device_id, 'High Memory Usage', 'warning',
                                 f"High memory usage on {name}: {mem:.1f}%")
        except Exception as e:
            logger.error(f"Memory check error for {name}: {e}")

        # --- HOTSPOT CAPACITY CHECK ---
        try:
            hs_users = get_latest_metric(device_id, 'hotspot_users')
            if hs_users is not None and hs_users > HOTSPOT_USER_THRESHOLD:
                if not has_open_alert(open_alerts, 'Hotspot Capacity'):
                    create_alert(device_id, 'Hotspot Capacity', 'warning',
                                 f"Hotspot near capacity on {name}: {int(hs_users)} active sessions")
        except Exception as e:
            logger.error(f"Hotspot check error for {name}: {e}")

        # --- WIREGUARD PEER DOWN CHECK ---
        try:
            if wg_age is not None and wg_age > WG_OFFLINE_THRESHOLD:
                if not has_open_alert(open_alerts, 'WireGuard Peer Offline'):
                    create_alert(device_id, 'WireGuard Peer Offline', 'critical',
                                 f"WireGuard peer {name} last handshake {int(wg_age)}s ago (threshold: {WG_OFFLINE_THRESHOLD}s)")
        except Exception as e:
            logger.error(f"WireGuard check error for {name}: {e}")

        # --- CLIENT DROP CHECK ---
        try:
            clients = get_latest_metric(device_id, 'connected_clients')
            if clients is not None and clients == 0 and uptime == 1.0:
                if not has_open_alert(open_alerts, 'Client Drop Detected'):
                    create_alert(device_id, 'Client Drop Detected', 'warning',
                                 f"All DHCP clients disappeared on {name} while device is online")
        except Exception as e:
            logger.error(f"Client drop check error for {name}: {e}")

def run_agent():
    logger.info("Starting Enhanced Diagnoser Agent...")
    while True:
        analyze_metrics()
        logger.info("Diagnosis cycle complete.")
        time.sleep(30)

if __name__ == "__main__":
    run_agent()
