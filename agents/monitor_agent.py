import time
import requests
import psutil
import platform
import subprocess
import os
import json
from datetime import datetime
import logging
import sys
import redis
import routeros_api

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)],
    force=True
)
logger = logging.getLogger("monitor-agent")

# Configuration
API_URL = os.getenv("API_URL", "http://backend:8000/api/v1")
API_KEY = os.getenv("NETGUARD_API_KEY")
REDIS_HOST = os.getenv("REDIS_HOST", "redis")

# Default Credentials
SSH_USER = os.getenv("SSH_USER", "admin")
SSH_PASSWORD = os.getenv("SSH_PASSWORD", "")

if not API_KEY:
    logger.critical("FATAL: NETGUARD_API_KEY env var not set.")
    sys.exit(1)

def get_headers():
    return {"X-API-Key": API_KEY}

def ping_host(host):
    """
    Pings a host and returns (latency_ms, status).
    Status: 1.0 (Online), 0.0 (Offline)
    Latency: float (ms) or None if offline
    """
    try:
        # Linux/Mac ping
        cmd = ["ping", "-c", "3", "-W", "5", host]
        output = subprocess.check_output(cmd, stderr=subprocess.STDOUT, universal_newlines=True)
        
        if "time=" in output:
            conn_time = output.split("time=")[1].split(" ")[0]
            return float(conn_time), 1.0
        else:
            return None, 0.0
            
    except subprocess.CalledProcessError:
        return None, 0.0
    except Exception as e:
        logger.error(f"Ping error for {host}: {e}")
        return None, 0.0

def report_metric(device_id, metric_type, value, unit=None, meta_data=None):
    payload = {
        "device_id": device_id,
        "metric_type": metric_type,
        "value": float(value),
        "unit": unit,
        "meta_data": meta_data,
        "time": datetime.utcnow().isoformat()
    }
    try:
        resp = requests.post(f"{API_URL}/monitoring/metrics", json=payload, headers=get_headers())
        if resp.status_code >= 400:
             logger.error(f"Failed to report metric {metric_type}: {resp.text}")
    except Exception as e:
        logger.error(f"Failed to report metric: {e}")

def get_mikrotik_stats(device_ip, username, password, port=8728):
    """
    Connects to MikroTik Router via API and fetches resources.
    Returns a dict of metrics.
    """
    metrics = []
    
    try:
        connection = routeros_api.RouterOsApiPool(
            device_ip, 
            username=username, 
            password=password,
            port=port,
            plaintext_login=True,
            use_ssl=False
        )
        api = connection.get_api()
        
        # 1. System Resources
        resource = api.get_resource('/system/resource')
        res_data = resource.get()
        if res_data:
            data = res_data[0]
            # CPU
            if 'cpu-load' in data:
                metrics.append(('cpu_usage', float(data['cpu-load']), '%', None))
            # Memory
            if 'free-memory' in data and 'total-memory' in data:
                free = int(data['free-memory'])
                total = int(data['total-memory'])
                used_interaction = ((total - free) / total) * 100
                metrics.append(('memory_usage', used_interaction, '%', {'total': total, 'free': free}))
            # Uptime
            if 'uptime' in data:
                # Uptime comes as string like "1d04:30:22" of "4h30m"
                # For now, just pass 1.0 as heartbeat, store string in meta
                metrics.append(('uptime_status', 1.0, 'status', {'uptime_str': data['uptime']}))
                
        # 2. Connected Devices (DHCP Leases)
        leases_res = api.get_resource('/ip/dhcp-server/lease')
        leases = leases_res.get()
        active_leases = [l for l in leases if l.get('status') == 'bound']
        
        device_list = []
        for l in active_leases:
            device_list.append({
                'ip': l.get('address'),
                'mac': l.get('mac-address'),
                'hostname': l.get('host-name', 'Unknown')
            })
            
        metrics.append(('connected_clients', len(active_leases), 'count', {'clients': device_list}))

        # 3. Hotspot - Active Users & Traffic (NEW)
        try:
             hotspot_active = api.get_resource('/ip/hotspot/active')
             active_users = hotspot_active.get()
             
             metrics.append(('hotspot_users', len(active_users), 'count', None))
             
             users_detail = []
             total_bytes_in = 0
             total_bytes_out = 0
             
             for u in active_users:
                 b_in = int(u.get('bytes-in', 0))
                 b_out = int(u.get('bytes-out', 0))
                 total_bytes_in += b_in
                 total_bytes_out += b_out
                 
                 users_detail.append({
                     'user': u.get('user'),
                     'ip': u.get('address'),
                     'mac': u.get('mac-address'),
                     'bytes_in': b_in,
                     'bytes_out': b_out,
                     'uptime': u.get('uptime')
                 })
                 
             # Report total traffic for now roughly
             # Storing the detailed breakdown in metadata for "Seeing what they are doing"
             total_traffic_mb = (total_bytes_in + total_bytes_out) / (1024 * 1024)
             metrics.append(('hotspot_traffic', total_traffic_mb, 'MB', {'users': users_detail}))
             
        except Exception as e_hotspot:
             logger.error(f"Failed to fetch hotspot stats: {e_hotspot}")

        connection.disconnect()
        return metrics

    except Exception as e:
        logger.error(f"MikroTik Connection Failed for {device_ip}: {e}")
        return []

