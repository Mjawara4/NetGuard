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


async def test_a_rotating_call_makes_the_stored_value_follow_the_latest_script():
    """Rotation is now opt-in; when asked for, the stored value must follow it.

    This used to assert that EVERY call rotates. That was the behaviour that let
    a second generation silently invalidate an already-downloaded script, so the
    default is now reuse -- see the reuse tests below. The guarantee that matters
    for a rotating call is unchanged: whatever the newest script sets is what
    NetGuard stores, and the previous password appears nowhere in it.
    """
    device = _device()
    first, _ = await _call(device, rotate=True)
    second, _ = await _call(device, rotate=True)
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


# ---------------------------------------------------------------------------
# Authorisation: role gate, org scoping, and the real route
# ---------------------------------------------------------------------------
import httpx

from app.core.database import get_db
from app.auth.deps import get_authorized_actor
from app.main import app
from app.models import User, UserRole

ORG_X, ORG_Y = uuid.uuid4(), uuid.uuid4()


class _OrgAwareDB:
    """Stands in for Postgres: applies the org predicate the handler put in its query.

    Holds one device belonging to ORG_Y. A query carrying a
    `sites.organization_id = <org>` predicate only sees it when that org is ORG_Y;
    a query with no such predicate sees it regardless. So removing the scoping
    from the handler makes another org's device visible here, as it would in SQL.
    """
    def __init__(self, device, owner_org):
        self.device, self.owner_org = device, owner_org
        self.commit = AsyncMock()
        self.add = MagicMock()

    async def execute(self, stmt):
        compiled = stmt.compile()
        scoped = "sites.organization_id" in str(compiled)
        visible = (not scoped) or self.owner_org in compiled.params.values()
        result = MagicMock()
        result.scalars.return_value.first.return_value = self.device if visible else None
        return result


def _user(role, org):
    return User(id=uuid.uuid4(), email="u@x", hashed_password="x", role=role, organization_id=org)


async def _as(actor, device, owner_org=ORG_Y):
    db = _OrgAwareDB(device, owner_org)
    resp = await devices.generate_provision_script(
        str(device.id), site_slug="a-site", timezone="UTC", db=db, actor=actor)
    return resp, db


async def test_org_admin_of_another_org_gets_404_not_a_script():
    device = _device()
    with pytest.raises(HTTPException) as ei:
        await _as(_user(UserRole.ORG_ADMIN, ORG_X), device)
    assert ei.value.status_code == 404
    assert device.ssh_password == "admin"


async def test_org_admin_succeeds_for_their_own_org_device():
    device = _device()
    resp, db = await _as(_user(UserRole.ORG_ADMIN, ORG_Y), device)
    assert device.ssh_password == resp.api_password
    db.commit.assert_awaited_once()


async def test_super_admin_sees_any_org():
    resp, _ = await _as(_user(UserRole.SUPER_ADMIN, None), _device())
    assert resp.api_username == "netguard"


@pytest.mark.parametrize("role", [UserRole.VIEWER, UserRole.NETWORK_AGENT])
async def test_non_admin_user_gets_403_and_nothing_changes(role):
    device = _device()
    with pytest.raises(HTTPException) as ei:
        await _as(_user(role, ORG_Y), device)   # same org: only the role is wrong
    assert ei.value.status_code == 403
    assert device.ssh_password == "admin"


async def test_scoped_api_key_is_not_role_gated():
    resp, _ = await _as(APIKey(organization_id=ORG_Y), _device())
    assert resp.api_password


async def test_second_warning_tells_operator_ssh_is_refused():
    resp, _ = await _call(_device())
    assert any("API-only" in w and "ssh" in w.lower() for w in resp.warnings)
    assert len(resp.warnings) == 2


def _route(actor, device):
    db = _OrgAwareDB(device, ORG_Y)
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_authorized_actor] = lambda: actor
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://t")


@pytest.fixture
def clean_overrides():
    yield
    app.dependency_overrides.clear()


