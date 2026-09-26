import json
import fakeredis
import pytest

import hotspot_cache


@pytest.fixture
def fake_redis(monkeypatch):
    fake = fakeredis.FakeRedis(decode_responses=True)
    monkeypatch.setattr(hotspot_cache, "_client", lambda: fake)
    return fake


def test_cache_key_format():
    assert hotspot_cache.cache_key("dev-1", "active") == "hotspot:dev-1:raw:active"


def test_write_dataset_stores_rows_and_timestamp(fake_redis):
    rows = [{"user": "alice", "bytes-in": "100"}]
    assert hotspot_cache.write_dataset("dev-1", "active", rows) is True

    stored = json.loads(fake_redis.get("hotspot:dev-1:raw:active"))
    assert stored["rows"] == rows
    assert isinstance(stored["fetched_at"], float)


def test_write_dataset_sets_ttl_for_dataset(fake_redis):
    hotspot_cache.write_dataset("dev-1", "active", [])
    ttl = fake_redis.ttl("hotspot:dev-1:raw:active")
    # TTL exists so the key never expires between refreshes (margin varies by
    # dataset -- see the comment on TTLS).
    assert 0 < ttl <= hotspot_cache.TTLS["active"]


def test_write_dataset_preserves_raw_rows_unmodified(fake_redis):
    # Raw RouterOS keys use dots and dashes; they must survive verbatim so the
    # backend's existing transformation code keeps working.
    rows = [{".id": "*1", "mac-address": "AA:BB", "session-time-left": "1h"}]
    hotspot_cache.write_dataset("dev-1", "active", rows)
    stored = json.loads(fake_redis.get("hotspot:dev-1:raw:active"))
    assert stored["rows"][0][".id"] == "*1"
    assert stored["rows"][0]["mac-address"] == "AA:BB"
    assert stored["rows"][0]["session-time-left"] == "1h"


def test_write_dataset_returns_false_on_redis_error(monkeypatch):
    class Boom:
        def setex(self, *a, **k):
            raise RuntimeError("redis down")

    monkeypatch.setattr(hotspot_cache, "_client", lambda: Boom())
    # Must never raise — a cache write failure must not break metric collection.
    assert hotspot_cache.write_dataset("dev-1", "active", []) is False


def test_unknown_dataset_rejected(fake_redis):
    with pytest.raises(ValueError):
        hotspot_cache.write_dataset("dev-1", "not-a-dataset", [])


def test_write_dataset_returns_false_on_unserializable_row(fake_redis):
    # json.dumps must run inside the try/except: a non-serializable row must
    # not raise into get_mikrotik_stats and break metric collection.
    rows = [{"bad": object()}]
    assert hotspot_cache.write_dataset("dev-1", "active", rows) is False


def test_should_refresh_returns_true_when_never_fetched():
    import monitor_agent
    last = {}
    assert monitor_agent.should_refresh(last, "dev-1", "users", 600, now=1000.0) is True


def test_should_refresh_respects_interval():
    import monitor_agent
    last = {("dev-1", "users"): 1000.0}
    assert monitor_agent.should_refresh(last, "dev-1", "users", 600, now=1500.0) is False
    assert monitor_agent.should_refresh(last, "dev-1", "users", 600, now=1601.0) is True


def test_should_refresh_does_not_mutate_last_refreshed():
    # New contract (C2): should_refresh is pure. Recording is a separate,
    # explicit step (record_refreshed) that callers only take on a
    # successful fetch+write, so a failed attempt cannot silently consume a
    # whole interval's worth of retries.
    import monitor_agent
    last = {}
    monitor_agent.should_refresh(last, "dev-1", "log", 30, now=500.0)
    assert last == {}


def test_record_refreshed_stores_the_time():
    import monitor_agent
    last = {}
    monitor_agent.record_refreshed(last, "dev-1", "log", now=500.0)
    assert last[("dev-1", "log")] == 500.0


# --- C1/C3: exists() -----------------------------------------------------

def test_exists_true_when_key_present(fake_redis):
    hotspot_cache.write_dataset("dev-1", "users", [{"name": "alice"}])
    assert hotspot_cache.exists("dev-1", "users") is True


def test_exists_false_when_key_absent(fake_redis):
    assert hotspot_cache.exists("dev-1", "users") is False


