"""THE RULE is enforced in this file: hotspot read endpoints never call the
router, not even on a cache miss.

Endpoint-level tests for the cache-only /summary, /system-info, /users,
/active, /profiles and /logs reads. These guard the actual conversion in
app/routers/hotspot.py, not just the app/services/hotspot_cache.py module the
earlier unit tests cover. Each endpoint is exercised in three cache states —
warm, cold, and corrupted — and every test carries a landmine on get_api_pool
(via the autouse `router_landmine` fixture) so any accidental router call
fails loudly instead of silently passing.

/reports is intentionally NOT covered here: it reads VoucherSale from
Postgres, never the router, so it already satisfies THE RULE without a
dataset conversion — see get_hotspot_reports in app/routers/hotspot.py.

All six hotspot read endpoints are covered as of this file's current state.
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


async def test_system_info_empty_string_memory_returns_200_not_raising(fake_redis):
    """S2: a raw row with free-memory/total-memory set to '' (empty string,
    as RouterOS sometimes reports transiently) must degrade that field to 0
    via the `or 0` guard, not raise -- and unlike the fully-corrupted cases
    above, the rest of the row (cpu_load, uptime, version, board_name) stays
    intact since the conversion no longer throws partway through.
    """
    device_id = str(uuid.uuid4())
    now = time.time()
    _set_raw(fake_redis, device_id, "system", now, [{
        "cpu-load": "5",
        "free-memory": "",
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
    assert result["free_memory"] == 0.0
    assert result["total_memory"] == 128.0
    assert result["cpu_load"] == "5"
    assert result["uptime"] == "1d2h3m4s"
    assert result["version"] == "7.1"
    assert result["board_name"] == "hAP ac2"
    assert result["fetched_at"] == now
    assert result["stale"] is False


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


async def test_users_empty_string_bytes_degrades_one_row_not_whole_list(fake_redis):
    """I4: `bytes-in`/`bytes-out` of '' (a real RouterOS quirk, distinct from
    the 'not-a-number' corruption case above) must not raise -- the `or 0`
    guard means one bad voucher degrades to bytes=0 instead of the whole
    list going empty.
    """
    device_id = str(uuid.uuid4())
    now = time.time()
    _set_raw(fake_redis, device_id, "users", now, [
        {"name": "alice", "bytes-in": "", "bytes-out": ""},
        {"name": "bob", "bytes-in": "100", "bytes-out": "200"},
    ])

    result = await hotspot.get_hotspot_users(
        device_id, limit=200, offset=0, search=None, refresh=False,
        db=_db_returning(_device(device_id)), actor=_unscoped_actor()
    )

    assert len(result) == 2
    alice = next(u for u in result if u.name == "alice")
    assert alice.bytes_in == 0
    assert alice.bytes_out == 0
    bob = next(u for u in result if u.name == "bob")
    assert bob.bytes_in == 100
    assert bob.bytes_out == 200


async def test_users_limit_200_skips_building_models_for_whole_dataset(fake_redis, monkeypatch):
    """I4: with no search filter, /users must slice the raw rows to the
    requested page BEFORE building pydantic models, not build 11k+ models
    and only then slice. Asserted by counting HotspotUser construction
    calls, not by timing.
    """
    device_id = str(uuid.uuid4())
    now = time.time()
    rows = [{"name": f"user{i}", "bytes-in": "0", "bytes-out": "0"} for i in range(5000)]
    _set_raw(fake_redis, device_id, "users", now, rows)

    construct_count = {"n": 0}
    real_cls = hotspot.HotspotUser

    class CountingHotspotUser(real_cls):
        def __init__(self, **kwargs):
            construct_count["n"] += 1
            super().__init__(**kwargs)

    monkeypatch.setattr(hotspot, "HotspotUser", CountingHotspotUser)

    result = await hotspot.get_hotspot_users(
        device_id, limit=200, offset=0, search=None, refresh=False,
        db=_db_returning(_device(device_id)), actor=_unscoped_actor()
    )

    assert len(result) == 200
    # The whole point of I4: 200, not 5000.
    assert construct_count["n"] == 200


async def test_users_search_still_scans_full_dataset(fake_redis):
    """The slice-first optimization must only apply when search is None --
    a search has to look at every row regardless of `limit`/`offset`."""
    device_id = str(uuid.uuid4())
    now = time.time()
    rows = [{"name": f"user{i}", "bytes-in": "0", "bytes-out": "0"} for i in range(300)]
    rows.append({"name": "findme", "bytes-in": "0", "bytes-out": "0"})
    _set_raw(fake_redis, device_id, "users", now, rows)

    result = await hotspot.get_hotspot_users(
        device_id, limit=200, offset=0, search="findme", refresh=False,
        db=_db_returning(_device(device_id)), actor=_unscoped_actor()
    )

    assert len(result) == 1
    assert result[0].name == "findme"


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


# ---------------------------------------------------------------------------
# /profiles
#
# get_hotspot_profiles returns a bare List[dict] (response_model enforces
# this in production), so like /users and /active there is no top-level dict
# to hang a "stale" key off of without changing the response shape from an
# array to an object. A degraded read instead returns an empty list with no
# exception. This endpoint joins the "profiles", "active" and "users"
# datasets to compute per-profile active_users counts.
# ---------------------------------------------------------------------------

HOTSPOT_PROFILE_KEYS = {
    "name", "rate-limit", "shared-users", "active_users",
    "custom_price", "custom_currency",
}


def _device_with_pricing(device_id, profile_pricing=None, default_currency="TZS"):
    device = _device(device_id)
    device.voucher_template = {
        "profile_pricing": profile_pricing or {},
        "default_currency": default_currency,
    }
    return device


async def test_profiles_warm_cache_returns_real_values(fake_redis):
    device_id = str(uuid.uuid4())
    now = time.time()
    _set_raw(fake_redis, device_id, "profiles", now, [
        {"name": "default", "rate-limit": "2M/2M", "shared-users": "1"},
        {"name": "premium", "rate-limit": "10M/10M", "shared-users": "1"},
    ])
    _set_raw(fake_redis, device_id, "active", now, [
        {"user": "alice"}, {"user": "bob"}, {"user": "carol"},
    ])
    _set_raw(fake_redis, device_id, "users", now, [
        {"name": "alice", "profile": "default"},
        {"name": "bob", "profile": "premium"},
        {"name": "carol", "profile": "default"},
    ])

    device = _device_with_pricing(
        device_id,
        profile_pricing={"default": {"price": 1000, "currency": "TZS"}},
    )

    result = await hotspot.get_hotspot_profiles(
        device_id, refresh=False, db=_db_returning(device), actor=_unscoped_actor()
    )

    assert len(result) == 2
    assert set(result[0].keys()) == HOTSPOT_PROFILE_KEYS
    default = next(p for p in result if p["name"] == "default")
    premium = next(p for p in result if p["name"] == "premium")
    assert default["rate-limit"] == "2M/2M"
    assert default["shared-users"] == "1"
    assert default["active_users"] == 2
    assert default["custom_price"] == 1000
    assert default["custom_currency"] == "TZS"
    assert premium["active_users"] == 1
    assert premium["custom_price"] == 0
    assert premium["custom_currency"] == "TZS"


async def test_profiles_cold_cache_returns_empty_list_not_error(fake_redis):
    device_id = str(uuid.uuid4())

    result = await hotspot.get_hotspot_profiles(
        device_id, refresh=False, db=_db_returning(_device_with_pricing(device_id)),
        actor=_unscoped_actor()
    )

    assert result == []


async def test_profiles_corrupted_rows_not_a_list_returns_empty_list(fake_redis):
    device_id = str(uuid.uuid4())
    now = time.time()
    # "profiles" cached payload has rows as a dict, not a list.
    _set_raw(fake_redis, device_id, "profiles", now, {"unexpected": "dict"})
    _set_raw(fake_redis, device_id, "active", now, [])
    _set_raw(fake_redis, device_id, "users", now, [])

    result = await hotspot.get_hotspot_profiles(
        device_id, refresh=False, db=_db_returning(_device_with_pricing(device_id)),
        actor=_unscoped_actor()
    )

    assert result == []


async def test_profiles_corrupted_malformed_row_returns_empty_list(fake_redis):
    device_id = str(uuid.uuid4())
    now = time.time()
    # "profiles" is a list, as required, but one entry is a string instead of
    # a dict — isinstance(rows, list) alone would not catch this; the
    # per-row .get() call inside the try block raises AttributeError.
    _set_raw(fake_redis, device_id, "profiles", now, ["not-a-dict"])
    _set_raw(fake_redis, device_id, "active", now, [])
    _set_raw(fake_redis, device_id, "users", now, [])

    result = await hotspot.get_hotspot_profiles(
        device_id, refresh=False, db=_db_returning(_device_with_pricing(device_id)),
        actor=_unscoped_actor()
    )

    assert result == []


# ---------------------------------------------------------------------------
# /logs
#
# get_hotspot_logs returns a bare list (no response_model, but still an
# array), so the same "no stale key" reasoning applies. Note the dataset
# name is "log" (singular) — that is what the poller agent writes; this is
# deliberately double-checked here since a mismatch would silently return
# empty forever with no error anywhere.
# ---------------------------------------------------------------------------

async def test_logs_warm_cache_returns_real_values(fake_redis):
    device_id = str(uuid.uuid4())
    now = time.time()
    _set_raw(fake_redis, device_id, "log", now, [
        {"topics": "hotspot,info", "time": "10:00:00", "message": "user alice (10.0.0.5): logged in"},
        {"topics": "system,error", "time": "11:00:00", "message": "unrelated system event"},
    ])

    result = await hotspot.get_hotspot_logs(
        device_id, db=_db_returning(_device(device_id)), actor=_unscoped_actor()
    )

    assert len(result) == 1
    assert set(result[0].keys()) == {"time", "user_info", "message"}
    assert result[0]["time"] == "10:00:00"
    assert result[0]["user_info"] == "alice"
    assert result[0]["message"] == "user alice (10.0.0.5): logged in"


async def test_logs_cold_cache_returns_empty_list_not_error(fake_redis):
    device_id = str(uuid.uuid4())

    result = await hotspot.get_hotspot_logs(
        device_id, db=_db_returning(_device(device_id)), actor=_unscoped_actor()
    )

    assert result == []


async def test_logs_corrupted_rows_not_a_list_returns_empty_list(fake_redis):
    device_id = str(uuid.uuid4())
    now = time.time()
    # "log" cached payload has rows as a dict, not a list.
    _set_raw(fake_redis, device_id, "log", now, {"unexpected": "dict"})

    result = await hotspot.get_hotspot_logs(
        device_id, db=_db_returning(_device(device_id)), actor=_unscoped_actor()
    )

    assert result == []


async def test_logs_corrupted_malformed_field_returns_empty_list(fake_redis):
    device_id = str(uuid.uuid4())
    now = time.time()
    # "topics" is an int instead of a string — .lower() raises AttributeError.
    _set_raw(fake_redis, device_id, "log", now, [
        {"topics": 12345, "time": "10:00:00", "message": "x"},
    ])

    result = await hotspot.get_hotspot_logs(
        device_id, db=_db_returning(_device(device_id)), actor=_unscoped_actor()
    )

    assert result == []
