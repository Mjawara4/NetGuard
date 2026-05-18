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
from retry_utils import retry_with_backoff

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

# Deep-inspection throttle (seconds)
DEEP_INSPECT_INTERVAL = int(os.getenv("DEEP_INSPECT_INTERVAL", "30"))
# Connection cache TTL (seconds)
CONN_CACHE_TTL = int(os.getenv("CONN_CACHE_TTL", "60"))

if not API_KEY:
    logger.critical("FATAL: NETGUARD_API_KEY env var not set.")
    sys.exit(1)

_connection_cache = {}

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
            # Extract average from summary line to be more accurate
            # The output has lines like: rtt min/avg/max/mdev = 0.123/0.456/0.789/0.123 ms
            avg_latency = None
            for line in output.splitlines():
                if "avg" in line and "rtt" in line:
                    parts = line.split("=")
                    if len(parts) == 2:
                        vals = parts[1].strip().split("/")
                        if len(vals) >= 2:
                            avg_latency = float(vals[1])
                            break
            if avg_latency is None:
                # Fallback: grab first occurrence of time=
                conn_time = output.split("time=")[1].split(" ")[0]
                avg_latency = float(conn_time)
            return avg_latency, 1.0
        else:
            return None, 0.0

    except subprocess.CalledProcessError:
        return None, 0.0
    except Exception as e:
        logger.error(f"Ping error for {host}: {e}")
        return None, 0.0

def _cache_key(ip, port):
    return (ip, int(port))

def get_api_connection(device_ip, username, password, port=8728):
    """Get or create a cached RouterOS API connection."""
    key = _cache_key(device_ip, port)
    now = time.time()
    cached = _connection_cache.get(key)

    if cached:
        pool, api, last_used = cached
        if now - last_used < CONN_CACHE_TTL:
            try:
                # Lightweight health check: try to get a tiny resource
                # If this fails, connection is dead
                api.get_resource('/system/resource').get()
                _connection_cache[key] = (pool, api, now)
                logger.debug(f"Reusing cached connection to {device_ip}:{port}")
                return api
            except Exception:
                logger.warning(f"Cached connection to {device_ip}:{port} stale, reconnecting...")
                try:
                    pool.disconnect()
                except Exception:
                    pass
        else:
            # TTL expired
            try:
                pool.disconnect()
            except Exception:
                pass

    # Create new connection
    pool = routeros_api.RouterOsApiPool(
        device_ip,
        username=username,
        password=password,
        port=port,
        plaintext_login=True,
        use_ssl=False
    )
    api = pool.get_api()
    _connection_cache[key] = (pool, api, now)
    logger.info(f"New RouterOS API connection to {device_ip}:{port}")
    return api

def evict_api_connection(device_ip, port=8728):
    """Remove a cached connection, usually after an error."""
    key = _cache_key(device_ip, port)
    cached = _connection_cache.pop(key, None)
    if cached:
        pool, _, _ = cached
        try:
            pool.disconnect()
        except Exception:
            pass
        logger.info(f"Evicted connection to {device_ip}:{port}")

def disconnect_all():
    """Disconnect all cached connections."""
    for key, (pool, _, _) in list(_connection_cache.items()):
        try:
            pool.disconnect()
        except Exception:
            pass
    _connection_cache.clear()

@retry_with_backoff(max_retries=3, initial_delay=1.0)
def report_metrics_batch(metrics_list):
    """
    Send a batch of metrics in a single HTTP request.
    metrics_list: list of dicts matching MetricCreate schema.
    """
    if not metrics_list:
        return
    try:
        resp = requests.post(
            f"{API_URL}/monitoring/metrics/batch",
            json=metrics_list,
            headers=get_headers(),
            timeout=30
        )
        resp.raise_for_status()
        result = resp.json()
        logger.info(f"Batch report: created={result.get('created', 0)}, skipped={result.get('skipped', 0)}")
    except requests.exceptions.RequestException as e:
        logger.error(f"Failed to report batch metrics: {e}")
        raise

