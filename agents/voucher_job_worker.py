"""Background worker that consumes hotspot voucher-generation jobs and
creates the vouchers on the router.

Task 2 (backend `POST /{device_id}/users/batch`) commits a `VoucherBatch` row
with status="queued" and LPUSHes a job dict onto the Redis list
`hotspot:voucher_jobs` (see `backend/app/services/voucher_jobs.enqueue`).
This module is the consumer: it BRPOPs that list forever, and for each job
connects to the target router over `routeros_api` and creates vouchers one
at a time, mirroring the collision-retry loop that used to run inline in the
backend request handler before Task 2 moved it out (commit f669e6d).

NAMING CONTRACT -- READ THIS BEFORE TOUCHING generate_candidate/generate_usernames:
`backend/app/services/voucher_jobs.py` (`generate_candidate`,
`generate_candidates`, `max_collision_attempts`) is the reference
implementation for voucher naming. This module cannot import it -- agents/
and backend/ are separate Docker images with separate requirements.txt and no
shared package -- so `generate_candidate` below is a parallel implementation
that MUST stay format-compatible with the backend's. The voucher code format
is a durable contract: vouchers already printed follow it, and support staff
recognise the shape on sight. Do not rewrite it from memory and do not
"improve" it -- mirror the backend file exactly, including the alphanumeric
random path's num_len/char_len split and the non-random path's separate
4-digit password. If the backend file changes, update this one to match, in
the same commit.
"""

import json
import logging
import os
import random
import string
import sys
import time

import redis
import requests
import routeros_api

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)],
    force=True,
)
logger = logging.getLogger("voucher-job-worker")

# Configuration -- same names/defaults as agents/monitor_agent.py, since this
# worker fetches devices from the same backend API using the same shared
# secret and the same ssh_username/ssh_password fallback.
API_URL = os.getenv("API_URL", "http://backend:8000/api/v1")
API_KEY = os.getenv("NETGUARD_API_KEY")
REDIS_HOST = os.getenv("REDIS_HOST", "redis")
SSH_USER = os.getenv("SSH_USER", "admin")
SSH_PASSWORD = os.getenv("SSH_PASSWORD", "")

if not API_KEY:
    logger.critical("FATAL: NETGUARD_API_KEY env var not set.")
    sys.exit(1)

# Must match backend/app/services/voucher_jobs.QUEUE_KEY exactly -- this is a
# contract across two containers with no shared module.
QUEUE_KEY = "hotspot:voucher_jobs"

# Roughly every 10 vouchers plus a final call, so a 500-voucher job makes
# ~50 progress calls rather than 500 (see report_progress / process_job).
PROGRESS_BATCH_SIZE = 10

_shared_client = None


def _client():
    global _shared_client
    if _shared_client is None:
        _shared_client = redis.Redis(host=REDIS_HOST, port=6379, db=0, decode_responses=True)
    return _shared_client


def get_headers():
    return {"X-API-Key": API_KEY}



# BRPOP's own `timeout` blocks the loop between jobs, but a Redis connection
# error raises immediately instead of blocking -- without this, an outage
# turns run_worker's `while True: claim_job(...)` into a tight busy-spin that
# burns a full core hammering a Redis that is already down. This is not
# retried/backed-off like the terminal progress report (that is a single
# job's completion signal with a natural bound); this is an infinite loop's
# error path, so a short flat sleep here is what actually matters.
REDIS_ERROR_SLEEP_SECONDS = 2


def claim_job(timeout=5):
    """BRPOP one job off QUEUE_KEY and return the decoded dict.

    Returns None both when the queue is empty (BRPOP timed out) and on any
    Redis error -- the worker must survive a Redis outage and keep retrying
    on the next loop iteration rather than crash. A malformed payload (should
    never happen, since only this codebase's own enqueue() writes to this
    key) is treated the same way: logged and dropped, not raised.
    """
    try:
        result = _client().brpop(QUEUE_KEY, timeout=timeout)
    except Exception as e:
        logger.error(f"Redis error while claiming a voucher job: {e}")
        time.sleep(REDIS_ERROR_SLEEP_SECONDS)
        return None

    if result is None:
        return None

    _, raw = result
    try:
        return json.loads(raw)
    except (TypeError, ValueError) as e:
        logger.error(f"Malformed voucher job payload, dropping: {e}")
        return None


