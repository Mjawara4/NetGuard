"""The endpoint the monitor agent needs to authenticate to a router.

Why it exists: the agent read devices from GET /inventory/devices and did

    pwd = device.get('ssh_password') or SSH_PASSWORD

but DeviceResponse strips ssh_password ("excluded - sensitive"), so that key
was ALWAYS absent and the agent fell back to SSH_PASSWORD, defaulting to the
literal "admin". It therefore authenticated as `netguard` with the wrong
password on every router whose credential was provisioned rather than global --
which is every router the setup script touches.

The symptom was CPU/memory/uptime permanently N/A and a login failure in the
router's log every 40 seconds, while the device pinged perfectly. Setting the
password on the router AND in NetGuard changed nothing, because neither was the
value being sent.

This is credential material, so it is a separate endpoint restricted to machine
actors rather than a flag on the device list.
"""
import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import HTTPException

from app.models import Device, APIKey
from app.models.core import User, UserRole
from app.routers import devices

pytestmark = pytest.mark.asyncio


def _device(pwd="Secret23Secret23Secret23", user="netguard"):
    return Device(id=uuid.uuid4(), name="r1", ip_address="10.13.13.3",
                  site_id=uuid.uuid4(), ssh_username=user, ssh_password=pwd,
                  ssh_port=8728)


def _db(rows):
    result = MagicMock()
    result.scalars.return_value.all.return_value = rows
    db = MagicMock()
    db.execute = AsyncMock(return_value=result)
    return db


async def _call(rows, actor):
    return await devices.get_device_credentials(db=_db(rows), actor=actor)


async def test_machine_actor_gets_the_credential_the_router_was_given():
    d = _device()
    out = await _call([d], APIKey(organization_id=None))
    assert len(out) == 1
    assert out[0].ssh_username == "netguard"
    assert out[0].ssh_password == "Secret23Secret23Secret23", (
        "the agent cannot authenticate without the stored password"
    )
    assert out[0].ssh_port == 8728
    assert str(out[0].id) == str(d.id)


async def test_a_human_cannot_read_router_passwords_here():
    """Operators have no use for this; it exists for the agent."""
    for role in (UserRole.SUPER_ADMIN, UserRole.ORG_ADMIN):
        with pytest.raises(HTTPException) as ei:
            await _call([_device()], User(role=role, organization_id=uuid.uuid4()))
        assert ei.value.status_code == 403


async def test_devices_without_a_stored_credential_are_left_out():
    """Nothing to send, and an empty password would look like a real one."""
    out = await _call([_device(pwd=None), _device(pwd=""), _device()], APIKey(organization_id=None))
    assert len(out) == 1


async def test_the_response_carries_nothing_beyond_what_the_agent_needs():
    out = await _call([_device()], APIKey(organization_id=None))
    fields = set(out[0].model_dump().keys())
    assert fields == {"id", "ip_address", "ssh_username", "ssh_password", "ssh_port"}, fields
