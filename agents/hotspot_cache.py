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

# TTLs exist so a key doesn't expire between refreshes -- expiry means "the
# writer stopped", not "data is stale" (staleness is judged from fetched_at,
# never from key absence). The margin over each dataset's real refresh
# interval varies by dataset:
#   - "active"/"system" are rewritten on every deep-inspect pass, gated by
#     DEEP_INSPECT_INTERVAL (default 30s, see monitor_agent.py). Their 120s
#     TTL is only a ~4x margin, not the 30x this comment used to claim.
#   - "log" is on its own 30s DATASET_INTERVALS entry, so its 900s TTL is a
#     genuine ~30x margin.
#   - "users"/"profiles" are invalidation-driven (the backend deletes the key
#     on write; see request_refresh in backend/app/services/hotspot_cache.py)
#     with DATASET_INTERVALS-gated safety refreshes underneath (1800s / 600s).
#     Their 86400s TTL is a backstop against a stuck invalidation, not a
#     multiple of the refresh cadence.
TTLS = {
    "active": 120,      # refreshed every DEEP_INSPECT_INTERVAL (~30s)
    "system": 120,      # refreshed every DEEP_INSPECT_INTERVAL (~30s)
    "users": 86400,     # invalidation-driven, with a 30 min (1800s) safety refresh
    "profiles": 86400,  # invalidation-driven, with a 10 min (600s) safety refresh
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


def exists(device_id, dataset):
    """Whether `dataset`'s cache key is currently present in Redis.

    Used as the correctness floor for refresh decisions: a wall-clock
    interval alone cannot tell the difference between "not due yet" and "the
    key was deleted (backend invalidation, Redis flush, eviction)".

    Returns a TRI-STATE, deliberately not a plain bool:
      - True  -- key present (Redis answered).
      - False -- key definitively absent (Redis answered; it is genuinely
        gone).
      - None  -- unknown, because Redis raised.

    Do NOT collapse this back to a bool. A prior version returned False on a
    Redis error, identically to "key absent" -- which made a Redis outage
    indistinguishable from a routine cache miss. Callers (see
    maybe_refresh_dataset in monitor_agent.py) treat that as "the dataset is
    due", so during an outage every pass looked due, forcing the ~3.6 MB
    voucher-list fetch on every single deep-inspect pass instead of once per
    interval -- a 60x router-load amplification. If Redis cannot answer, we
    cannot know the key is missing, so assuming it is missing is exactly the
    wrong inference. Callers must force a refresh only on a confirmed False,
    and fall back to the wall-clock interval alone when this returns None.
    """
    try:
        return bool(_client().exists(cache_key(device_id, dataset)))
    except Exception as e:
        logger.warning(f"Hotspot cache exists check failed for {device_id}/{dataset}: {e}")
        return None
