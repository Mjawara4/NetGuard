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


def test_exists_false_on_redis_error(monkeypatch):
    class Boom:
        def exists(self, *a, **k):
            raise RuntimeError("redis down")

    monkeypatch.setattr(hotspot_cache, "_client", lambda: Boom())
    # Must never raise, same contract as write_dataset.
    assert hotspot_cache.exists("dev-1", "users") is False


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
    # C1/C3: even though the interval has not elapsed, an absent cache key
    # (invalidation, or a simulated Redis flush) must force a refresh.
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