def test_exists_returns_none_on_redis_error(monkeypatch):
    # BLOCKER 1 Part A: exists() is a tri-state. A Redis error must report
    # "unknown" (None), NOT "absent" (False) -- collapsing those two was the
    # root cause of the cache-hammering defect (see exists()'s docstring).
    class Boom:
        def exists(self, *a, **k):
            raise RuntimeError("redis down")

    monkeypatch.setattr(hotspot_cache, "_client", lambda: Boom())
    # Must never raise, same contract as write_dataset.
    assert hotspot_cache.exists("dev-1", "users") is None


def test_exists_false_after_simulated_redis_flush(fake_redis):
    # Simulates C3: Redis flushed while the agent runs. The key is gone even
    # though the agent's own in-memory last_refreshed still thinks it's fresh.
    hotspot_cache.write_dataset("dev-1", "users", [{"name": "alice"}])
    fake_redis.flushall()
    assert hotspot_cache.exists("dev-1", "users") is False


# --- C1 Part B: deep_inspect_due -----------------------------------------

def test_deep_inspect_due_by_interval():
    import monitor_agent
    assert monitor_agent.deep_inspect_due(last_deep=1000.0, now=1029.0, interval=30) is False
    assert monitor_agent.deep_inspect_due(last_deep=1000.0, now=1030.0, interval=30) is True


def test_deep_inspect_due_forced_by_trigger_bypasses_interval():
    import monitor_agent
    # Would NOT be due by interval alone (only 5s elapsed of a 30s interval),
    # but a received trigger must force it through anyway.
    assert monitor_agent.deep_inspect_due(last_deep=1000.0, now=1005.0, interval=30, force=False) is False
    assert monitor_agent.deep_inspect_due(last_deep=1000.0, now=1005.0, interval=30, force=True) is True


# --- C1 Part B: wait_for_trigger ------------------------------------------

def test_wait_for_trigger_returns_true_on_message(monkeypatch):
    import monitor_agent

    class FakePubSub:
        def subscribe(self, channel):
            pass

        def get_message(self, timeout):
            return {"type": "message", "data": b"go"}

    class FakeRedisConn:
        def pubsub(self):
            return FakePubSub()

    monkeypatch.setattr(monitor_agent.redis, "Redis", lambda **kwargs: FakeRedisConn())
    assert monitor_agent.wait_for_trigger(1) is True


def test_wait_for_trigger_returns_false_on_timeout(monkeypatch):
    import monitor_agent

    class FakePubSub:
        def subscribe(self, channel):
            pass

        def get_message(self, timeout):
            return None

    class FakeRedisConn:
        def pubsub(self):
            return FakePubSub()

    monkeypatch.setattr(monitor_agent.redis, "Redis", lambda **kwargs: FakeRedisConn())
    assert monitor_agent.wait_for_trigger(0.01) is False


def test_wait_for_trigger_returns_false_and_sleeps_on_redis_error(monkeypatch):
    import monitor_agent

    def boom(**kwargs):
        raise RuntimeError("redis down")

    slept = {}
    monkeypatch.setattr(monitor_agent.redis, "Redis", boom)
    monkeypatch.setattr(monitor_agent.time, "sleep", lambda s: slept.setdefault("seconds", s))
    assert monitor_agent.wait_for_trigger(7) is False
    assert slept["seconds"] == 7


# --- C2: maybe_refresh_dataset --------------------------------------------

class _FakeResource:
    def __init__(self, rows=None, error=None):
        self._rows = rows
        self._error = error

    def get(self):
        if self._error:
            raise self._error
        return self._rows


class _FakeApi:
    def __init__(self, resource):
        self._resource = resource

    def get_resource(self, path):
        return self._resource


def test_maybe_refresh_dataset_records_time_on_success(fake_redis):
    import monitor_agent
    last = {}
    api = _FakeApi(_FakeResource(rows=[{"name": "alice"}]))
    ok = monitor_agent.maybe_refresh_dataset(
        api, "dev-1", "users", "/ip/hotspot/user", 1800, last, now=1000.0
    )
    assert ok is True
    assert last[("dev-1", "users")] == 1000.0


def test_maybe_refresh_dataset_does_not_record_on_fetch_failure(fake_redis):
    # C2: a timed-out fetch must not consume the refresh slot -- the next
    # pass should retry immediately rather than waiting a full interval.
    import monitor_agent
    last = {}
    api = _FakeApi(_FakeResource(error=TimeoutError("router timed out")))
    ok = monitor_agent.maybe_refresh_dataset(
        api, "dev-1", "users", "/ip/hotspot/user", 1800, last, now=1000.0
    )
    assert ok is False
    assert ("dev-1", "users") not in last
    # Confirm the retry actually happens on the very next pass (a later now
    # far short of the 1800s interval still reports "due").
    assert monitor_agent.should_refresh(last, "dev-1", "users", 1800, now=1001.0) is True


