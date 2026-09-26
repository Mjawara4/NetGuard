"""Endpoint-level tests for the cache-only /summary and /system-info reads.

These guard the actual conversion in app/routers/hotspot.py, not just the
app/services/hotspot_cache.py module the earlier unit tests cover. Each
endpoint is exercised in three cache states — warm, cold, and corrupted —
and every test carries a landmine on get_api_pool so any accidental router
call fails loudly instead of silently passing.
"""

import json
import time
import uuid
from unittest.mock import AsyncMock, MagicMock

import fakeredis
import pytest

from app.models import APIKey, Device
from app.routers import hotspot
from app.services import hotspot_cache


def _device(device_id):
    return Device(
        id=device_id,
        name="test-device",
        ip_address="10.0.0.1",
        site_id=uuid.uuid4(),
        ssh_username="admin",
        ssh_password="admin",
        ssh_port=8728,
    )


def _db_returning(device):
    result = MagicMock()
    result.scalars.return_value.first.return_value = device
    db = MagicMock()
    db.execute = AsyncMock(return_value=result)
    return db


def _unscoped_actor():
    # organization_id=None takes the `isinstance(actor, APIKey) and not
    # actor.organization_id` unscoped branch in both endpoints.
    return APIKey(organization_id=None)


@pytest.fixture(autouse=True)
def fake_redis(monkeypatch):
    fake = fakeredis.FakeRedis(decode_responses=True)
    monkeypatch.setattr(hotspot_cache, "_client", lambda: fake)
    return fake


@pytest.fixture(autouse=True)
def router_landmine(monkeypatch):
    """Any accidental router call from these endpoints must fail the test."""

    def _boom(*args, **kwargs):
        raise AssertionError("read endpoint reached get_api_pool — THE RULE violated")

    monkeypatch.setattr(hotspot, "get_api_pool", _boom)
    monkeypatch.setattr(hotspot, "decrypt_device_secrets", lambda device: device)


def _set_raw(fake_redis, device_id, dataset, fetched_at, rows):
    fake_redis.set(
        hotspot_cache.cache_key(device_id, dataset),
        json.dumps({"fetched_at": fetched_at, "rows": rows}),
    )


# ---------------------------------------------------------------------------
# /summary
# ---------------------------------------------------------------------------

async def test_summary_warm_cache_returns_real_values(fake_redis):
    device_id = str(uuid.uuid4())
    now = time.time()
    _set_raw(fake_redis, device_id, "active", now, [
        {"bytes-in": "1000", "bytes-out": "2000"},
        {"bytes-in": "3000", "bytes-out": "4000"},
    ])
    _set_raw(fake_redis, device_id, "users", now, [
        {"profile": "default"},
        {"profile": "default"},
        {"profile": "premium"},
    ])

    result = await hotspot.get_hotspot_summary(
        device_id, db=_db_returning(_device(device_id)), actor=_unscoped_actor()
    )

    assert set(result.keys()) == {
        "active_count", "total_vouchers", "total_data_mb",
        "profile_distribution", "fetched_at", "stale",
    }
    assert result["active_count"] == 2
    assert result["total_vouchers"] == 3
    assert result["total_data_mb"] == round(10000 / 1024 / 1024, 2)
    assert sorted(result["profile_distribution"], key=lambda x: x["name"]) == [
        {"name": "default", "value": 2}, {"name": "premium", "value": 1},
    ]
    assert result["fetched_at"] == now
    assert result["stale"] is False


async def test_summary_cold_cache_returns_200_and_stale(fake_redis):
    device_id = str(uuid.uuid4())

    result = await hotspot.get_hotspot_summary(
        device_id, db=_db_returning(_device(device_id)), actor=_unscoped_actor()
    )

    assert set(result.keys()) == {
        "active_count", "total_vouchers", "total_data_mb",
        "profile_distribution", "fetched_at", "stale",
    }
    assert result["active_count"] == 0
    assert result["total_vouchers"] == 0
    assert result["total_data_mb"] == 0
    assert result["profile_distribution"] == []
    assert result["fetched_at"] is None
    assert result["stale"] is True


async def test_summary_corrupted_rows_not_a_list_returns_200_and_stale(fake_redis):
    device_id = str(uuid.uuid4())
    now = time.time()
    # "active" cached payload has rows as a dict, not a list.
    _set_raw(fake_redis, device_id, "active", now, {"unexpected": "dict"})
    _set_raw(fake_redis, device_id, "users", now, [{"profile": "default"}])

    result = await hotspot.get_hotspot_summary(
        device_id, db=_db_returning(_device(device_id)), actor=_unscoped_actor()
    )

    assert set(result.keys()) == {
        "active_count", "total_vouchers", "total_data_mb",
        "profile_distribution", "fetched_at", "stale",
    }
    assert result["stale"] is True
    assert result["fetched_at"] is None


