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

# Pubsub channel the monitor agent listens on (agents/monitor_agent.py's
# wait_for_trigger). Publishing here makes a received trigger force the
# agent's next pass to perform a deep inspect immediately, bypassing its
# DEEP_INSPECT_INTERVAL throttle -- see request_refresh below.
TRIGGER_CHANNEL = "agent_trigger:monitor"

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


def request_refresh(device_id=None):
    """Ask the monitor agent to refresh sooner than its normal cadence.

    Publishes to TRIGGER_CHANNEL, which wait_for_trigger in
    agents/monitor_agent.py listens on; a received message forces that
    agent's next pass to perform a deep inspect right away instead of
    waiting up to DEEP_INSPECT_INTERVAL (default 30s). Call this right after
    invalidate(...) so the window between an operator's write and the cache
    repopulating is a second or two instead of up to 30 minutes (C1).

    `device_id` is informational only (the agent triggers one full pass
    across all devices, not a single one) -- passed through in the message
    body in case a future agent version wants to target one device.

    Never raises: a failure to publish must not break the write endpoint
    that just succeeded against the router. The dataset still gets picked up
    by the agent's own interval/exists-check safety net (see should_refresh
    and hotspot_cache.exists in the agent), just later.
    """
    try:
        _client().publish(TRIGGER_CHANNEL, str(device_id) if device_id else "")
    except Exception as e:
        logger.warning(f"Hotspot cache refresh trigger publish failed: {e}")


def age_seconds(fetched_at):
    if fetched_at is None:
        return None
    return max(0.0, time.time() - float(fetched_at))