def test_maybe_refresh_dataset_does_not_record_on_write_failure(monkeypatch):
    # C2: a failed cache write (Redis down) must not record the timestamp
    # either -- only fetch AND write succeeding should.
    import monitor_agent
    last = {}
    api = _FakeApi(_FakeResource(rows=[{"name": "alice"}]))
    monkeypatch.setattr(hotspot_cache, "write_dataset", lambda *a, **k: False)
    monkeypatch.setattr(hotspot_cache, "exists", lambda *a, **k: True)
    ok = monitor_agent.maybe_refresh_dataset(
        api, "dev-1", "users", "/ip/hotspot/user", 1800, last, now=1000.0
    )
    assert ok is False
    assert ("dev-1", "users") not in last


def test_maybe_refresh_dataset_refreshes_when_cache_key_absent_even_if_not_due(fake_redis):
    # C1/C3, and BLOCKER 1 Part A's "definitively False" half: even though the
    # interval has not elapsed, a cache key confirmed absent (invalidation, or
    # a simulated Redis flush -- Redis DID answer, and said "no key") must
    # force a refresh. Contrast with the "unknown" (None) case below, which
    # must NOT force a refresh.
    import monitor_agent
    last = {("dev-1", "users"): 999.0}  # "just refreshed" a moment ago
    api = _FakeApi(_FakeResource(rows=[{"name": "alice"}]))
    ok = monitor_agent.maybe_refresh_dataset(
        api, "dev-1", "users", "/ip/hotspot/user", 1800, last, now=1000.0
    )
    assert ok is True
    assert last[("dev-1", "users")] == 1000.0


def test_maybe_refresh_dataset_skips_when_due_and_key_present(fake_redis):
    import monitor_agent
    hotspot_cache.write_dataset("dev-1", "users", [{"name": "alice"}])
    last = {("dev-1", "users"): 999.0}
    api = _FakeApi(_FakeResource(rows=[{"name": "bob"}]))
    ok = monitor_agent.maybe_refresh_dataset(
        api, "dev-1", "users", "/ip/hotspot/user", 1800, last, now=1000.0
    )
    assert ok is False
    assert last[("dev-1", "users")] == 999.0


# --- BLOCKER 1 Part A: exists() tri-state must not force on "unknown" -----

def test_maybe_refresh_dataset_does_not_force_refresh_when_exists_is_unknown(monkeypatch):
    """BLOCKER 1 Part A: when hotspot_cache.exists() returns None (Redis
    itself errored -- "unknown", not "absent"), a not-yet-due dataset must
    NOT be force-refreshed. Only a confirmed False (genuinely absent) may
    force a refresh; treating "unknown" the same as "absent" is exactly the
    cache-hammering defect this fix removes.
    """
    import monitor_agent

    monkeypatch.setattr(hotspot_cache, "exists", lambda *a, **k: None)
    last = {("dev-1", "users"): 999.0}  # refreshed a moment ago; interval not elapsed
    fetch_calls = {"n": 0}

    class _CountingResource:
        def get(self):
            fetch_calls["n"] += 1
            return [{"name": "alice"}]

    api = _FakeApi(_CountingResource())
    ok = monitor_agent.maybe_refresh_dataset(
        api, "dev-1", "users", "/ip/hotspot/user", 1800, last, now=1000.0
    )
    assert ok is False
    assert fetch_calls["n"] == 0
    assert last[("dev-1", "users")] == 999.0


# --- BLOCKER 1 Part B: failure backoff -------------------------------------