def wait_for_trigger(seconds):
    try:
        r = redis.Redis(host=REDIS_HOST, port=6379, db=0)
        p = r.pubsub()
        p.subscribe('agent_trigger:monitor')
        msg = p.get_message(timeout=seconds)
        if msg and msg['type'] == 'message':
             logger.info("Manual Trigger Received! Skipping sleep.")
             return
    except Exception:
        time.sleep(seconds)

def run_agent():
    logger.info("Starting Monitor Agent with MikroTik Support")
    
    while True:
        try:
            # Fetch devices
            resp = requests.get(f"{API_URL}/inventory/devices", headers=get_headers())
            
            if resp.status_code == 200:
                devices = resp.json()
                logger.info(f"Monitoring {len(devices)} devices...")

                for device in devices:
                    ip = device.get('ip_address')
                    dev_id = device['id']
                    
                    if not ip:
                        continue

                    # 1. Basic Ping
                    latency, status = ping_host(ip)
                    report_metric(dev_id, "status", status)
                    if status == 1.0: 
                        logger.info(f"Ping {ip}: Success ({latency}ms)")
                        report_metric(dev_id, "latency", latency, "ms")
                    else:
                        logger.warning(f"Ping {ip}: Unreachable")
                        
                    # 2. Deep Inspection (MikroTik)
                    # If status is Online, try to fetch specific router stats
                    if status == 1.0:
                        # Determine credentials
                        user = device.get('ssh_username') or SSH_USER
                        # Use device specific password if exists, else global
                        pwd = device.get('ssh_password') or SSH_PASSWORD 
                        db_port = int(device.get('ssh_port', 8728))
                        # Heuristic: If port is 22 (SSH), use 8728 (API) for RouterOS API connections
                        port = 8728 if db_port == 22 else db_port
                        
                        logger.info(f"Attempting MikroTik login for {ip} with user {user} on port {port}")
                        mt_metrics = get_mikrotik_stats(ip, user, pwd, port)
                        
                        for m_type, m_val, m_unit, m_meta in mt_metrics:
                            report_metric(dev_id, m_type, m_val, m_unit, m_meta)
                            logger.info(f"Reported {m_type} for {ip}: {m_val}")

            else:
                logger.error(f"Failed to fetch devices: {resp.status_code}")

        except Exception as e:
            logger.exception(f"Monitor loop error: {e}")
            
        wait_for_trigger(5)

if __name__ == "__main__":
    run_agent()