def fetch_device(device_id):
    """Fetch one device's connection details from the backend inventory API.

    Deliberately reuses the exact pattern agents/monitor_agent.py (and
    fix_agent.py, diagnoser_agent.py, wg_agent.py) already use in production:
    GET the full device list from `{API_URL}/inventory/devices` with
    `get_headers()`, then look up by id -- there is no per-device inventory
    endpoint call in any existing agent, so this does not invent a new path.
    Returns the device dict (plain JSON, not a model -- callers use
    `.get(...)`), or None if the device is not found or the request failed.
    """
    try:
        resp = requests.get(f"{API_URL}/inventory/devices", headers=get_headers(), timeout=10)
        resp.raise_for_status()
    except requests.exceptions.RequestException as e:
        logger.error(f"Failed to fetch devices: {e}")
        return None

    for device in resp.json():
        if device.get("id") == device_id:
            return device
    return None


def report_progress(batch_id, vouchers, status):
    """POST incremental progress for a voucher batch to the backend.

    `vouchers` is only the NEW vouchers since the last successful call (not
    the cumulative list), so a 500-voucher job sends ~50 small calls instead
    of 500, or one call with an ever-growing payload. The endpoint itself
    (`POST /hotspot/jobs/{batch_id}/progress`) is added in Task 4, which
    lands after this worker -- until then every call here 404s in a real
    deployment. That is expected and is not this task's job to fix: this
    function logs the failure and returns False rather than raising, so the
    job's own retry/collision logic keeps working (and is unit-testable
    today) independent of that endpoint existing.

    Returns True on a successful POST, False otherwise. Callers should only
    drop already-sent vouchers from their own pending buffer when this
    returns True, so a transient failure does not silently discard vouchers
    that exist on the router -- they stay pending and go out on the next
    flush (or the final one).
    """
    try:
        resp = requests.post(
            f"{API_URL}/hotspot/jobs/{batch_id}/progress",
            json={"vouchers": vouchers, "status": status},
            headers=get_headers(),
            timeout=10,
        )
        resp.raise_for_status()
        return True
    except requests.exceptions.RequestException as e:
        logger.error(f"Failed to report progress for batch {batch_id} (status={status}): {e}")
        return False


# Delays (seconds) between successive attempts at the TERMINAL report only
# (see report_terminal_progress below) -- 5 attempts total, with these 4 gaps
# summing to 30s. A backend restart is observed to take ~10-30s, so an outage
# that started right before the terminal call is expected to have recovered
# by the 4th or 5th attempt. Intermediate ("running") progress calls made
# from _create_vouchers are NOT retried this way: they get another chance for
# free at the next ~10-voucher flush (or this same terminal call, since any
# unflushed vouchers are still sitting in `pending`), so retrying them here
# too would just be redundant backoff stacked on top of that natural retry.
TERMINAL_REPORT_BACKOFF_SECONDS = [2, 4, 8, 16]


