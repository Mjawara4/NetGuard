"""Redis-list queue for background voucher generation jobs.

The worker (agents/voucher_job_worker.py) consumes QUEUE_KEY with BRPOP, so the
key name and the payload keys are a contract across two containers with no
shared module. Change them in both places or not at all.

Job payload keys (all eleven, no more, no fewer):
    batch_id, device_id, qty, prefix, profile, time_limit, data_limit,
    comment, length, random_mode, format

`length`, `random_mode` and `format` are not optional extras -- they select
which of the three naming shapes `generate_candidate` below produces (see its
docstring). Dropping them silently changes what code a voucher batch gets
without telling the operator, so route them straight from the validated
`BatchUserCreate` request model rather than re-defaulting them at the call
site: two independently-drifting default sets is exactly how they'd get
dropped again.

This module also holds the voucher-naming and collision-retry logic that used
to live inline in `batch_generate_users` (app/routers/hotspot.py). It is
extracted here purely for the backend's own testability -- the backend no
longer executes it itself, because generation now happens in the worker
container, which cannot import this module (separate image, separate
requirements.txt, no shared package). `agents/voucher_job_worker.py` carries
a parallel implementation which MUST stay format-compatible with the
functions below.

The voucher code format is a durable contract: existing printed vouchers
follow it and support staff recognise it on sight. Do not change the naming
scheme here, and do not let the worker's copy drift from it.
"""

import json
import logging
import os
import random
import string

import redis

logger = logging.getLogger(__name__)

REDIS_HOST = os.getenv("REDIS_HOST", "redis")
QUEUE_KEY = "hotspot:voucher_jobs"

_shared_client = None


def _client():
    global _shared_client
    if _shared_client is None:
        _shared_client = redis.Redis(host=REDIS_HOST, port=6379, db=0, decode_responses=True)
    return _shared_client


def enqueue(job):
    """LPUSH a job. Returns False on Redis failure; never raises.

    The batch row is committed before this is called, so a failed enqueue
    leaves a durable `queued` row the operator can see and retry -- far better
    than losing the request.
    """
    try:
        _client().lpush(QUEUE_KEY, json.dumps(job))
        return True
    except Exception as e:
        logger.error(f"Failed to enqueue voucher job {job.get('batch_id')}: {e}")
        return False


# ---------------------------------------------------------------------------
# Voucher naming / collision-retry reference implementation
#
# Moved verbatim (not rewritten) from the old inline loop in
# batch_generate_users. Pure function: no FastAPI request context, no DB
# access, no network I/O -- given a (prefix, qty, ...) shape it produces
# candidate (username, password) pairs the same way the original loop did.
# Collision detection itself still requires a live round trip to the router
# (a name already exists there), so that check cannot be part of a pure
# function; what this preserves is the *shape* of the retry allowance
# (qty * 3 attempts) and the exact naming rules, for the worker to mirror.
# ---------------------------------------------------------------------------

COLLISION_ATTEMPTS_MULTIPLIER = 3


def max_collision_attempts(qty):
    """The same allowance the original inline loop used: qty * 3 attempts to
    absorb "already exists" collisions from the router."""
    return qty * COLLISION_ATTEMPTS_MULTIPLIER


def generate_candidate(prefix, length=None, random_mode=False, fmt="alphanumeric"):
    """Generate a single (username, password) candidate pair.

    Mirrors the original inline logic exactly:
    - random_mode + format="numeric": an all-digit username, password == username.
    - random_mode + format="alphanumeric" (default): username is `length`
      characters split between lowercase letters and digits, password == username.
    - not random_mode: username is `prefix` + a numeric suffix (default 4
      digits), password is a separate random 4-digit code.
    """
    if random_mode:
        if fmt == "numeric":
            # numeric mode with variable length
            n = length if length else 8
            username = ''.join(random.choices(string.digits, k=n))
            password = username
        else:
            # alphanumeric mode: split length between letters and numbers
            # default length 8 if not specified
            n = length if length else 8
            num_len = n // 2
            char_len = n - num_len

            letters = ''.join(random.choices(string.ascii_lowercase, k=char_len))
            numbers = ''.join(random.choices(string.digits, k=num_len))
            username = f"{letters}{numbers}"
            password = username  # Same as username
    else:
        suffix_len = length if length else 4
        suffix = ''.join(random.choices(string.digits, k=suffix_len))
        username = f"{prefix}{suffix}"
        password = ''.join(random.choices(string.digits, k=4))  # Simple 4 digit password

    return username, password


def generate_candidates(qty, prefix, length=None, random_mode=False, fmt="alphanumeric"):
    """Generate `max_collision_attempts(qty)` candidate (username, password)
    pairs -- the pure, over-provisioned list a caller can walk through,
    creating each on the router in turn and skipping the ones that collide,
    stopping once `qty` have been created (or the list is exhausted).

    This does not check for collisions itself (that needs the router); it
    only reproduces the original loop's naming and its qty*3 attempt budget.
    """
    return [
        generate_candidate(prefix, length=length, random_mode=random_mode, fmt=fmt)
        for _ in range(max_collision_attempts(qty))
    ]
