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
import hotspot_cache

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

def get_mikrotik_stats(device_ip, username, password, port=8728, device_id=None, last_refreshed=None):
    """
    Connects to MikroTik Router via API and fetches resources.
    Returns a list of metric dicts.
    """
    metrics = []

    try:
        api = get_api_connection(device_ip, username, password, port)
        metrics.append({
            "metric_type": "api_reachable",
            "value": 1.0,
            "unit": "status",
            "meta_data": None
        })

        # 1. System Resources
        resource = api.get_resource('/system/resource')
        res_data = resource.get()
        if device_id and res_data:
            hotspot_cache.write_dataset(device_id, "system", res_data)
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
            if device_id:
                hotspot_cache.write_dataset(device_id, "active", active_users)

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

        # 4. Interface stats (rx/tx bytes)
        try:
            iface_res = api.get_resource('/interface')
            interfaces = iface_res.get()
            for iface in interfaces:
                if iface.get('running') == 'true':
                    iname = iface.get('name', 'unknown')
                    rx = int(iface.get('rx-byte', 0))
                    tx = int(iface.get('tx-byte', 0))
                    metrics.append({
                        "metric_type": "interface_rx_bytes",
                        "value": float(rx),
                        "unit": "bytes",
                        "meta_data": {"interface": iname}
                    })
                    metrics.append({
                        "metric_type": "interface_tx_bytes",
                        "value": float(tx),
                        "unit": "bytes",
                        "meta_data": {"interface": iname}
                    })
        except Exception as e_iface:
            logger.error(f"Interface stats failed: {e_iface}")

        # Datasets the hotspot UI reads but this agent does not need for metrics.
        # Each has its own interval so they do not add a round trip to every poll.
        if device_id is not None and last_refreshed is not None:
            for dataset, path in (
                ("users", '/ip/hotspot/user'),
                ("profiles", '/ip/hotspot/user/profile'),
                ("log", '/log'),
            ):
                interval = DATASET_INTERVALS[dataset]
                # One dataset failing must not abort the metric collection
                # that the rest of this function performed successfully;
                # maybe_refresh_dataset only logs on failure.
                maybe_refresh_dataset(api, device_id, dataset, path, interval, last_refreshed, device_ip=device_ip)

        return metrics

    except Exception as e:
        logger.error(f"MikroTik Connection Failed for {device_ip}: {e}")
        evict_api_connection(device_ip, port)
        metrics.append({
            "metric_type": "api_reachable",
            "value": 0.0,
            "unit": "status",
            "meta_data": None
        })
        return metrics

def wait_for_trigger(seconds):
    """Block for up to `seconds`, or return early if a message arrives on the
    'agent_trigger:monitor' pubsub channel.

    Returns True if a trigger was received -- the caller should force its next
    deep-inspect pass to bypass DEEP_INSPECT_INTERVAL, since a trigger means
    the backend just invalidated a cache key and wants it repopulated now, not
    up to 30s from now. Returns False otherwise, including on a Redis error
    (where this just falls back to a plain sleep, as before).
    """
    try:
        r = redis.Redis(host=REDIS_HOST, port=6379, db=0)
        p = r.pubsub()
        p.subscribe('agent_trigger:monitor')
        msg = p.get_message(timeout=seconds)
        if msg and msg['type'] == 'message':
            logger.info("Manual Trigger Received! Forcing deep inspect next pass.")
            return True
        return False
    except Exception:
        time.sleep(seconds)
        return False


def deep_inspect_due(last_deep, now, interval, force=False):
    """True if a device is due for a deep inspect: by interval, or forced.

    `force` is how a received pubsub trigger (see wait_for_trigger) bypasses
    DEEP_INSPECT_INTERVAL for one pass.
    """
    return force or (now - last_deep) >= interval


# Per-dataset refresh intervals in seconds. Datasets that only change when an
# operator acts (users, profiles) are invalidated on write by the backend
# (which also publishes agent_trigger:monitor, see request_refresh in
# backend/app/services/hotspot_cache.py); the interval here is just a safety
# net for router-side changes such as auto-expiry, and for a missed/failed
# invalidation.
#
# `users` is deliberately the longest interval, not an oversight to align with
# `profiles`: it is 11k+ rows / several MB on a real router, and the poll loop
# is sequential, so fetching it blocks the rest of that pass's metric
# collection (gated by DEEP_INSPECT_INTERVAL, default ~30s) every time it
# runs. 1800s keeps that gap rare. `profiles` and `log` stay short because
# they are small (KB-scale) and cheap to fetch every time they are due.
DATASET_INTERVALS = {
    "users": 1800,
    "profiles": 600,
    "log": 30,
}