def report_terminal_progress(batch_id, vouchers, status):
    """Report a job's TERMINAL status ("complete" or "failed"), retrying a
    failed POST with backoff instead of firing once and giving up.

    Why this one call gets special treatment: it is the only progress report
    that can never be "made up" later -- there is no next flush after this.
    If it never lands, the VoucherBatch row is stuck at a non-terminal status
    forever (feeding the frontend's C1 stuck-job problem) AND `vouchers`
    (the entire accumulated-but-unflushed `pending` buffer, potentially
    hundreds of real, router-created vouchers) never reaches the database --
    invisible in History and unprintable, which is the exact bug this whole
    feature exists to eliminate. A brief backend restart during a deploy is
    the realistic trigger: it takes ~10-30s, comfortably inside this
    function's ~30s of cumulative backoff.

    Bounded, not infinite: after the attempts below are exhausted this logs
    at ERROR with the job_id and how many vouchers are stranded, so an
    operator or a log search (e.g. by job_id) can find and manually recover
    them, then gives up and returns False. Callers must not block forever on
    this -- the worker still has to move on to its next job.
    """
    max_attempts = len(TERMINAL_REPORT_BACKOFF_SECONDS) + 1
    for attempt in range(1, max_attempts + 1):
        if report_progress(batch_id, vouchers, status):
            return True
        if attempt < max_attempts:
            delay = TERMINAL_REPORT_BACKOFF_SECONDS[attempt - 1]
            logger.warning(
                f"Terminal progress report for batch {batch_id} (status={status}) "
                f"failed on attempt {attempt}/{max_attempts}; retrying in {delay}s"
            )
            time.sleep(delay)

    logger.error(
        f"Voucher job {batch_id} terminal report (status={status}) failed after "
        f"{max_attempts} attempts. {len(vouchers)} voucher(s) exist on the router "
        f"but were NOT recorded in VoucherBatch -- they will not appear in History "
        f"and cannot be printed until manually recovered. job_id={batch_id}"
    )
    return False


# ---------------------------------------------------------------------------
# Voucher naming / collision-retry -- parallel implementation of
# backend/app/services/voucher_jobs.py. See the module docstring above.
# Keep this section byte-for-byte equivalent in behavior to that file.
# ---------------------------------------------------------------------------

COLLISION_ATTEMPTS_MULTIPLIER = 3


def max_collision_attempts(qty):
    """The same allowance the original inline loop used: qty * 3 attempts to
    absorb "already exists" collisions from the router. Mirrors
    backend/app/services/voucher_jobs.max_collision_attempts."""
    return qty * COLLISION_ATTEMPTS_MULTIPLIER


