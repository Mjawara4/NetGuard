"""Redis cache writer for raw hotspot router payloads.

The monitor agent already fetches most of these datasets to derive metrics; it
writes the raw rows here so the backend can serve hotspot reads without making
its own router round trips (~187 ms each over the VPN).

Rows are stored exactly as RouterOS returned them. The backend owns the
transformation into response schemas, so this module must not reshape anything.
"""

import json
import logging
import os
import time

import redis

logger = logging.getLogger(__name__)

REDIS_HOST = os.getenv("REDIS_HOST", "redis")

# TTLs are ~30x each dataset's refresh interval, so a key never expires between
# refreshes. Expiry therefore means "the writer stopped", not "data is stale" —
# staleness is judged from fetched_at, never from key absence.
TTLS = {
    "active": 120,      # refreshed every ~4s with the metric poll
    "system": 120,      # refreshed every ~4s with the metric poll
    "users": 86400,     # invalidation-driven, with a 10 min safety refresh
    "profiles": 86400,  # invalidation-driven, with a 10 min safety refresh
    "log": 900,         # refreshed every ~30s
}

_shared_client = None


def _client():
    global _shared_client
    if _shared_client is None:
        _shared_client = redis.Redis(host=REDIS_HOST, port=6379, db=0, decode_responses=True)
    return _shared_client


def cache_key(device_id, dataset):
    return f"hotspot:{device_id}:raw:{dataset}"


def write_dataset(device_id, dataset, rows):
    """Store raw router rows for one dataset. Returns False on Redis failure.

    Never raises on a Redis problem: a cache write failure must not break the
    metric collection this agent exists to do.
    """
    if dataset not in TTLS:
        raise ValueError(f"unknown dataset {dataset!r}; expected one of {sorted(TTLS)}")

    try:
        payload = json.dumps({"fetched_at": time.time(), "rows": rows})
        _client().setex(cache_key(device_id, dataset), TTLS[dataset], payload)
        return True
    except Exception as e:
        logger.warning(f"Hotspot cache write failed for {device_id}/{dataset}: {e}")
        return False
