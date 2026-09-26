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
    # TTL is ~30x the refresh interval so a key never expires between refreshes.
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