def test_maybe_refresh_dataset_backs_off_after_failed_fetch_then_retries(fake_redis):
    """BLOCKER 1 Part B: a failed router fetch starts a
    FAILURE_BACKOFF_SECONDS-long backoff for that (device_id, dataset) pair.
    While backed off, the dataset is skipped even if otherwise due; once the
    window elapses, it is retried and a success clears the failure record.
    """
    import monitor_agent

    last = {}
    last_failed = {}
    fail_api = _FakeApi(_FakeResource(error=TimeoutError("router timed out")))

    # First attempt fails and starts the backoff.
    ok = monitor_agent.maybe_refresh_dataset(
        fail_api, "dev-1", "users", "/ip/hotspot/user", 30, last,
        last_failed=last_failed, now=1000.0,
    )
    assert ok is False
    assert last_failed[("dev-1", "users")] == 1000.0

    # 30s later: interval (30) would otherwise make this "due", but the 120s
    # backoff window has not elapsed -- must be skipped without even trying.
    success_api = _FakeApi(_FakeResource(rows=[{"name": "alice"}]))
    ok = monitor_agent.maybe_refresh_dataset(
        success_api, "dev-1", "users", "/ip/hotspot/user", 30, last,
        last_failed=last_failed, now=1030.0,
    )
    assert ok is False
    assert ("dev-1", "users") not in last

    # Past the 120s backoff window: retried, and succeeds.
    ok = monitor_agent.maybe_refresh_dataset(
        success_api, "dev-1", "users", "/ip/hotspot/user", 30, last,
        last_failed=last_failed, now=1121.0,
    )
    assert ok is True
    assert last[("dev-1", "users")] == 1121.0
    # Success clears the failure record so recovery is immediate, not delayed
    # by a stale backoff.
    assert ("dev-1", "users") not in last_failed


def test_maybe_refresh_dataset_backs_off_after_failed_write_too(monkeypatch):
    """BLOCKER 1 Part B: a failed cache write (not just a failed fetch) also
    starts the backoff -- both failure modes named in the spec are covered.
    """
    import monitor_agent

    last = {}
    last_failed = {}
    api = _FakeApi(_FakeResource(rows=[{"name": "alice"}]))
    monkeypatch.setattr(hotspot_cache, "exists", lambda *a, **k: True)
    monkeypatch.setattr(hotspot_cache, "write_dataset", lambda *a, **k: False)

    ok = monitor_agent.maybe_refresh_dataset(
        api, "dev-1", "users", "/ip/hotspot/user", 30, last,
        last_failed=last_failed, now=1000.0,
    )
    assert ok is False
    assert last_failed[("dev-1", "users")] == 1000.0

    # Still backed off shortly after, even though it would otherwise be due.
    ok = monitor_agent.maybe_refresh_dataset(
        api, "dev-1", "users", "/ip/hotspot/user", 30, last,
        last_failed=last_failed, now=1010.0,
    )
    assert ok is False


# --- BLOCKER 1 Parts A+B together: the hammering regression test ----------

def test_regression_redis_outage_does_not_hammer_router_every_pass(monkeypatch):
    """Regression test for BLOCKER 1 (the critical finding): simulates Redis
    erroring on BOTH exists() and write_dataset() -- a Redis outage -- across
    many consecutive deep-inspect passes, and asserts the router fetch is
    attempted at most once per FAILURE_BACKOFF_SECONDS window, never on every
    pass.

    Before this fix: exists() returning False on error made every pass look
    "due" (Part A bug), and a failing write was retried every pass with no
    backoff (Part B gap) -- together, a 3.6 MB router fetch on every single
    ~30s deep-inspect pass for the duration of the outage.
    """
    import monitor_agent

    # Redis is down for both operations this function touches.
    monkeypatch.setattr(hotspot_cache, "exists", lambda *a, **k: None)
    monkeypatch.setattr(hotspot_cache, "write_dataset", lambda *a, **k: False)

    fetch_calls = {"n": 0}

    class _CountingResource:
        def get(self):
            fetch_calls["n"] += 1
            return [{"name": "alice"}]

    class _CountingApi:
        def get_resource(self, path):
            return _CountingResource()

    last_refreshed = {}
    last_failed = {}
    api = _CountingApi()

    # 20 simulated passes at the DEEP_INSPECT_INTERVAL cadence (30s), i.e.
    # 570s (9.5 minutes) of continuous Redis outage.
    num_passes = 20
    pass_interval = 30
    for i in range(num_passes):
        now = 1000.0 + i * pass_interval
        monitor_agent.maybe_refresh_dataset(
            api, "dev-1", "users", "/ip/hotspot/user", pass_interval,
            last_refreshed, last_failed=last_failed, now=now,
        )

    # should_refresh is always True here (write never succeeds, so
    # record_refreshed is never called) -- without the backoff this would be
    # one router fetch per pass, i.e. num_passes (20). With a 120s backoff
    # over ~570s elapsed, only a handful of attempts should occur.
    elapsed = (num_passes - 1) * pass_interval
    max_expected_attempts = elapsed // monitor_agent.FAILURE_BACKOFF_SECONDS + 1
    assert fetch_calls["n"] >= 1
    assert fetch_calls["n"] <= max_expected_attempts
    assert fetch_calls["n"] < num_passes  # explicitly: NOT one fetch per pass
