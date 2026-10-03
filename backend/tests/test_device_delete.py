"""Deleting a device must clear every table that references it.

The endpoint did a manual cascade ("Cascade delete (Manual for MVP)") but only
for metrics and alerts. hotspot_sales and voucher_batches also have a NOT NULL
foreign key to devices, so any device with a single voucher sale or batch --
which every router that has ever sold access has -- failed to delete with a
foreign-key violation, surfaced to the operator as a bare "Failed to delete
device." A real device (Mikrotik) had 3 sales and could not be removed.
"""
import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.models import Device, APIKey
from app.routers import devices

pytestmark = pytest.mark.asyncio


def _db(device):
    result = MagicMock()
    result.scalars.return_value.first.return_value = device
    db = MagicMock()
    db.execute = AsyncMock(return_value=result)
    db.delete = AsyncMock()
    db.commit = AsyncMock()
    return db


def _executed_tables(db):
    """Table names targeted by every db.execute(delete(...)) call."""
    tables = []
    for call in db.execute.await_args_list:
        stmt = call.args[0]
        # delete() statements expose the target table; selects are skipped.
        t = getattr(stmt, "table", None)
        if t is not None and getattr(stmt, "is_dml", False):
            tables.append(t.name)
    return tables


async def test_delete_clears_sales_and_batches_not_just_metrics_and_alerts():
    device = Device(id=uuid.uuid4(), name="r1", ip_address="10.13.13.3", site_id=uuid.uuid4())
    db = _db(device)

    await devices.delete_device(str(device.id), db=db, actor=APIKey(organization_id=None))

    tables = _executed_tables(db)
    # Depth-1: directly reference devices.
    assert "hotspot_sales" in tables, (
        "voucher sales not cleared; a device that sold any access cannot be deleted"
    )
    assert "voucher_batches" in tables, "voucher batches not cleared"
    assert "alerts" in tables
    # Depth-2: reference alerts, so they must be cleared before alerts.
    assert "incidents" in tables, (
        "incidents reference alerts; deleting alerts fails while they exist"
    )
    assert "auto_fix_actions" in tables, "auto_fix_actions reference alerts"
    # Grandchildren must come before alerts.
    assert tables.index("incidents") < tables.index("alerts")
    assert tables.index("auto_fix_actions") < tables.index("alerts")
    db.delete.assert_awaited_once_with(device)
    db.commit.assert_awaited_once()


async def test_dependents_are_deleted_before_the_device():
    """The device row must go last, after everything that points at it."""
    device = Device(id=uuid.uuid4(), name="r1", ip_address="10.13.13.3", site_id=uuid.uuid4())
    db = _db(device)

    order = []
    db.execute.side_effect = lambda stmt: order.append(("execute", stmt)) or _db(device).execute.return_value
    # re-wire execute to still return a result with the device for the initial select
    res = MagicMock(); res.scalars.return_value.first.return_value = device
    async def exec_rec(stmt):
        order.append(("execute", stmt)); return res
    db.execute = AsyncMock(side_effect=exec_rec)
    async def del_rec(obj):
        order.append(("delete", obj))
    db.delete = AsyncMock(side_effect=del_rec)

    await devices.delete_device(str(device.id), db=db, actor=APIKey(organization_id=None))

    kinds = [k for k, _ in order]
    assert kinds[-1] == "delete", "the device row was deleted before its dependents"


async def test_missing_device_is_404_and_deletes_nothing():
    db = _db(None)
    with pytest.raises(Exception) as ei:
        await devices.delete_device(str(uuid.uuid4()), db=db, actor=APIKey(organization_id=None))
    assert getattr(ei.value, "status_code", None) == 404
    db.delete.assert_not_awaited()
    db.commit.assert_not_awaited()
