"""Tests for cache invalidation on hotspot write endpoints.

Unlike test_hotspot_endpoints_cache.py, THE RULE ("never call the router")
does NOT apply here. These endpoints — creating/deleting a voucher, a
profile, or kicking an active session — legitimately reach the router: the
write must be confirmed by the device before the operator is told it
succeeded. Only the six *read* endpoints (covered in
test_hotspot_endpoints_cache.py, which carries its own file-scoped
autouse landmine) are forbidden from calling the router.

Each test here stubs `get_api_pool` to return a fake connection so no real
network call is attempted, then asserts that the affected Redis dataset key
(app/services/hotspot_cache.py's NEW `hotspot:{device_id}:raw:{dataset}`
scheme) is deleted after a successful write, and preserved after a failed one.
"""

import json
import time
import uuid
from unittest.mock import AsyncMock, MagicMock

import fakeredis
import pytest
from fastapi import HTTPException

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
    db.commit = AsyncMock()
    db.rollback = AsyncMock()
    return db


def _unscoped_actor():
    # organization_id=None takes the `isinstance(actor, APIKey) and not
    # actor.organization_id` unscoped branch.
    return APIKey(organization_id=None)


def _seed(fake_redis, device_id, dataset, rows, fetched_at=None):
    fake_redis.set(
        hotspot_cache.cache_key(device_id, dataset),
        json.dumps({"fetched_at": fetched_at or time.time(), "rows": rows}),
    )


def _stub_connection():
    """A fake PooledConnection: .get_api() -> a MagicMock API, .disconnect() no-op."""
    api = MagicMock()
    connection = MagicMock()
    connection.get_api.return_value = api
    connection.disconnect.return_value = None
    return connection, api


@pytest.fixture(autouse=True)
def fake_redis(monkeypatch):
    fake = fakeredis.FakeRedis(decode_responses=True)
    monkeypatch.setattr(hotspot_cache, "_client", lambda: fake)
    return fake


@pytest.fixture(autouse=True)
def no_real_router(monkeypatch):
    """These endpoints legitimately call the router — always route it through
    a stub, never the real `get_api_pool`/`decrypt_device_secrets`."""
    monkeypatch.setattr(hotspot, "decrypt_device_secrets", lambda device: device)


# ---------------------------------------------------------------------------
# POST /{device_id}/users
# ---------------------------------------------------------------------------

async def test_create_user_success_invalidates_users_cache(fake_redis, monkeypatch):
    device_id = str(uuid.uuid4())
    _seed(fake_redis, device_id, "users", [{"name": "old-voucher"}])

    connection, api = _stub_connection()
    resource = MagicMock()
    resource.get.return_value = []  # no existing user with this name
    resource.add.return_value = None
    api.get_resource.return_value = resource
    monkeypatch.setattr(hotspot, "get_api_pool", lambda *a, **kw: connection)

    result = await hotspot.create_hotspot_user(
        device_id,
        hotspot.HotspotUser(name="newuser", password="pw", profile="default"),
        db=_db_returning(_device(device_id)),
        actor=_unscoped_actor(),
    )

    assert result == {"status": "success"}
    assert fake_redis.get(hotspot_cache.cache_key(device_id, "users")) is None


async def test_create_user_router_failure_preserves_cache(fake_redis, monkeypatch):
    """A failed voucher creation must not blow away a valid cache."""
    device_id = str(uuid.uuid4())
    _seed(fake_redis, device_id, "users", [{"name": "old-voucher"}])

    connection, api = _stub_connection()
    resource = MagicMock()
    resource.get.return_value = []
    resource.add.side_effect = Exception("router unreachable")
    api.get_resource.return_value = resource
    monkeypatch.setattr(hotspot, "get_api_pool", lambda *a, **kw: connection)

    with pytest.raises(HTTPException):
        await hotspot.create_hotspot_user(
            device_id,
            hotspot.HotspotUser(name="newuser", password="pw", profile="default"),
            db=_db_returning(_device(device_id)),
            actor=_unscoped_actor(),
        )

    assert fake_redis.get(hotspot_cache.cache_key(device_id, "users")) is not None


# ---------------------------------------------------------------------------
# DELETE /{device_id}/users/{username}
# ---------------------------------------------------------------------------

async def test_delete_user_success_invalidates_users_cache(fake_redis, monkeypatch):
    device_id = str(uuid.uuid4())
    _seed(fake_redis, device_id, "users", [{"name": "gone-voucher"}])

    connection, api = _stub_connection()
    resource = MagicMock()
    resource.get.return_value = [{"id": "*1", "name": "gone-voucher"}]
    resource.remove.return_value = None
    api.get_resource.return_value = resource
    monkeypatch.setattr(hotspot, "get_api_pool", lambda *a, **kw: connection)

    result = await hotspot.delete_hotspot_user(
        device_id, "gone-voucher",
        db=_db_returning(_device(device_id)),
        actor=_unscoped_actor(),
    )

    assert result == {"status": "success"}
    assert fake_redis.get(hotspot_cache.cache_key(device_id, "users")) is None


