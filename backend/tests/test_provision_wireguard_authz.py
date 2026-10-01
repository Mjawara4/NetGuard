"""Role gate on POST /devices/{id}/provision-wireguard.

Why this endpoint needs the same gate as provision-script: its response body
carries `wg_private_key`, the router's tunnel private key, and the script it
returns embeds it. Task 9 gated provision-script specifically to protect that
key. Leaving this door open beside it made the new gate theatre -- an actor who
only wants the tunnel key would use the older endpoint. Any authorized actor,
including a VIEWER, could call it.

The gate must sit BEFORE key generation and persistence, so a refused caller
cannot leave a freshly minted key on the device row or a peer appended to the
server's wg0.conf. Each refusal test therefore asserts that nothing was read,
written, minted or appended, not merely that the status code was 403.
"""
import base64
import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import HTTPException

from app.models import APIKey, Device, User, UserRole
from app.routers import devices
from app.services.wireguard import WireGuardService

PRIV = base64.b64encode(bytes(range(32))).decode()
PUB = base64.b64encode(bytes(range(100, 132))).decode()
SERVER_PUB = base64.b64encode(bytes(range(60, 92))).decode()
ORG = uuid.uuid4()


def _device(priv=None, pub=None, ip=None):
    return Device(id=uuid.uuid4(), name="r1", ip_address="192.0.2.1",
                  site_id=uuid.uuid4(), wg_private_key=priv, wg_public_key=pub,
                  wg_ip_address=ip, ssh_username="admin", ssh_password="admin")


def _db(row):
    result = MagicMock()
    result.scalars.return_value.first.return_value = row
    db = MagicMock()
    db.execute = AsyncMock(return_value=result)
    db.add = MagicMock()
    db.commit = AsyncMock()
    db.refresh = AsyncMock()
    return db


@pytest.fixture
def no_side_effects(monkeypatch):
    """Record every state-changing call the handler can make, and stop it reaching disk."""
    calls = {"keys": 0, "peers": [], "ip": 0}

    def keys():
        calls["keys"] += 1
        return PRIV, PUB

    async def get_ip(db):
        calls["ip"] += 1
        return "10.13.13.7"

    monkeypatch.setattr(WireGuardService, "generate_keys", staticmethod(keys))
    monkeypatch.setattr(WireGuardService, "get_available_ip", staticmethod(get_ip))
    monkeypatch.setattr(WireGuardService, "add_peer_to_conf",
                        staticmethod(lambda pub, ip: calls["peers"].append((pub, ip))))
    monkeypatch.setattr(devices.settings, "WG_SERVER_PUBLIC_KEY", SERVER_PUB)
    monkeypatch.setattr(devices.settings, "WG_SERVER_ENDPOINT", "203.0.113.1")
    monkeypatch.setattr(devices.settings, "WG_SERVER_PORT", 51820)
    return calls


def _user(role, org=ORG):
    return User(id=uuid.uuid4(), email="u@x", hashed_password="x", role=role,
                organization_id=org)


async def _call(actor, device, db=None):
    db = db or _db(device)
    resp = await devices.provision_wireguard(str(device.id), db=db, actor=actor)
    return resp, db


async def test_org_admin_gets_the_tunnel_and_the_script(no_side_effects):
    device = _device()
    resp, db = await _call(_user(UserRole.ORG_ADMIN), device)
    assert resp.wg_private_key == PRIV
    assert resp.wg_ip_address == "10.13.13.7"
    assert "wireguard-netguard" in resp.mikrotik_script
    db.commit.assert_awaited_once()
    assert no_side_effects["keys"] == 1


async def test_super_admin_gets_the_tunnel_and_the_script(no_side_effects):
    device = _device()
    resp, _ = await _call(_user(UserRole.SUPER_ADMIN, None), device)
    assert resp.wg_private_key == PRIV


@pytest.mark.parametrize("role", [UserRole.VIEWER, UserRole.NETWORK_AGENT])
async def test_non_admin_user_gets_403_and_no_key_is_minted(role, no_side_effects):
    device = _device()
    db = _db(device)
    with pytest.raises(HTTPException) as ei:
        await _call(_user(role), device, db=db)
    assert ei.value.status_code == 403
    # The gate is before any work: nothing read, nothing minted, nothing persisted,
    # no peer appended to the server config.
    db.execute.assert_not_awaited()
    db.commit.assert_not_awaited()
    assert no_side_effects == {"keys": 0, "peers": [], "ip": 0}
    assert device.wg_private_key is None and device.wg_ip_address is None


async def test_the_403_never_carries_the_private_key(no_side_effects):
    device = _device(priv=PRIV, pub=PUB, ip="10.13.13.7")
    with pytest.raises(HTTPException) as ei:
        await _call(_user(UserRole.VIEWER), device)
    assert PRIV not in str(ei.value.detail)


async def test_scoped_api_key_is_not_role_gated(no_side_effects):
    # API keys are machine-scoped; Task 9 left them alone on provision-script and this
    # mirrors it, so an agent integration does not break.
    resp, _ = await _call(APIKey(organization_id=ORG), _device())
    assert resp.wg_private_key == PRIV


async def test_unscoped_api_key_is_not_role_gated(no_side_effects):
    resp, _ = await _call(APIKey(organization_id=None), _device())
    assert resp.wg_private_key == PRIV


def test_both_provisioning_endpoints_gate_on_the_same_roles():
    # The two endpoints hand out the same secret. If one widens, this goes red rather
    # than leaving the narrower gate as theatre beside an open door.
    import inspect
    pat = "actor.role not in (UserRole.SUPER_ADMIN, UserRole.ORG_ADMIN)"
    for fn in (devices.provision_wireguard, devices.generate_provision_script):
        src = inspect.getsource(fn)
        assert pat in src, fn.__name__
        assert "403" in src, fn.__name__