async def test_route_other_org_is_404_over_http(clean_overrides):
    device = _device()
    async with _route(_user(UserRole.ORG_ADMIN, ORG_X), device) as c:
        r = await c.post(f"/api/v1/inventory/devices/{device.id}/provision-script?site_slug=a-site")
    assert r.status_code == 404
    assert "script" not in r.json()


async def test_route_own_org_is_200_with_full_key_set(clean_overrides):
    device = _device()
    async with _route(_user(UserRole.ORG_ADMIN, ORG_Y), device) as c:
        r = await c.post(f"/api/v1/inventory/devices/{device.id}/provision-script?site_slug=a-site")
    assert r.status_code == 200
    body = r.json()
    assert set(body) == {"device_id", "site_slug", "script", "api_username",
                         "api_password", "admin_password", "warnings"}
    assert device.ssh_password == body["api_password"]


async def test_route_viewer_is_403_over_http(clean_overrides):
    device = _device()
    async with _route(_user(UserRole.VIEWER, ORG_Y), device) as c:
        r = await c.post(f"/api/v1/inventory/devices/{device.id}/provision-script?site_slug=a-site")
    assert r.status_code == 403
    print("VIEWER 403 body:", r.json())


async def test_route_get_is_not_allowed(clean_overrides):
    device = _device()
    async with _route(_user(UserRole.ORG_ADMIN, ORG_Y), device) as c:
        r = await c.get(f"/api/v1/inventory/devices/{device.id}/provision-script?site_slug=a-site")
    assert r.status_code == 405


async def test_stored_address_becomes_the_tunnel_address():
    """Monitoring must dial the tunnel, not whatever address was typed in.

    The script pins SSH and the API to 10.13.13.0/24, so after it runs the
    tunnel address is the ONLY way in. A device added by hand carries its LAN
    default (a real one carried 192.168.88.1), which is unreachable from the
    server -- so monitoring dials the wrong host and fails with no clue why.
    """
    device = _device()
    assert device.ip_address == "192.0.2.1", "fixture precondition"

    resp, _ = await _call(device)

    assert device.ip_address == device.wg_ip_address, (
        f"ip_address stayed {device.ip_address!r} but the router is only "
        f"reachable at {device.wg_ip_address!r} once the script is applied"
    )


async def test_address_is_not_touched_when_there_is_no_tunnel_address():
    """Defensive: never blank out a working address."""
    device = _device()
    device.wg_ip_address = None
    try:
        await _call(device)
    except Exception:
        pass
    assert device.ip_address == "192.0.2.1"


# --- reuse unless explicitly rotating -------------------------------------
#
# Rotating on every call made generating a script twice silently invalidate the
# first file. On a real install the script was generated four times while other
# bugs were fixed; the file applied to the router was from an earlier generation
# than the one the database held, so `netguard` authenticated against neither.
# The router pinged fine and never connected, with no indication why.

GOOD_STORED = "Ab3Cd4Ef5Gh6Ij7Kl8Mn9Op0"   # what generate_api_password produces


def _provisioned(**kw):
    """A device that has already been through provisioning once."""
    d = _device(**kw)
    d.ssh_username = "netguard"
    d.ssh_password = GOOD_STORED
    return d


async def test_second_call_reuses_the_stored_password_so_the_file_still_matches():
    device = _provisioned()
    resp, _ = await _call(device)
    assert resp.api_password == GOOD_STORED, (
        "a second generation minted a new password, which silently invalidates "
        "any script already downloaded"
    )
    assert device.ssh_password == GOOD_STORED
    assert f'password="{GOOD_STORED}"' in resp.script


async def test_two_calls_in_a_row_produce_the_same_credential():
    device = _provisioned()
    first, _ = await _call(device)
    second, _ = await _call(device)
    assert first.api_password == second.api_password
    assert first.script == second.script


