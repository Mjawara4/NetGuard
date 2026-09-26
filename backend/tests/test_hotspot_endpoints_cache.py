"""THE RULE is enforced in this file: hotspot read endpoints never call the
router, not even on a cache miss.

Endpoint-level tests for the cache-only /summary, /system-info, /users and
/active reads. These guard the actual conversion in app/routers/hotspot.py,
not just the app/services/hotspot_cache.py module the earlier unit tests
cover. Each endpoint is exercised in three cache states — warm, cold, and
corrupted — and every test carries a landmine on get_api_pool (via the
autouse `router_landmine` fixture) so any accidental router call fails loudly
instead of silently passing.

/profiles and /logs are still router-backed as of this file's current state
(Task 6 converts them) — they are deliberately NOT covered here yet. Once
converted, their coverage belongs in this file too, so THE RULE stays
enforced for the full read surface in one place rather than splitting across
files.
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


# ---------------------------------------------------------------------------
# /users
#
# get_hotspot_users returns a bare List[HotspotUser] (response_model enforces
# this in production), so unlike /summary and /system-info there is no
# top-level dict to hang a "stale" key off of without changing the response
# shape from an array to an object — a breaking change for the frontend that
# is out of scope here. A degraded read (missing or corrupted cache) instead
# returns an empty list with no exception, matching THE RULE's "HTTP 200,
# never a 500" without altering the existing array response contract.
# ---------------------------------------------------------------------------

HOTSPOT_USER_FIELDS = {
    "name", "password", "profile", "uptime", "bytes_in", "bytes_out",
    "limit_uptime", "limit_bytes_total", "comment",
}


async def test_users_warm_cache_returns_real_values(fake_redis):
    device_id = str(uuid.uuid4())
    now = time.time()
    _set_raw(fake_redis, device_id, "users", now, [
        {"name": "alice", "password": "pw1", "profile": "default", "uptime": "1h",
         "bytes-in": "1000", "bytes-out": "2000", "limit-uptime": "2h",
         "limit-bytes-total": "500000", "comment": "vip"},
        {"name": "bob", "profile": "premium"},
    ])

    result = await hotspot.get_hotspot_users(
        device_id, limit=200, offset=0, search=None, refresh=False,
        db=_db_returning(_device(device_id)), actor=_unscoped_actor()
    )

    assert len(result) == 2
    assert set(type(result[0]).model_fields.keys()) == HOTSPOT_USER_FIELDS
    alice = next(u for u in result if u.name == "alice")
    assert alice.password == "pw1"
    assert alice.profile == "default"
    assert alice.uptime == "1h"
    assert alice.bytes_in == 1000
    assert alice.bytes_out == 2000
    assert alice.limit_uptime == "2h"
    assert alice.limit_bytes_total == 500000
    assert alice.comment == "vip"


async def test_users_cold_cache_returns_empty_list_not_error(fake_redis):
    device_id = str(uuid.uuid4())

    result = await hotspot.get_hotspot_users(
        device_id, limit=200, offset=0, search=None, refresh=False,
        db=_db_returning(_device(device_id)), actor=_unscoped_actor()
    )

    assert result == []


async def test_users_corrupted_rows_not_a_list_returns_empty_list(fake_redis):
    device_id = str(uuid.uuid4())
    now = time.time()
    # cached payload has rows as a dict, not a list.
    _set_raw(fake_redis, device_id, "users", now, {"unexpected": "dict"})

    result = await hotspot.get_hotspot_users(
        device_id, limit=200, offset=0, search=None, refresh=False,
        db=_db_returning(_device(device_id)), actor=_unscoped_actor()
    )

    assert result == []


async def test_users_corrupted_non_numeric_field_returns_empty_list(fake_redis):
    device_id = str(uuid.uuid4())
    now = time.time()
    _set_raw(fake_redis, device_id, "users", now, [
        {"name": "alice", "bytes-in": "not-a-number"},
    ])

    result = await hotspot.get_hotspot_users(
        device_id, limit=200, offset=0, search=None, refresh=False,
        db=_db_returning(_device(device_id)), actor=_unscoped_actor()
    )

    assert result == []


# ---------------------------------------------------------------------------
# /active
#
# Same list-response reasoning as /users applies here (no top-level "stale"
# key). This endpoint additionally joins the "active" and "users" datasets to
# compute remaining_time, so both datasets are exercised, including the case
# where one is present and the other is cold.
# ---------------------------------------------------------------------------

HOTSPOT_ACTIVE_FIELDS = {
    "id", "user", "address", "uptime", "bytes_in", "bytes_out",
    "mac_address", "remaining_time", "limit_uptime", "limit_bytes_total",
}


async def test_active_warm_cache_returns_real_values(fake_redis):
    device_id = str(uuid.uuid4())
    now = time.time()
    _set_raw(fake_redis, device_id, "active", now, [
        {"id": "*1", "user": "alice", "address": "10.0.0.5", "uptime": "1h",
         "bytes-in": "100", "bytes-out": "200", "mac-address": "AA:BB:CC:DD:EE:FF"},
    ])
    _set_raw(fake_redis, device_id, "users", now, [
        {"name": "alice", "limit-uptime": "2h"},
    ])

    result = await hotspot.get_active_users(
        device_id, limit=200, offset=0, refresh=False,
        db=_db_returning(_device(device_id)), actor=_unscoped_actor()
    )

    assert len(result) == 1
    a = result[0]
    assert set(type(a).model_fields.keys()) == HOTSPOT_ACTIVE_FIELDS
    assert a.id == "*1"
    assert a.user == "alice"
    assert a.address == "10.0.0.5"
    assert a.uptime == "1h"
    assert a.bytes_in == 100
    assert a.bytes_out == 200
    assert a.mac_address == "AA:BB:CC:DD:EE:FF"


async def test_active_cold_cache_returns_empty_list_not_error(fake_redis):
    device_id = str(uuid.uuid4())

    result = await hotspot.get_active_users(
        device_id, limit=200, offset=0, refresh=False,
        db=_db_returning(_device(device_id)), actor=_unscoped_actor()
    )

    assert result == []


async def test_active_missing_users_dataset_degrades_to_unlim(fake_redis):
    """'active' is warm but 'users' — needed for the limits join — is cold.

    read_dataset cannot distinguish "cache miss" from "this device genuinely
    has zero registered users": both decode to ([], None). The unchanged
    transformation loop already handles an empty user_limits map the same
    way it handles a router response with no users — sessions are still
    returned, just without a computed remaining_time. This is the correct,
    pre-existing degrade path, not a bug to special-case away.
    """
    device_id = str(uuid.uuid4())
    now = time.time()
    _set_raw(fake_redis, device_id, "active", now, [
        {"id": "*1", "user": "alice", "address": "10.0.0.5", "uptime": "1h",
         "bytes-in": "100", "bytes-out": "200"},
    ])

    result = await hotspot.get_active_users(
        device_id, limit=200, offset=0, refresh=False,
        db=_db_returning(_device(device_id)), actor=_unscoped_actor()
    )

    assert len(result) == 1
    assert result[0].user == "alice"
    assert result[0].remaining_time == "UNLIM"


async def test_active_corrupted_active_rows_not_a_list_returns_empty_list(fake_redis):
    device_id = str(uuid.uuid4())
    now = time.time()
    _set_raw(fake_redis, device_id, "active", now, {"unexpected": "dict"})
    _set_raw(fake_redis, device_id, "users", now, [{"name": "alice"}])

    result = await hotspot.get_active_users(
        device_id, limit=200, offset=0, refresh=False,
        db=_db_returning(_device(device_id)), actor=_unscoped_actor()
    )

    assert result == []


async def test_active_corrupted_non_numeric_field_returns_empty_list(fake_redis):
    device_id = str(uuid.uuid4())
    now = time.time()
    _set_raw(fake_redis, device_id, "active", now, [
        {"user": "alice", "bytes-in": "not-a-number", "address": "10.0.0.5", "uptime": "1h"},
    ])
    _set_raw(fake_redis, device_id, "users", now, [{"name": "alice"}])

    result = await hotspot.get_active_users(
        device_id, limit=200, offset=0, refresh=False,
        db=_db_returning(_device(device_id)), actor=_unscoped_actor()
    )

    assert result == []


async def test_active_limits_join_computes_remaining_time(fake_redis):
    """The most breakable thing in this task: remaining_time depends on
    joining the 'active' and 'users' datasets by username via the
    user_limits map. If that join breaks silently, remaining_time reverts to
    the 'UNLIM' default instead of raising — this test guards against that.
    """
    device_id = str(uuid.uuid4())
    now = time.time()
    _set_raw(fake_redis, device_id, "active", now, [
        {"id": "*1", "user": "alice", "address": "10.0.0.5", "uptime": "30m",
         "bytes-in": "0", "bytes-out": "0"},
    ])
    _set_raw(fake_redis, device_id, "users", now, [
        {"name": "alice", "limit-uptime": "2h"},
    ])

    result = await hotspot.get_active_users(
        device_id, limit=200, offset=0, refresh=False,
        db=_db_returning(_device(device_id)), actor=_unscoped_actor()
    )

    assert len(result) == 1
    assert result[0].remaining_time == "1h30m"
    assert result[0].remaining_time != "UNLIM"
