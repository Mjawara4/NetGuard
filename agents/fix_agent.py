import time
import requests
import os
import logging
import sys
import routeros_api
from datetime import datetime, timezone

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)],
    force=True
)
logger = logging.getLogger("fix-agent")

API_URL = os.getenv("API_URL", "http://backend:8000/api/v1")
API_KEY = os.getenv("NETGUARD_API_KEY")
SSH_USER = os.getenv("SSH_USER", "admin")
SSH_PASSWORD = os.getenv("SSH_PASSWORD", "admin")
VERIFY_WAIT_SECONDS = int(os.getenv("FIX_VERIFY_WAIT", "30"))
CPU_THRESHOLD = float(os.getenv("CPU_THRESHOLD", "80"))
HOTSPOT_KICK_THRESHOLD = int(os.getenv("HOTSPOT_KICK_THRESHOLD", "50"))

if not API_KEY:
    logger.critical("FATAL: NETGUARD_API_KEY env var not set.")
    sys.exit(1)

def get_headers():
    return {"X-API-Key": API_KEY}

def connect_routeros(ip, username, password, port=8728):
    """Open a plain RouterOS API connection and return the api object."""
    pool = routeros_api.RouterOsApiPool(
        ip,
        username=username,
        password=password,
        port=port,
        plaintext_login=True,
        use_ssl=False
    )
    return pool, pool.get_api()

def attempt_high_cpu_fix(device) -> tuple:
    """
    Attempt to reduce CPU on a MikroTik device via RouterOS API.
    Returns (success: bool, log: str)
    """
    ip = device.get('ip_address')
    user = device.get('ssh_username') or SSH_USER
    pwd = device.get('ssh_password') or SSH_PASSWORD
    port_raw = int(device.get('ssh_port', 8728))
    port = 8728 if port_raw == 22 else port_raw
    log_lines = []

    pool = None
    try:
        pool, api = connect_routeros(ip, user, pwd, port)
        log_lines.append(f"Connected to {ip}:{port}")

        # Step 1: re-check current CPU — might have self-resolved
        res = api.get_resource('/system/resource').get()
        if res:
            cpu_now = float(res[0].get('cpu-load', 100))
            log_lines.append(f"Current CPU: {cpu_now}%")
            if cpu_now < CPU_THRESHOLD:
                return True, f"CPU self-resolved ({cpu_now}%). " + "; ".join(log_lines)

        # Step 2: if hotspot has many active sessions, kick the heaviest one
        try:
            active_res = api.get_resource('/ip/hotspot/active')
            active_users = active_res.get()
            log_lines.append(f"Hotspot active sessions: {len(active_users)}")
            if len(active_users) > HOTSPOT_KICK_THRESHOLD:
                # Sort by bytes consumed descending and remove top user
                top = sorted(active_users, key=lambda u: int(u.get('bytes-in', 0)) + int(u.get('bytes-out', 0)), reverse=True)
                if top:
                    victim = top[0]
                    victim_id = victim.get('.id')
                    victim_user = victim.get('user', 'unknown')
                    active_res.remove(id=victim_id)
                    log_lines.append(f"Removed heaviest hotspot session: {victim_user} (id={victim_id})")
        except Exception as e_hs:
            log_lines.append(f"Hotspot kick skipped: {e_hs}")

        # Step 3: restart hotspot service to clear stuck sessions
        try:
            hs = api.get_resource('/ip/hotspot')
            hotspots = hs.get()
            if hotspots:
                hs_id = hotspots[0].get('.id')
                hs.set(id=hs_id, **{'disabled': 'yes'})
                time.sleep(2)
                hs.set(id=hs_id, **{'disabled': 'no'})
                log_lines.append("Restarted hotspot service")
        except Exception as e_restart:
            log_lines.append(f"Hotspot restart skipped: {e_restart}")

        return True, "; ".join(log_lines)

    except Exception as e:
        return False, f"RouterOS connection failed: {e}"
    finally:
        if pool:
            try:
                pool.disconnect()
            except Exception:
                pass