def get_mikrotik_stats(device_ip, username, password, port=8728):
    """
    Connects to MikroTik Router via API and fetches resources.
    Returns a list of metric dicts.
    """
    metrics = []

    try:
        api = get_api_connection(device_ip, username, password, port)

        # 1. System Resources
        resource = api.get_resource('/system/resource')
        res_data = resource.get()
        if res_data:
            data = res_data[0]
            # CPU
            if 'cpu-load' in data:
                metrics.append({
                    "metric_type": "cpu_usage",
                    "value": float(data['cpu-load']),
                    "unit": "%",
                    "meta_data": None
                })
            # Memory
            if 'free-memory' in data and 'total-memory' in data:
                free = int(data['free-memory'])
                total = int(data['total-memory'])
                used_pct = ((total - free) / total) * 100
                metrics.append({
                    "metric_type": "memory_usage",
                    "value": used_pct,
                    "unit": "%",
                    "meta_data": {"total": total, "free": free}
                })
            # Uptime
            if 'uptime' in data:
                metrics.append({
                    "metric_type": "uptime_status",
                    "value": 1.0,
                    "unit": "status",
                    "meta_data": {"uptime_str": data['uptime']}
                })

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

        metrics.append({
            "metric_type": "connected_clients",
            "value": len(active_leases),
            "unit": "count",
            "meta_data": {"clients": device_list}
        })

        # 3. Hotspot - Active Users & Traffic
        try:
            hotspot_active = api.get_resource('/ip/hotspot/active')
            active_users = hotspot_active.get()

            metrics.append({
                "metric_type": "hotspot_users",
                "value": len(active_users),
                "unit": "count",
                "meta_data": None
            })

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

            total_traffic_mb = (total_bytes_in + total_bytes_out) / (1024 * 1024)
            metrics.append({
                "metric_type": "hotspot_traffic",
                "value": total_traffic_mb,
                "unit": "MB",
                "meta_data": {"users": users_detail}
            })

        except Exception as e_hotspot:
            logger.error(f"Failed to fetch hotspot stats: {e_hotspot}")

        return metrics

    except Exception as e:
        logger.error(f"MikroTik Connection Failed for {device_ip}: {e}")
        evict_api_connection(device_ip, port)
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

def build_metric_payload(dev_id, metric_type, value, unit=None, meta_data=None):
    return {
        "device_id": dev_id,
        "metric_type": metric_type,
        "value": float(value),
        "unit": unit,
        "meta_data": meta_data,
        "time": datetime.utcnow().isoformat()
    }

def run_agent():
    logger.info("Starting Monitor Agent with MikroTik Support")
    device_last_polled = {}

    while True:
        try:
            # Fetch devices with retry and timeout
            try:
                resp = requests.get(
                    f"{API_URL}/inventory/devices",
                    headers=get_headers(),
                    timeout=10
                )
                resp.raise_for_status()
            except requests.exceptions.RequestException as e:
                logger.error(f"Failed to fetch devices: {e}")
                wait_for_trigger(5)
                continue

            if resp.status_code == 200:
                devices = resp.json()
                logger.info(f"Monitoring {len(devices)} devices...")

                for device in devices:
                    ip = device.get('ip_address')
                    dev_id = device['id']

                    if not ip:
                        continue

                    now = time.time()
                    batch = []

                    # 1. Basic Ping (always)
                    latency, status = ping_host(ip)
                    batch.append(build_metric_payload(dev_id, "status", status))
                    if status == 1.0:
                        logger.info(f"Ping {ip}: Success ({latency}ms)")
                        batch.append(build_metric_payload(dev_id, "latency", latency, "ms"))
                    else:
                        logger.warning(f"Ping {ip}: Unreachable")
                        # Device offline: reset deep-inspect timer so we inspect immediately when back
                        device_last_polled.pop(dev_id, None)

                    # 2. Deep Inspection (MikroTik) — throttle to DEEP_INSPECT_INTERVAL
                    if status == 1.0:
                        last_deep = device_last_polled.get(dev_id, 0)
                        if now - last_deep >= DEEP_INSPECT_INTERVAL:
                            device_last_polled[dev_id] = now

                            user = device.get('ssh_username') or SSH_USER
                            pwd = device.get('ssh_password') or SSH_PASSWORD
                            db_port = int(device.get('ssh_port', 8728))
                            port = 8728 if db_port == 22 else db_port

                            logger.info(f"Deep inspect {ip} (user={user}, port={port})")
                            mt_metrics = get_mikrotik_stats(ip, user, pwd, port)

                            for m in mt_metrics:
                                batch.append(build_metric_payload(
                                    dev_id,
                                    m["metric_type"],
                                    m["value"],
                                    m.get("unit"),
                                    m.get("meta_data")
                                ))
                                logger.info(f"Collected {m['metric_type']} for {ip}: {m['value']}")
                        else:
                            logger.debug(f"Skipping deep inspect for {ip} (last={int(now-last_deep)}s ago)")

                    # 3. Report all metrics for this device in one batch
                    if batch:
                        try:
                            report_metrics_batch(batch)
                        except Exception as e:
                            logger.error(f"Failed to report batch for {ip}: {e}")

            else:
                logger.error(f"Failed to fetch devices: {resp.status_code}")

        except Exception as e:
            logger.exception(f"Monitor loop error: {e}")

        wait_for_trigger(5)

if __name__ == "__main__":
    try:
        run_agent()
    finally:
        disconnect_all()
