import json

import fakeredis
import pytest

from app.services import voucher_jobs


@pytest.fixture
def fake_redis(monkeypatch):
    fake = fakeredis.FakeRedis(decode_responses=True)
    monkeypatch.setattr(voucher_jobs, "_client", lambda: fake)
    return fake


def test_enqueue_pushes_job_json(fake_redis):
    job = {"batch_id": "b1", "device_id": "d1", "qty": 5, "prefix": "TEST",
           "profile": "default", "time_limit": None, "data_limit": None,
           "comment": "Batch-TEST"}
    assert voucher_jobs.enqueue(job) is True

    raw = fake_redis.rpop(voucher_jobs.QUEUE_KEY)
    assert json.loads(raw) == job


def test_enqueue_returns_false_on_redis_error(monkeypatch):
    class Boom:
        def lpush(self, *a, **k):
            raise RuntimeError("redis down")

    monkeypatch.setattr(voucher_jobs, "_client", lambda: Boom())
    # Must not raise: the batch row is already committed by the time we enqueue,
    # so a Redis failure has to be reportable, not fatal.
    assert voucher_jobs.enqueue({"batch_id": "b1"}) is False


# ---------------------------------------------------------------------------
# Naming / collision-retry reference implementation
#
# Not required by Task 2's interface (only enqueue/QUEUE_KEY are consumed by
# the endpoint), but this module doubles as the reference the worker's
# equivalent must stay format-compatible with, so it gets its own coverage.
# ---------------------------------------------------------------------------

def test_max_collision_attempts_matches_original_qty_times_three():
    assert voucher_jobs.max_collision_attempts(10) == 30
    assert voucher_jobs.max_collision_attempts(1) == 3


def test_generate_candidate_non_random_uses_prefix_and_suffix():
    username, password = voucher_jobs.generate_candidate("PROMO", length=4, random_mode=False)
    assert username.startswith("PROMO")
    assert len(username) == len("PROMO") + 4
    assert username[len("PROMO"):].isdigit()
    assert password.isdigit()
    assert len(password) == 4


def test_generate_candidate_random_numeric_username_equals_password():
    username, password = voucher_jobs.generate_candidate(
        "", length=6, random_mode=True, fmt="numeric"
    )
    assert username.isdigit()
    assert len(username) == 6
    assert password == username


def test_generate_candidate_random_alphanumeric_splits_length():
    username, password = voucher_jobs.generate_candidate(
        "", length=8, random_mode=True, fmt="alphanumeric"
    )
    assert password == username
    assert len(username) == 8
    letters = username[:4]
    digits = username[4:]
    assert letters.isalpha() and letters.islower()
    assert digits.isdigit()


def test_generate_candidates_returns_qty_times_three_candidates():
    candidates = voucher_jobs.generate_candidates(5, "V", length=4, random_mode=False)
    assert len(candidates) == 15
    assert all(u.startswith("V") for u, p in candidates)
