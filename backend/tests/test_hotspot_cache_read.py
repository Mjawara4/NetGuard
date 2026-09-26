import json
import time

import fakeredis
import pytest

from app.services import hotspot_cache


@pytest.fixture
def fake_redis(monkeypatch):
    fake = fakeredis.FakeRedis(decode_responses=True)
    monkeypatch.setattr(hotspot_cache, "_client", lambda: fake)
    return fake


def test_read_dataset_returns_rows_and_fetched_at(fake_redis):
    fake_redis.set(
        "hotspot:dev-1:raw:active",
        json.dumps({"fetched_at": 1000.0, "rows": [{"user": "alice"}]}),
    )
    rows, fetched_at = hotspot_cache.read_dataset("dev-1", "active")
    assert rows == [{"user": "alice"}]
    assert fetched_at == 1000.0


def test_missing_key_returns_empty_not_error(fake_redis):
    rows, fetched_at = hotspot_cache.read_dataset("dev-1", "active")
    assert rows == []
    assert fetched_at is None


def test_corrupt_payload_returns_empty_not_error(fake_redis):
    fake_redis.set("hotspot:dev-1:raw:active", "}{not json")
    rows, fetched_at = hotspot_cache.read_dataset("dev-1", "active")
    assert rows == []
    assert fetched_at is None


def test_redis_failure_returns_empty_not_error(monkeypatch):
    class Boom:
        def get(self, *a, **k):
            raise RuntimeError("redis down")

    monkeypatch.setattr(hotspot_cache, "_client", lambda: Boom())
    # THE RULE: a cache failure must degrade to empty, never fall through to
    # the router and never raise.
    assert hotspot_cache.read_dataset("dev-1", "active") == ([], None)


def test_age_seconds():
    assert hotspot_cache.age_seconds(None) is None
    assert hotspot_cache.age_seconds(time.time() - 5) >= 4.5


# --- C1 Part B: request_refresh --------------------------------------------

def test_request_refresh_publishes_to_trigger_channel(fake_redis):
    pubsub = fake_redis.pubsub()
    pubsub.subscribe(hotspot_cache.TRIGGER_CHANNEL)
    pubsub.get_message(timeout=1)  # discard the subscribe confirmation

    hotspot_cache.request_refresh("dev-1")

    msg = pubsub.get_message(timeout=1)
    assert msg is not None
    assert msg["type"] == "message"
    assert msg["channel"] == hotspot_cache.TRIGGER_CHANNEL


def test_request_refresh_never_raises_when_redis_down(monkeypatch):
    class Boom:
        def publish(self, *a, **k):
            raise RuntimeError("redis down")

    monkeypatch.setattr(hotspot_cache, "_client", lambda: Boom())
    # Must not raise -- a failed trigger publish must never break the write
    # endpoint that just succeeded against the router.
    hotspot_cache.request_refresh("dev-1")


def test_request_refresh_with_no_device_id_still_publishes(fake_redis):
    pubsub = fake_redis.pubsub()
    pubsub.subscribe(hotspot_cache.TRIGGER_CHANNEL)
    pubsub.get_message(timeout=1)

    hotspot_cache.request_refresh()

    msg = pubsub.get_message(timeout=1)
    assert msg is not None
    assert msg["type"] == "message"
