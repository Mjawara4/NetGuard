"""Tests for GET /hotspot/jobs/{job_id} and POST /hotspot/jobs/{job_id}/progress.

These are Task 4 of the background-voucher-generation feature: the two
endpoints that let agents/voucher_job_worker.py (Task 3) report progress on a
voucher batch and let the operator's browser poll it. Task 2's
batch_generate_users creates the VoucherBatch row up front with
status="queued" and vouchers=[]; the worker then calls the progress endpoint
roughly every 10 vouchers plus a final call, and the frontend polls the GET
endpoint to render a progress bar.

Two things this file guards especially closely:

1. Append-only progress. The worker's report_progress sends only the NEW
   vouchers since its last successful call (not the cumulative list) -- see
   its docstring in agents/voucher_job_worker.py. If the endpoint replaced
   VoucherBatch.vouchers wholesale instead of extending it, every batch above
   ~10 vouchers would end up with only its last partial flush of vouchers
   persisted, silently discarding the rest -- vouchers that already exist on
   the router and are meant to be printable.

2. Cache invalidation on terminal status only. Task 2 removed the "users"
   cache invalidation from the batch-create endpoint because it no longer
   touches real vouchers; nothing replaced it until this task. Without it,
   vouchers the worker just created would not show up in the operator's
   voucher list, reprint history, or dashboard count for up to 30 minutes
   (the monitor agent's refresh interval) -- a defect that already bit once.
   So invalidate+request_refresh must fire when status becomes "complete" or
   "failed" (real vouchers exist on the router either way), and must NOT
   fire on an intermediate "running" call, which would otherwise force a
   ~3.6 MB router refetch every ~10 vouchers.

3. Dedup by username on append (fix round 1). The append is a
   read-modify-write with no lock: if this endpoint commits but the worker
   never sees the ack (its 10s client timeout exists for exactly this), the
   worker's pending buffer still believes those vouchers are unsent and
   resends them. Since VoucherBatch.vouchers is what the operator prints, a
   naive extend would store (and let print) two slips with identical
   credentials -- a real support/refund problem. Usernames are unique by
   construction, so a username already present in the stored array means
   that exact voucher was already recorded and must be skipped, while
   genuinely new vouchers in the same call must still be kept.
"""

import copy
import time
import uuid
from unittest.mock import AsyncMock, MagicMock

import fakeredis
import pytest
from fastapi import HTTPException

from app.models import APIKey, User, UserRole, VoucherBatch
from app.routers import hotspot
from app.services import hotspot_cache


def _voucher_batch(device_id=None, organization_id=None, status="queued", vouchers=None, count=10):
    return VoucherBatch(
        id=uuid.uuid4(),
        device_id=device_id or uuid.uuid4(),
        organization_id=organization_id or uuid.uuid4(),
        batch_name="Batch-test",
        prefix="test",
        profile="default",
        time_limit=None,
        data_limit=None,
        count=count,
        vouchers=vouchers if vouchers is not None else [],
        status=status,
    )


def _db_returning(row):
    result = MagicMock()
    result.scalars.return_value.first.return_value = row
    db = MagicMock()
    db.execute = AsyncMock(return_value=result)
    db.add = MagicMock()
    db.commit = AsyncMock()
    db.rollback = AsyncMock()
    return db


def _unscoped_actor():
    # organization_id=None takes the `isinstance(actor, APIKey) and not
    # actor.organization_id` unscoped branch -- this is the actor shape the
    # worker itself authenticates as (agents/voucher_job_worker.py uses the
    # same NETGUARD_API_KEY every other agent uses against /inventory/devices,
    # which is likewise unscoped).
    return APIKey(organization_id=None)


def _scoped_actor(organization_id):
    return APIKey(organization_id=organization_id)


@pytest.fixture(autouse=True)
def fake_redis(monkeypatch):
    fake = fakeredis.FakeRedis(decode_responses=True)
    monkeypatch.setattr(hotspot_cache, "_client", lambda: fake)
    return fake


def _seed_users_cache(fake_redis, device_id, rows):
    import json
    fake_redis.set(
        hotspot_cache.cache_key(str(device_id), "users"),
        json.dumps({"fetched_at": time.time(), "rows": rows}),
    )