# ---------------------------------------------------------------------------
# POST /{device_id}/users/batch
# ---------------------------------------------------------------------------

async def test_batch_generate_users_invalidates_users_cache(fake_redis, monkeypatch):
    device_id = str(uuid.uuid4())
    _seed(fake_redis, device_id, "users", [{"name": "old-voucher"}])

    connection, api = _stub_connection()
    resource = MagicMock()
    resource.add.return_value = None
    api.get_resource.return_value = resource
    monkeypatch.setattr(hotspot, "get_api_pool", lambda *a, **kw: connection)

    result = await hotspot.batch_generate_users(
        device_id,
        hotspot.BatchUserCreate(qty=1, prefix="V", profile="default", random_mode=True, format="numeric", length=4),
        db=_db_returning(_device(device_id)),
        actor=_unscoped_actor(),
    )

    assert len(result) == 1
    assert fake_redis.get(hotspot_cache.cache_key(device_id, "users")) is None


# ---------------------------------------------------------------------------
# DELETE /{device_id}/users/bulk
# ---------------------------------------------------------------------------

async def test_bulk_delete_users_invalidates_users_cache(fake_redis, monkeypatch):
    device_id = str(uuid.uuid4())
    _seed(fake_redis, device_id, "users", [{"name": "expired-voucher"}])

    connection, api = _stub_connection()
    resource = MagicMock()
    resource.get.return_value = [{
        "id": "*1", "comment": "promo",
        "uptime": "0s", "limit-uptime": None,
        "bytes-in": "0", "bytes-out": "0", "limit-bytes-total": None,
    }]
    api.get_resource.return_value = resource

    binary_resource = MagicMock()
    binary_resource.call.return_value = None
    api.get_binary_resource.return_value = binary_resource

    monkeypatch.setattr(hotspot, "get_api_pool", lambda *a, **kw: connection)

    result = await hotspot.bulk_delete_users(
        device_id, comment="promo", expired=False, unused=False,
        db=_db_returning(_device(device_id)),
        actor=_unscoped_actor(),
    )

    assert result["status"] == "success"
    assert fake_redis.get(hotspot_cache.cache_key(device_id, "users")) is None


# ---------------------------------------------------------------------------
# POST /{device_id}/profiles
# ---------------------------------------------------------------------------

async def test_create_profile_success_invalidates_profiles_cache(fake_redis, monkeypatch):
    device_id = str(uuid.uuid4())
    _seed(fake_redis, device_id, "profiles", [{"name": "old-profile"}])

    connection, api = _stub_connection()
    resource = MagicMock()
    resource.add.return_value = None
    api.get_resource.return_value = resource
    monkeypatch.setattr(hotspot, "get_api_pool", lambda *a, **kw: connection)

    result = await hotspot.create_hotspot_profile(
        device_id,
        hotspot.HotspotProfile(name="new-profile", rateLimit="1M/1M", sharedUsers=1),
        db=_db_returning(_device(device_id)),
        actor=_unscoped_actor(),
    )

    assert result == {"status": "success"}
    assert fake_redis.get(hotspot_cache.cache_key(device_id, "profiles")) is None


# ---------------------------------------------------------------------------
# DELETE /{device_id}/profiles/{profile_name}
# ---------------------------------------------------------------------------

async def test_delete_profile_success_invalidates_profiles_cache(fake_redis, monkeypatch):
    device_id = str(uuid.uuid4())
    _seed(fake_redis, device_id, "profiles", [{"name": "gone-profile"}])

    connection, api = _stub_connection()
    resource = MagicMock()
    resource.get.return_value = [{"id": "*1", "name": "gone-profile"}]
    resource.remove.return_value = None
    api.get_resource.return_value = resource
    monkeypatch.setattr(hotspot, "get_api_pool", lambda *a, **kw: connection)

    result = await hotspot.delete_hotspot_profile(
        device_id, "gone-profile",
        db=_db_returning(_device(device_id)),
        actor=_unscoped_actor(),
    )

    assert result == {"status": "success"}
    assert fake_redis.get(hotspot_cache.cache_key(device_id, "profiles")) is None


# ---------------------------------------------------------------------------
# DELETE /{device_id}/active/{active_id}
# ---------------------------------------------------------------------------

async def test_kick_active_user_invalidates_active_cache(fake_redis, monkeypatch):
    device_id = str(uuid.uuid4())
    _seed(fake_redis, device_id, "active", [{"user": "someone"}])

    connection, api = _stub_connection()
    resource = MagicMock()
    resource.remove.return_value = None
    api.get_resource.return_value = resource
    monkeypatch.setattr(hotspot, "get_api_pool", lambda *a, **kw: connection)

    result = await hotspot.kick_active_user(
        device_id, "*A1",
        db=_db_returning(_device(device_id)),
        actor=_unscoped_actor(),
    )

    assert result == {"status": "success"}
    assert fake_redis.get(hotspot_cache.cache_key(device_id, "active")) is None