async def test_summary_corrupted_non_numeric_field_returns_200_and_stale(fake_redis):
    device_id = str(uuid.uuid4())
    now = time.time()
    _set_raw(fake_redis, device_id, "active", now, [
        {"bytes-in": "not-a-number", "bytes-out": "5"},
    ])
    _set_raw(fake_redis, device_id, "users", now, [{"profile": "default"}])

    result = await hotspot.get_hotspot_summary(
        device_id, db=_db_returning(_device(device_id)), actor=_unscoped_actor()
    )

    assert set(result.keys()) == {
        "active_count", "total_vouchers", "total_data_mb",
        "profile_distribution", "fetched_at", "stale",
    }
    assert result["stale"] is True
    assert result["fetched_at"] is None


# ---------------------------------------------------------------------------
# /system-info
# ---------------------------------------------------------------------------

async def test_system_info_warm_cache_returns_real_values(fake_redis):
    device_id = str(uuid.uuid4())
    now = time.time()
    _set_raw(fake_redis, device_id, "system", now, [{
        "cpu-load": "5",
        "free-memory": str(64 * 1024 * 1024),
        "total-memory": str(128 * 1024 * 1024),
        "uptime": "1d2h3m4s",
        "version": "7.1",
        "board-name": "hAP ac2",
    }])

    result = await hotspot.get_router_system_info(
        device_id, db=_db_returning(_device(device_id)), actor=_unscoped_actor()
    )

    assert set(result.keys()) == {
        "cpu_load", "free_memory", "total_memory", "uptime", "version",
        "board_name", "fetched_at", "stale",
    }
    assert result["cpu_load"] == "5"
    assert result["free_memory"] == 64.0
    assert result["total_memory"] == 128.0
    assert result["uptime"] == "1d2h3m4s"
    assert result["version"] == "7.1"
    assert result["board_name"] == "hAP ac2"
    assert result["fetched_at"] == now
    assert result["stale"] is False


async def test_system_info_cold_cache_returns_200_and_stale(fake_redis):
    device_id = str(uuid.uuid4())

    result = await hotspot.get_router_system_info(
        device_id, db=_db_returning(_device(device_id)), actor=_unscoped_actor()
    )

    assert set(result.keys()) == {
        "cpu_load", "free_memory", "total_memory", "uptime", "version",
        "board_name", "fetched_at", "stale",
    }
    assert result["cpu_load"] is None
    assert result["free_memory"] is None
    assert result["total_memory"] is None
    assert result["uptime"] is None
    assert result["version"] is None
    assert result["board_name"] is None
    assert result["fetched_at"] is None
    assert result["stale"] is True


async def test_system_info_corrupted_rows_not_a_list_returns_200_and_stale(fake_redis):
    """This is the exact shape of the Critical finding: rows decoded to a
    dict instead of a list. Before the fix, `rows[0]` on a dict ran outside
    the try/except and raised (KeyError, uncaught by the narrower except
    tuple), producing an HTTP 500 — the precise failure this test guards
    against.
    """
    device_id = str(uuid.uuid4())
    now = time.time()
    _set_raw(fake_redis, device_id, "system", now, {"unexpected": "dict"})

    result = await hotspot.get_router_system_info(
        device_id, db=_db_returning(_device(device_id)), actor=_unscoped_actor()
    )

    assert set(result.keys()) == {
        "cpu_load", "free_memory", "total_memory", "uptime", "version",
        "board_name", "fetched_at", "stale",
    }
    assert result["stale"] is True
    assert result["fetched_at"] is None


async def test_system_info_corrupted_non_numeric_field_returns_200_and_stale(fake_redis):
    device_id = str(uuid.uuid4())
    now = time.time()
    _set_raw(fake_redis, device_id, "system", now, [{
        "cpu-load": "5",
        "free-memory": "not-a-number",
        "total-memory": str(128 * 1024 * 1024),
        "uptime": "1d",
        "version": "7.1",
        "board-name": "hAP ac2",
    }])

    result = await hotspot.get_router_system_info(
        device_id, db=_db_returning(_device(device_id)), actor=_unscoped_actor()
    )

    assert set(result.keys()) == {
        "cpu_load", "free_memory", "total_memory", "uptime", "version",
        "board_name", "fetched_at", "stale",
    }
    assert result["stale"] is True
    assert result["fetched_at"] is None