# ---------------------------------------------------------------------------
# GET /hotspot/jobs/{job_id}
# ---------------------------------------------------------------------------

async def test_get_job_queued_batch_returns_zero_created(fake_redis):
    batch = _voucher_batch(status="queued", vouchers=[], count=25)

    result = await hotspot.get_voucher_job(
        str(batch.id), db=_db_returning(batch), actor=_unscoped_actor()
    )

    assert result["job_id"] == str(batch.id)
    assert result["status"] == "queued"
    assert result["count"] == 25
    assert result["created"] == 0
    assert result["vouchers"] == []


async def test_get_job_partially_complete_returns_correct_created_and_vouchers(fake_redis):
    vouchers = [{"username": "v1", "password": "v1"}, {"username": "v2", "password": "v2"}]
    batch = _voucher_batch(status="running", vouchers=vouchers, count=25)

    result = await hotspot.get_voucher_job(
        str(batch.id), db=_db_returning(batch), actor=_unscoped_actor()
    )

    assert result["status"] == "running"
    assert result["created"] == 2
    assert result["vouchers"] == vouchers


async def test_get_job_unknown_id_returns_404(fake_redis):
    with pytest.raises(HTTPException) as exc_info:
        await hotspot.get_voucher_job(
            str(uuid.uuid4()), db=_db_returning(None), actor=_unscoped_actor()
        )

    assert exc_info.value.status_code == 404


async def test_get_job_other_organization_not_readable(fake_redis):
    """A scoped actor whose organization doesn't own the batch must get 404,
    not the batch's data. In production, VoucherBatch.organization_id ==
    actor.organization_id is part of the SQL WHERE clause for a scoped actor
    (mirroring the isinstance(actor, APIKey) and not actor.organization_id
    branch other hotspot endpoints use), so that query returns no row for a
    mismatched org -- exactly what _db_returning(None) simulates here.
    """
    with pytest.raises(HTTPException) as exc_info:
        await hotspot.get_voucher_job(
            str(uuid.uuid4()),
            db=_db_returning(None),
            actor=_scoped_actor(uuid.uuid4()),
        )

    assert exc_info.value.status_code == 404


async def test_get_job_super_admin_not_org_scoped(fake_redis):
    """A super admin User (no organization_id at all) must still be able to
    read any batch -- mirrors the isinstance(actor, User) and
    actor.role == UserRole.SUPER_ADMIN branch other hotspot endpoints use."""
    batch = _voucher_batch(status="complete", vouchers=[{"username": "v1", "password": "v1"}])
    admin = User(role=UserRole.SUPER_ADMIN, organization_id=None)

    result = await hotspot.get_voucher_job(str(batch.id), db=_db_returning(batch), actor=admin)

    assert result["status"] == "complete"
    assert result["created"] == 1


# ---------------------------------------------------------------------------
# POST /hotspot/jobs/{job_id}/progress
# ---------------------------------------------------------------------------

async def test_progress_appends_cumulatively_across_two_calls(fake_redis):
    """The append-only guarantee: two progress calls with disjoint new
    vouchers must leave both persisted, not just the second call's batch.
    This is the regression test for a wholesale-replace bug that would
    silently discard everything before the worker's last ~10-voucher flush.
    """
    batch = _voucher_batch(status="queued", vouchers=[])
    db = _db_returning(batch)

    first_vouchers = [{"username": "v1", "password": "v1"}, {"username": "v2", "password": "v2"}]
    result1 = await hotspot.report_voucher_job_progress(
        str(batch.id),
        hotspot.VoucherJobProgress(vouchers=first_vouchers, status="running"),
        db=db,
        actor=_unscoped_actor(),
    )
    assert result1["created"] == 2
    assert batch.vouchers == first_vouchers

    second_vouchers = [{"username": "v3", "password": "v3"}]
    result2 = await hotspot.report_voucher_job_progress(
        str(batch.id),
        hotspot.VoucherJobProgress(vouchers=second_vouchers, status="running"),
        db=db,
        actor=_unscoped_actor(),
    )

    # Cumulative, not replaced: all three vouchers must be present.
    assert result2["created"] == 3
    assert batch.vouchers == first_vouchers + second_vouchers