def should_refresh(last_refreshed, device_id, dataset, interval, now=None):
    """True if `dataset` for `device_id` is due for a refresh, by wall-clock
    interval alone.

    Pure: never mutates `last_refreshed`. This is only the time-based half of
    the refresh decision -- callers combine it with hotspot_cache.exists(...)
    (a dataset is also due if its cache key is simply missing, e.g. after
    invalidation or a Redis flush) and must call record_refreshed(...)
    themselves once the refresh actually succeeds. See maybe_refresh_dataset,
    which wires all of this together for the caller.
    """
    if now is None:
        now = time.time()
    previous = last_refreshed.get((device_id, dataset))
    return previous is None or now - previous >= interval


def record_refreshed(last_refreshed, device_id, dataset, now=None):
    """Record that `dataset` for `device_id` was just successfully refreshed.

    Callers must only call this after both the fetch and the cache write
    succeeded -- recording on a failed attempt is exactly the bug (C2) this
    split from should_refresh exists to prevent: it would silently consume a
    whole interval's worth of retries on a single timeout.
    """
    if now is None:
        now = time.time()
    last_refreshed[(device_id, dataset)] = now


def maybe_refresh_dataset(api, device_id, dataset, path, interval, last_refreshed, device_ip=None, now=None):
    """Fetch and cache one hotspot dataset if it is due, then record success.

    "Due" is: due by interval (should_refresh), OR the cache key is simply
    absent (hotspot_cache.exists returns False -- covers invalidation, a
    Redis flush, or eviction; see C1/C3). The timestamp in `last_refreshed` is
    only recorded when BOTH the router fetch and the cache write succeed, so
    a failed attempt (timeout, Redis error) leaves the slot open for an
    immediate retry on the next pass instead of burning the whole interval
    (C2). Returns True if a refresh was attempted and succeeded, False
    otherwise (not due, fetch failed, or cache write failed).

    No separate failure backoff is added here: this function is only called
    from inside a per-device deep inspect that is itself already gated to
    happen at most once per DEEP_INSPECT_INTERVAL (~30s) per device, which is
    backoff enough for a persistently failing dataset. A forced pass (a
    received pubsub trigger) can shorten that gap, but wait_for_trigger only
    ever consumes one queued message per call, so a burst of writes collapses
    to at most one extra forced pass, not a spin.
    """
    due = should_refresh(last_refreshed, device_id, dataset, interval, now=now) or not hotspot_cache.exists(device_id, dataset)
    if not due:
        return False

    try:
        rows = api.get_resource(path).get()
    except Exception as e_ds:
        logger.warning(f"Failed to fetch {dataset} for {device_ip or device_id}: {e_ds}")
        return False

    if not hotspot_cache.write_dataset(device_id, dataset, rows):
        logger.warning(f"Failed to cache write {dataset} for {device_ip or device_id}; will retry next pass")
        return False

    record_refreshed(last_refreshed, device_id, dataset, now=now)
    logger.info(f"Cached {dataset} for {device_ip or device_id}: {len(rows)} rows")
    return True


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
    dataset_last_refreshed = {}
    # Set by wait_for_trigger's return value; forces the *next* pass's deep
    # inspect to bypass DEEP_INSPECT_INTERVAL (see C1 Part B). Consumed once
    # per pass -- it is reassigned from wait_for_trigger at the bottom of
    # every iteration (and on the early-continue path below), so it never
    # lingers past the one pass it was meant for.
    force_deep_inspect = False

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
                force_deep_inspect = wait_for_trigger(5)
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

                    # 2. Deep Inspection (MikroTik) — throttle to DEEP_INSPECT_INTERVAL,
                    # unless a pubsub trigger forces this pass through early.
                    if status == 1.0:
                        last_deep = device_last_polled.get(dev_id, 0)
                        if deep_inspect_due(last_deep, now, DEEP_INSPECT_INTERVAL, force=force_deep_inspect):
                            device_last_polled[dev_id] = now

                            user = device.get('ssh_username') or SSH_USER
                            pwd = device.get('ssh_password') or SSH_PASSWORD
                            db_port = int(device.get('ssh_port', 8728))
                            port = 8728 if db_port == 22 else db_port

                            logger.info(f"Deep inspect {ip} (user={user}, port={port})")
                            mt_metrics = get_mikrotik_stats(ip, user, pwd, port, device_id=dev_id, last_refreshed=dataset_last_refreshed)

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

        force_deep_inspect = wait_for_trigger(5)

if __name__ == "__main__":
    try:
        run_agent()
    finally:
        disconnect_all()