def generate_candidate(prefix, length=None, random_mode=False, fmt="alphanumeric"):
    """Generate a single (username, password) candidate pair.

    Mirrors backend/app/services/voucher_jobs.generate_candidate exactly:
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


def generate_usernames(prefix, qty):
    """Return `qty` unique, `prefix`-prefixed usernames.

    Uses the same non-random naming shape as generate_candidate (prefix + a
    4-digit numeric suffix), generating candidates until `qty` unique names
    are collected or `max_collision_attempts(qty)` attempts are exhausted --
    this local call has no router to check against, so "collision" here
    means "already produced in this same call". In the vanishingly unlikely
    case the attempt budget runs out first (only plausible for qty close to
    or above 10**length), a deterministic fallback fills the remainder so
    this always returns exactly `qty` unique names.
    """
    names = set()
    attempts = 0
    budget = max_collision_attempts(qty)
    while len(names) < qty and attempts < budget:
        attempts += 1
        username, _ = generate_candidate(prefix, random_mode=False)
        names.add(username)

    counter = 0
    while len(names) < qty:
        names.add(f"{prefix}X{counter}")
        counter += 1

    return list(names)


def _create_vouchers(resource, job):
    """Create up to job['qty'] vouchers on an already-connected router
    resource, mirroring the original inline collision-retry loop (moved to
    backend/app/services/voucher_jobs.py in Task 2, commit f669e6d) exactly:
    one candidate at a time, `resource.add(**params)`, and on any exception
    from the router -- not just "already exists" -- log (unless it looks
    like a name collision) and try the next candidate, up to qty*3 attempts
    total.

    Returns the list of {"username", "password"} dicts actually created (may
    be shorter than qty if the attempt budget ran out first, same as the
    original synchronous behavior).
    """
    qty = job["qty"]
    prefix = job["prefix"]
    profile = job["profile"]
    time_limit = job.get("time_limit")
    data_limit = job.get("data_limit")
    comment = job.get("comment")
    length = job.get("length")
    random_mode = job.get("random_mode")
    fmt = job.get("format")

    batch_id = job.get("batch_id")
    generated = []
    pending = []
    attempts = 0
    max_attempts = max_collision_attempts(qty)

    while len(generated) < qty and attempts < max_attempts:
        attempts += 1
        username, password = generate_candidate(prefix, length=length, random_mode=random_mode, fmt=fmt)

        params = {
            'name': username,
            'password': password,
            'profile': profile,
            'comment': comment,
        }
        if time_limit:
            params['limit-uptime'] = time_limit
        if data_limit:
            params['limit-bytes-total'] = data_limit

        try:
            resource.add(**params)
        except Exception as e:
            # Likely "user already exists" -- try the next candidate. Any
            # other router error is logged but also retried, exactly like
            # the original inline loop did: this loop's job is only to
            # absorb naming collisions within its qty*3 budget, not to
            # distinguish error types.
            if "already exists" not in str(e).lower():
                logger.warning(f"Voucher create error for batch {batch_id} (attempt {attempts}/{max_attempts}): {e}")
            continue

        voucher = {"username": username, "password": password}
        generated.append(voucher)
        pending.append(voucher)

        if len(pending) >= PROGRESS_BATCH_SIZE:
            if report_progress(batch_id, pending, "running"):
                pending = []
            # else: keep accumulating and retry on the next flush point (or
            # the final call in process_job) rather than dropping them --
            # those vouchers already exist on the router.

    logger.info(f"Batch {batch_id} generation loop done: {len(generated)}/{qty} created in {attempts} attempts")
    return generated, pending


def process_job(job):
    """Handle one claimed voucher job end-to-end: mark it running, connect to
    its device's router, create vouchers, and report completion or failure.

    Failure semantics: anything that stops this job before or outside the
    per-voucher retry loop above (device not found, router connection
    failure) is a genuine "the router errored" condition, so the batch is
    marked "failed" -- with whatever vouchers were already created and
    reported as pending, since those vouchers exist on the router and must
    stay printable. A per-voucher naming collision (handled inside
    _create_vouchers) never reaches this far; the job still ends "complete"
    even if fewer than qty vouchers were created before the attempt budget
    ran out, matching the original synchronous endpoint's behavior.
    """
    batch_id = job["batch_id"]
    pending = []

    report_progress(batch_id, [], "running")

    try:
        device = fetch_device(job["device_id"])
        if not device:
            raise RuntimeError(f"Device {job['device_id']} not found")

        ip = device.get("ip_address")
        ssh_username = device.get("ssh_username") or SSH_USER
        ssh_password = device.get("ssh_password") or SSH_PASSWORD
        # Same form as agents/monitor_agent.py's identical computation (its
        # deep-inspect block, ~line 584) -- two agents reading the exact same
        # `ssh_port` field must not diverge on how they turn it into a
        # connection port.
        db_port = int(device.get("ssh_port", 8728))
        port = 8728 if db_port == 22 else db_port

        pool = routeros_api.RouterOsApiPool(
            ip,
            username=ssh_username,
            password=ssh_password,
            port=port,
            plaintext_login=True,
            use_ssl=False,
        )
        try:
            api = pool.get_api()
            resource = api.get_resource('/ip/hotspot/user')
            generated, pending = _create_vouchers(resource, job)
        finally:
            try:
                pool.disconnect()
            except Exception:
                pass

        report_terminal_progress(batch_id, pending, "complete")

    except Exception as e:
        logger.error(f"Voucher job {batch_id} failed: {e}", exc_info=True)
        report_terminal_progress(batch_id, pending, "failed")


def run_worker():
    logger.info("Starting Voucher Job Worker")
    while True:
        job = claim_job(timeout=5)
        if job is None:
            continue
        try:
            process_job(job)
        except Exception as e:
            # Last-resort net: process_job already handles its own failure
            # reporting, so reaching here means a bug in process_job itself.
            # Never let that kill the loop -- log and go back to waiting.
            logger.error(f"Unhandled error processing voucher job {job.get('batch_id')}: {e}", exc_info=True)


if __name__ == "__main__":
    run_worker()
