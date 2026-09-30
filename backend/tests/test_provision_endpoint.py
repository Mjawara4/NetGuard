"""HTTP-level tests for POST /devices/{id}/provision-script (Task 9).

Handlers are called directly with a mocked session, as in
test_voucher_job_endpoints.py.

The property guarded hardest: a device with no WireGuard tunnel must get a 409
naming the remedy, never a script carrying a placeholder. Each refusal test
asserts that NO state was written and that build_provision_script was never
reached, so a handler that "fixes up" the input and carries on cannot pass.
"""
import base64
import re
import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import HTTPException

from app.models import APIKey, Device
from app.routers import devices
from app.services.provisioning import script as script_mod

PRIV = base64.b64encode(bytes(range(32))).decode()
SERVER_PUB = base64.b64encode(bytes(range(100, 132))).decode()
assert len(PRIV) == 44
BAD_STRINGS = ("None", "PLACEHOLDER", "NOT_FOUND", "auto-read-from-volume")


def _device(priv=PRIV, ip="10.13.13.7"):
    return Device(id=uuid.uuid4(), name="r1", ip_address="192.0.2.1",
                  site_id=uuid.uuid4(), wg_private_key=priv, wg_ip_address=ip,
                  ssh_username="admin", ssh_password="admin")


def _db(row):
    result = MagicMock()
    result.scalars.return_value.first.return_value = row
    db = MagicMock()
    db.execute = AsyncMock(return_value=result)
    db.add = MagicMock()
    db.commit = AsyncMock()
    return db


@pytest.fixture(autouse=True)
def server_settings(monkeypatch):
    monkeypatch.setattr(devices.settings, "WG_SERVER_PUBLIC_KEY", SERVER_PUB)
    monkeypatch.setattr(devices.settings, "WG_SERVER_ENDPOINT", "203.0.113.1")
    monkeypatch.setattr(devices.settings, "WG_SERVER_PORT", 51820)


@pytest.fixture
def builder_spy(monkeypatch):
    spy = MagicMock(side_effect=script_mod.build_provision_script)
    monkeypatch.setattr(script_mod, "build_provision_script", spy)
    return spy


async def _call(device, **kw):
    kw.setdefault("site_slug", "a-site")
    kw.setdefault("timezone", "Africa/Banjul")
    db = kw.pop("db", None) or _db(device)
    resp = await devices.generate_provision_script(
        str(device.id), db=db, actor=APIKey(organization_id=None), **kw)
    return resp, db


@pytest.mark.parametrize("priv,ip", [(None, "10.13.13.7"), ("", "10.13.13.7"), (PRIV, None)])
async def test_device_without_tunnel_gets_409_and_nothing_is_written(builder_spy, priv, ip):
    device = _device(priv=priv, ip=ip)
    with pytest.raises(HTTPException) as ei:
        await _call(device)
    assert ei.value.status_code == 409
    assert "provision-wireguard" in ei.value.detail
    assert "first" in ei.value.detail.lower()
    builder_spy.assert_not_called()
    # Credentials untouched, nothing committed.
    assert device.ssh_username == "admin" and device.ssh_password == "admin"


async def test_409_detail_is_what_a_client_sees_and_is_clean():
    with pytest.raises(HTTPException) as ei:
        await _call(_device(priv=None))
    for bad in BAD_STRINGS:
        assert bad not in ei.value.detail


async def test_409_does_not_commit():
    db = _db(_device(priv=None))
    with pytest.raises(HTTPException):
        await _call(db.execute.return_value.scalars.return_value.first.return_value, db=db)
    db.commit.assert_not_awaited()


async def test_provisioned_device_returns_script_with_its_real_tunnel_ip():
    device = _device(ip="10.13.13.42")
    resp, _ = await _call(device)
    # The line that assigns the tunnel address, not just any mention of it.
    assert ('/ip address add address=10.13.13.42/24 interface=wireguard-netguard'
            in resp.script)
    assert resp.site_slug == "a-site"
    assert resp.api_username == "netguard"
    assert re.fullmatch(r"[A-Za-z0-9]{24}", resp.api_password)
    assert re.fullmatch(r"[A-Za-z0-9]{24}", resp.admin_password)
    assert resp.api_password != resp.admin_password


async def test_tunnel_private_key_and_server_key_reach_the_script():
    resp, _ = await _call(_device())
    assert PRIV in resp.script
    assert SERVER_PUB in resp.script


async def test_script_contains_no_placeholder_or_none():
    resp, _ = await _call(_device())
    for bad in BAD_STRINGS:
        assert bad not in resp.script


async def test_stored_credentials_are_exactly_what_the_script_and_response_carry():
    device = _device()
    resp, db = await _call(device)
    assert device.ssh_username == "netguard"
    assert device.ssh_password == resp.api_password
    db.commit.assert_awaited_once()
    # The router ends up with precisely what NetGuard stored, on the right account.
    assert f'/user set [find where name=netguard] password="{device.ssh_password}"' in resp.script
    assert f'/user set [find where name=admin] password="{resp.admin_password}"' in resp.script
    assert device.ssh_password != resp.admin_password


async def test_every_call_rotates_so_stored_value_follows_the_latest_script():
    device = _device()
    first, _ = await _call(device)
    second, _ = await _call(device)
    assert first.api_password != second.api_password
    assert device.ssh_password == second.api_password
    assert first.api_password not in second.script
    assert any("rotated" in w.lower() for w in second.warnings)


async def test_bad_site_slug_is_a_400_and_writes_nothing():
    device = _device()
    db = _db(device)
    with pytest.raises(HTTPException) as ei:
        await _call(device, site_slug="Bad Slug!", db=db)
    assert ei.value.status_code == 400
    assert "site_slug" in ei.value.detail
    db.commit.assert_not_awaited()
    assert device.ssh_password == "admin"


async def test_unknown_timezone_is_a_400():
    with pytest.raises(HTTPException) as ei:
        await _call(_device(), timezone="Mars/Olympus")
    assert ei.value.status_code == 400


async def test_unusable_server_key_is_500_not_a_placeholder_script(monkeypatch):
    monkeypatch.setattr(devices.settings, "WG_SERVER_PUBLIC_KEY", "SERVER_PUBLIC_KEY_PLACEHOLDER")
    monkeypatch.setattr(devices.WireGuardService, "get_server_public_key",
                        staticmethod(lambda: (_ for _ in ()).throw(ValueError("missing"))))
    device = _device()
    with pytest.raises(HTTPException) as ei:
        await _call(device)
    assert ei.value.status_code == 500
    assert device.ssh_password == "admin"


async def test_malformed_server_key_from_settings_is_500_not_400(monkeypatch):
    # 44 chars, long enough to skip the fallback, but not base64 of 32 bytes.
    monkeypatch.setattr(devices.settings, "WG_SERVER_PUBLIC_KEY", "auto-read-from-volume-or-manual-" + "x" * 12)
    with pytest.raises(HTTPException) as ei:
        await _call(_device())
    assert ei.value.status_code == 500


async def test_unknown_device_is_404():
    device = _device()
    db = _db(None)
    with pytest.raises(HTTPException) as ei:
        await _call(device, db=db)
    assert ei.value.status_code == 404


async def test_malformed_device_id_is_404():
    with pytest.raises(HTTPException) as ei:
        await devices.generate_provision_script(
            "not-a-uuid", site_slug="a-site", timezone="UTC",
            db=_db(None), actor=APIKey(organization_id=None))
    assert ei.value.status_code == 404
