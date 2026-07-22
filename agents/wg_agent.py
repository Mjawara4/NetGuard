import os
import time
import subprocess
import requests
import logging
import sys
from log_utils import post_agent_log

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)],
    force=True
)
logger = logging.getLogger("wg-agent")

API_URL = os.getenv("API_URL", "http://backend:8000/api/v1")
API_KEY = os.getenv("NETGUARD_API_KEY")
WG_CHECK_INTERVAL = int(os.getenv("WG_CHECK_INTERVAL", "30"))
# Consecutive failures before declaring a peer offline
WG_FAIL_THRESHOLD = int(os.getenv("WG_FAIL_THRESHOLD", "3"))
WG_ONLINE_THRESHOLD = int(os.getenv("WG_ONLINE_THRESHOLD", "1"))  # successes to auto-resolve

if not API_KEY:
    logger.critical("FATAL: NETGUARD_API_KEY env var not set.")
    sys.exit(1)

# Track consecutive failure/success counts per device_id
_fail_counts = {}
_success_counts = {}

def get_headers():
    return {"X-API-Key": API_KEY}

def ping_host(host, count=3):
    """Ping host, return (latency_ms or None, status 1.0/0.0)."""
    try:
        output = subprocess.check_output(
            ["ping", "-c", str(count), "-W", "3", host],
            stderr=subprocess.STDOUT, universal_newlines=True
        )
        if "time=" in output:
            for line in output.splitlines():
                if "avg" in line and "rtt" in line:
                    parts = line.split("=")
                    if len(parts) == 2:
                        vals = parts[1].strip().split("/")
                        if len(vals) >= 2:
                            return float(vals[1]), 1.0
            val = output.split("time=")[1].split(" ")[0]
            return float(val), 1.0
        return None, 0.0
    except subprocess.CalledProcessError:
        return None, 0.0
    except Exception as e:
        logger.error(f"Ping error for {host}: {e}")
        return None, 0.0

def get_devices():
    try:
        r = requests.get(f"{API_URL}/inventory/devices", headers=get_headers(), timeout=10)
        if r.status_code == 200:
            return r.json()
    except Exception as e:
        logger.error(f"Failed to fetch devices: {e}")
    return []

def report_metric(device_id, value, unit="status", metric_type="wg_reachable"):
    try:
        requests.post(
            f"{API_URL}/monitoring/metrics",
            json={"device_id": device_id, "metric_type": metric_type,
                  "value": float(value), "unit": unit},
            headers=get_headers(), timeout=10
        )
    except Exception as e:
        logger.error(f"Failed to report metric: {e}")

def get_open_wg_alert(device_id):
    try:
        r = requests.get(
            f"{API_URL}/monitoring/alerts",
            params={"device_id": device_id, "status": "open"},
            headers=get_headers(), timeout=10
        )
        if r.status_code == 200:
            return next((a for a in r.json() if a['rule_name'] == 'WireGuard Peer Offline'), None)
    except Exception:
        pass
    return None

def create_alert(device_id, name):
    try:
        requests.post(
            f"{API_URL}/monitoring/alerts",
            json={"device_id": device_id, "rule_name": "WireGuard Peer Offline",
                  "severity": "critical",
                  "message": f"WireGuard peer {name} unreachable via VPN tunnel"},
            headers=get_headers(), timeout=10
        )
        logger.warning(f"Alert created: WireGuard Peer Offline for {name}")
    except Exception as e:
        logger.error(f"Alert create error: {e}")

def resolve_alert(alert_id, name):
    try:
        requests.patch(
            f"{API_URL}/monitoring/alerts/{alert_id}",
            json={"status": "resolved", "resolution_summary": f"WireGuard peer {name} is reachable again"},
            headers=get_headers(), timeout=10
        )
        logger.info(f"Resolved WireGuard alert for {name}")
    except Exception as e:
        logger.error(f"Alert resolve error: {e}")

def run_agent():
    logger.info(f"Starting WireGuard Agent (ping-based, fail_threshold={WG_FAIL_THRESHOLD})")
    post_agent_log("wg-agent", "INFO", "WireGuard Agent started (ping-based peer monitoring)")

    while True:
        try:
            devices = get_devices()
            wg_devices = [d for d in devices if d.get('wg_ip_address')]

            if not wg_devices:
                logger.debug("No devices with wg_ip_address configured")
                time.sleep(WG_CHECK_INTERVAL)
                continue

            for device in wg_devices:
                device_id = device['id']
                name = device['name']
                wg_ip = device['wg_ip_address']

                _, status = ping_host(wg_ip)
                report_metric(device_id, status)

                if status == 1.0:
                    _fail_counts[device_id] = 0
                    _success_counts[device_id] = _success_counts.get(device_id, 0) + 1
                    logger.info(f"WG peer {name} ({wg_ip}): reachable")

                    if _success_counts[device_id] >= WG_ONLINE_THRESHOLD:
                        alert = get_open_wg_alert(device_id)
                        if alert:
                            resolve_alert(alert['id'], name)
                            _success_counts[device_id] = 0
                else:
                    _success_counts[device_id] = 0
                    _fail_counts[device_id] = _fail_counts.get(device_id, 0) + 1
                    fails = _fail_counts[device_id]
                    logger.warning(f"WG peer {name} ({wg_ip}): unreachable (consecutive fails: {fails})")

                    if fails >= WG_FAIL_THRESHOLD:
                        alert = get_open_wg_alert(device_id)
                        if not alert:
                            create_alert(device_id, name)
                        _fail_counts[device_id] = 0

        except Exception as e:
            logger.exception(f"WG agent loop error: {e}")

        time.sleep(WG_CHECK_INTERVAL)

if __name__ == "__main__":
    run_agent()