async def test_progress_retried_call_does_not_lose_prior_vouchers(fake_redis):
    """A retried call (same shape the worker would resend after a failed
    POST) must not wipe out vouchers a previous, successful call already
    persisted -- it only ever adds on top."""
    batch = _voucher_batch(status="running", vouchers=[{"username": "existing", "password": "existing"}])
    db = _db_returning(batch)

    result = await hotspot.report_voucher_job_progress(
        str(batch.id),
        hotspot.VoucherJobProgress(vouchers=[{"username": "new", "password": "new"}], status="running"),
        db=db,
        actor=_unscoped_actor(),
    )

    assert result["created"] == 2
    assert {"username": "existing", "password": "existing"} in batch.vouchers
    assert {"username": "new", "password": "new"} in batch.vouchers


async def test_progress_overlapping_call_dedups_by_username(fake_redis):
    """The read-modify-write-with-no-lock case: if this endpoint commits an
    append but the worker never sees the ack (its 10s client timeout exists
    for exactly this), the worker resends the same still-pending vouchers on
    its next flush. The second call here carries one voucher already
    persisted by the first ("v2") plus one genuinely new one ("v3") -- each
    username must appear exactly once in the stored array afterward, with
    the non-overlapping ones (v1, v2, v3) all still present.
    """
    batch = _voucher_batch(status="running", vouchers=[])
    db = _db_returning(batch)

    first_vouchers = [{"username": "v1", "password": "v1"}, {"username": "v2", "password": "v2"}]
    await hotspot.report_voucher_job_progress(
        str(batch.id),
        hotspot.VoucherJobProgress(vouchers=first_vouchers, status="running"),
        db=db,
        actor=_unscoped_actor(),
    )

    overlapping_vouchers = [{"username": "v2", "password": "v2"}, {"username": "v3", "password": "v3"}]
    result = await hotspot.report_voucher_job_progress(
        str(batch.id),
        hotspot.VoucherJobProgress(vouchers=overlapping_vouchers, status="running"),
        db=db,
        actor=_unscoped_actor(),
    )

    usernames = [v["username"] for v in batch.vouchers]
    assert sorted(usernames) == ["v1", "v2", "v3"]
    assert len(usernames) == len(set(usernames))
    assert result["created"] == 3


async def test_progress_fully_duplicate_replay_is_a_noop(fake_redis):
    """An exact resend of a call that already committed -- the worst case of
    the lost-ack scenario -- must leave the stored array completely
    unchanged, not just deduped-per-username-but-still-growing."""
    batch = _voucher_batch(status="running", vouchers=[])
    db = _db_returning(batch)

    vouchers = [{"username": "v1", "password": "v1"}, {"username": "v2", "password": "v2"}]
    await hotspot.report_voucher_job_progress(
        str(batch.id),
        hotspot.VoucherJobProgress(vouchers=vouchers, status="running"),
        db=db,
        actor=_unscoped_actor(),
    )
    stored_after_first_call = copy.deepcopy(batch.vouchers)

    result = await hotspot.report_voucher_job_progress(
        str(batch.id),
        hotspot.VoucherJobProgress(vouchers=vouchers, status="running"),
        db=db,
        actor=_unscoped_actor(),
    )

    assert batch.vouchers == stored_after_first_call
    assert result["created"] == 2


async def test_progress_status_complete_marks_batch_complete(fake_redis):
    batch = _voucher_batch(status="running", vouchers=[])
    db = _db_returning(batch)

    result = await hotspot.report_voucher_job_progress(
        str(batch.id),
        hotspot.VoucherJobProgress(vouchers=[{"username": "v1", "password": "v1"}], status="complete"),
        db=db,
        actor=_unscoped_actor(),
    )

    assert result["status"] == "complete"
    assert batch.status == "complete"