def get_latest_metric(device_id, metric_type) -> float | None:
    """Fetch the most recent value of a metric for a device."""
    try:
        resp = requests.get(
            f"{API_URL}/monitoring/metrics/latest",
            params={"device_id": device_id, "metric_type": metric_type, "limit": 1},
            headers=get_headers(),
            timeout=10
        )
        if resp.status_code == 200:
            data = resp.json()
            if data:
                return float(data[0]['value'])
    except Exception as e:
        logger.error(f"Failed to fetch metric {metric_type} for {device_id}: {e}")
    return None

def log_fix_action(alert_id, action_type, status, log_output):
    try:
        requests.post(
            f"{API_URL}/monitoring/alerts/{alert_id}/fix-actions",
            json={"action_type": action_type, "status": status, "log_output": log_output},
            headers=get_headers(),
            timeout=10
        )
    except Exception as e:
        logger.error(f"Failed to log fix action: {e}")

def update_alert(alert_id, status, resolution_summary=None):
    try:
        requests.patch(
            f"{API_URL}/monitoring/alerts/{alert_id}",
            json={"status": status, "resolution_summary": resolution_summary},
            headers=get_headers(),
            timeout=10
        )
    except Exception as e:
        logger.error(f"Failed to update alert {alert_id}: {e}")

def run_agent():
    logger.info("Starting Classic Fix Agent (RouterOS API mode)...")

    while True:
        try:
            resp = requests.get(
                f"{API_URL}/monitoring/alerts",
                params={"status": "open"},
                headers=get_headers(),
                timeout=10
            )
            if resp.status_code != 200:
                logger.error(f"Failed to fetch alerts: {resp.status_code}")
                time.sleep(10)
                continue

            alerts = [a for a in resp.json() if a['status'] == 'open' and a['severity'] == 'critical']

            if not alerts:
                time.sleep(10)
                continue

            # Fetch all devices once per cycle
            dev_resp = requests.get(f"{API_URL}/inventory/devices", headers=get_headers(), timeout=10)
            devices = {d['id']: d for d in (dev_resp.json() if dev_resp.status_code == 200 else [])}

            for alert in alerts:
                alert_id = alert['id']
                device = devices.get(alert['device_id'])

                if not device:
                    logger.warning(f"Device not found for alert {alert_id}")
                    continue

                if "High CPU" in alert.get('message', '') or alert.get('rule_name') == 'High CPU':
                    logger.info(f"Attempting High CPU fix on {device['name']} ({device['ip_address']})")
                    success, fix_log = attempt_high_cpu_fix(device)

                    log_fix_action(alert_id, "ROUTER_CPU_FIX", "success" if success else "failed", fix_log)
                    logger.info(f"Fix attempt: success={success} | {fix_log}")

                    if success:
                        # Wait for monitor agent to push a fresh metric then verify
                        logger.info(f"Waiting {VERIFY_WAIT_SECONDS}s to verify CPU improvement...")
                        time.sleep(VERIFY_WAIT_SECONDS)
                        cpu_after = get_latest_metric(alert['device_id'], 'cpu_usage')
                        if cpu_after is not None and cpu_after < CPU_THRESHOLD:
                            logger.info(f"CPU dropped to {cpu_after}% — marking alert auto_fixed")
                            update_alert(alert_id, "auto_fixed",
                                         f"CPU reduced to {cpu_after}% after RouterOS remediation. {fix_log}")
                        else:
                            current = f"{cpu_after}%" if cpu_after is not None else "unknown"
                            logger.warning(f"CPU still high ({current}) after fix — leaving alert open")
                            log_fix_action(alert_id, "VERIFY_FAILED", "failed",
                                           f"CPU still at {current} after remediation. Manual review needed.")
                    else:
                        logger.error(f"Fix failed: {fix_log}")

        except Exception as e:
            logger.exception(f"Fix loop error: {e}")

        time.sleep(10)

if __name__ == "__main__":
    run_agent()
