"""Read raw hotspot router payloads that the monitor agent caches in Redis.

THE RULE this module exists to enforce: hotspot read endpoints never call the
router. Each router round trip costs ~187 ms over the VPN, and the page fires
nine of them. A cache miss here returns empty data with no fetched_at, and the
caller reports that as "updating" — it must never fall back to the router.
"""

import json
import logging
import os
import time

import redis

logger = logging.getLogger(__name__)

REDIS_HOST = os.getenv("REDIS_HOST", "redis")

DATASETS = ("active", "users", "profiles", "system", "log")

_shared_client = None


def _client():
    global _shared_client
    if _shared_client is None:
        _shared_client = redis.Redis(host=REDIS_HOST, port=6379, db=0, decode_responses=True)
    return _shared_client


def cache_key(device_id, dataset):
    return f"hotspot:{device_id}:raw:{dataset}"


def read_dataset(device_id, dataset):
    """Return (rows, fetched_at) for one dataset, or ([], None) if unavailable."""
    try:
        raw = _client().get(cache_key(device_id, dataset))
    except Exception as e:
        logger.warning(f"Hotspot cache read failed for {device_id}/{dataset}: {e}")
        return [], None

    if not raw:
        return [], None

    try:
        payload = json.loads(raw)
        return payload.get("rows", []), payload.get("fetched_at")
    except (ValueError, AttributeError) as e:
        logger.warning(f"Hotspot cache payload unparseable for {device_id}/{dataset}: {e}")
        return [], None


def invalidate(device_id, *datasets):
    """Delete cached datasets after a write, so the next refresh repopulates."""
    for dataset in datasets:
        try:
            _client().delete(cache_key(device_id, dataset))
        except Exception as e:
            logger.warning(f"Hotspot cache invalidate failed for {device_id}/{dataset}: {e}")


def age_seconds(fetched_at):
    if fetched_at is None:
        return None
    return max(0.0, time.time() - float(fetched_at))