async def test_reuse_leaves_the_admin_password_alone():
    """We cannot reproduce it -- it is never stored -- so we must not change it."""
    device = _provisioned()
    resp, _ = await _call(device)
    assert resp.admin_password is None
    assert "/user set [find where name=admin] password=" not in resp.script
    assert any("admin" in w.lower() for w in resp.warnings), (
        "reusing must say that the admin password was left unchanged"
    )


async def test_rotate_mints_a_new_api_password_and_stores_it():
    """Rotation replaces the API credential only.

    It used to reset admin as well. That was removed deliberately: admin is the
    operator's credential, never stored, and rotating it destroyed the only copy
    -- see test_rotate_does_not_touch_admin_on_an_already_provisioned_router.
    """
    device = _provisioned()
    resp, _ = await _call(device, rotate=True)
    assert resp.api_password != GOOD_STORED
    assert re.fullmatch(r"[A-Za-z0-9]{24}", resp.api_password)
    assert device.ssh_password == resp.api_password
    assert f'/user set [find where name=netguard] password="{resp.api_password}"' in resp.script


async def test_first_ever_call_still_mints_both():
    """No stored netguard credential yet, so there is nothing to reuse."""
    device = _device()           # ssh_username="admin"
    resp, _ = await _call(device)
    assert re.fullmatch(r"[A-Za-z0-9]{24}", resp.api_password)
    assert resp.admin_password and re.fullmatch(r"[A-Za-z0-9]{24}", resp.admin_password)
    assert device.ssh_username == "netguard"


async def test_a_stored_password_that_could_not_have_come_from_us_is_replaced():
    """Defensive: never emit a stored value that validation would reject."""
    for junk in ("short", "has spaces in it", 'quote"inside', ""):
        device = _provisioned()
        device.ssh_password = junk
        resp, _ = await _call(device)
        assert resp.api_password != junk
        assert re.fullmatch(r"[A-Za-z0-9]{24}", resp.api_password)


async def test_rotate_default_is_a_real_boolean_not_a_query_object():
    """`x: bool = Query(False)` leaves the default a truthy Query object.

    Over HTTP FastAPI resolves it, so the bug only shows when the function is
    called directly -- which is how every test here calls it, and how the reuse
    branch came to be silently skipped.
    """
    import inspect
    default = inspect.signature(devices.generate_provision_script).parameters["rotate"].default
    assert default is False, f"default is {default!r}, which is truthy"


# --- the admin password is set ONCE, on the first provision only ----------
#
# Asked for after a real lockout. admin is the router's only full-access
# account and NetGuard never stores its password -- it is shown once and that
# is the only copy. Rotating it on a later run therefore replaces the one
# credential the operator holds with one they may not record, and the recovery
# path is a factory reset, which means a site visit.
#
# A factory router ships with a BLANK admin password reachable from the LAN, so
# it must still be set the first time. After that it belongs to the operator.


async def test_rotate_does_not_touch_admin_on_an_already_provisioned_router():
    device = _provisioned()
    resp, _ = await _call(device, rotate=True)
    assert resp.api_password != GOOD_STORED, "rotate must still mint a new API password"
    assert resp.admin_password is None, (
        "rotating replaced the admin password; that is the credential the "
        "operator holds and NetGuard cannot reproduce"
    )
    assert "/user set [find where name=admin] password=" not in resp.script


async def test_first_provision_still_sets_admin_because_factory_is_blank():
    device = _device()           # never provisioned: ssh_username="admin"
    resp, _ = await _call(device)
    assert resp.admin_password, "a factory router would be left with a blank admin password"
    assert f'/user set [find where name=admin] password="{resp.admin_password}"' in resp.script


async def test_admin_is_untouched_on_every_later_call_however_generated():
    device = _device()
    first, _ = await _call(device)                 # first provision: sets admin
    assert first.admin_password
    for kw in ({}, {"rotate": True}, {}, {"rotate": True}):
        later, _ = await _call(device, **kw)
        assert later.admin_password is None, f"admin rotated again with {kw}"
        assert "name=admin] password=" not in later.script