async def test_progress_unknown_job_id_returns_404(fake_redis):
    with pytest.raises(HTTPException) as exc_info:
        await hotspot.report_voucher_job_progress(
            str(uuid.uuid4()),
            hotspot.VoucherJobProgress(vouchers=[], status="running"),
            db=_db_returning(None),
            actor=_unscoped_actor(),
        )

    assert exc_info.value.status_code == 404


# ---------------------------------------------------------------------------
# Cache invalidation -- the gap this task closes.
# ---------------------------------------------------------------------------

async def test_progress_complete_invalidates_users_cache_and_requests_refresh(fake_redis, monkeypatch):
    device_id = uuid.uuid4()
    batch = _voucher_batch(device_id=device_id, status="running", vouchers=[])
    db = _db_returning(batch)
    _seed_users_cache(fake_redis, device_id, [{"name": "old-voucher"}])

    triggered = []
    monkeypatch.setattr(
        hotspot_cache, "request_refresh", lambda device_id=None: triggered.append(device_id)
    )

    await hotspot.report_voucher_job_progress(
        str(batch.id),
        hotspot.VoucherJobProgress(vouchers=[{"username": "v1", "password": "v1"}], status="complete"),
        db=db,
        actor=_unscoped_actor(),
    )

    # "users" cache key deleted...
    assert fake_redis.get(hotspot_cache.cache_key(str(device_id), "users")) is None
    # ...and the monitor agent nudged to repopulate sooner than its 1800s interval.
    assert triggered == [str(device_id)]


async def test_progress_failed_invalidates_users_cache_and_requests_refresh(fake_redis, monkeypatch):
    """"failed" also means real vouchers exist on the router (whatever was
    created before the failure), so it must invalidate exactly like
    "complete" does."""
    device_id = uuid.uuid4()
    batch = _voucher_batch(device_id=device_id, status="running", vouchers=[])
    db = _db_returning(batch)
    _seed_users_cache(fake_redis, device_id, [{"name": "old-voucher"}])

    triggered = []
    monkeypatch.setattr(
        hotspot_cache, "request_refresh", lambda device_id=None: triggered.append(device_id)
    )

    await hotspot.report_voucher_job_progress(
        str(batch.id),
        hotspot.VoucherJobProgress(vouchers=[{"username": "v1", "password": "v1"}], status="failed"),
        db=db,
        actor=_unscoped_actor(),
    )

    assert fake_redis.get(hotspot_cache.cache_key(str(device_id), "users")) is None
    assert triggered == [str(device_id)]


async def test_progress_intermediate_running_does_not_invalidate_cache(fake_redis, monkeypatch):
    """The other half of the regression test: an intermediate "running" call
    (the worker's every-~10-vouchers flush) must NOT invalidate, or a
    500-voucher job would force a ~3.6 MB router refetch ~50 times over,
    repeatedly blocking the monitor agent's metric loop.
    """
    device_id = uuid.uuid4()
    batch = _voucher_batch(device_id=device_id, status="queued", vouchers=[])
    db = _db_returning(batch)
    _seed_users_cache(fake_redis, device_id, [{"name": "still-here"}])

    triggered = []
    monkeypatch.setattr(
        hotspot_cache, "request_refresh", lambda device_id=None: triggered.append(device_id)
    )

    await hotspot.report_voucher_job_progress(
        str(batch.id),
        hotspot.VoucherJobProgress(vouchers=[{"username": "v1", "password": "v1"}], status="running"),
        db=db,
        actor=_unscoped_actor(),
    )

    # Cache untouched...
    assert fake_redis.get(hotspot_cache.cache_key(str(device_id), "users")) is not None
    # ...and the agent not nudged either.
    assert triggered == []


async def test_progress_other_organization_not_writable(fake_redis):
    """Mirrors the GET authorization test: a scoped actor whose organization
    doesn't own the batch must not be able to report progress on it either.
    """
    with pytest.raises(HTTPException) as exc_info:
        await hotspot.report_voucher_job_progress(
            str(uuid.uuid4()),
            hotspot.VoucherJobProgress(vouchers=[{"username": "v1", "password": "v1"}], status="complete"),
            db=_db_returning(None),
            actor=_scoped_actor(uuid.uuid4()),
        )

    assert exc_info.value.status_code == 404
