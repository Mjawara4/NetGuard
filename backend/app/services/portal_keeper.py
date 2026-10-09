"""Keeps every router's Buy button pointing at that router.

A portal folder outlives a router reset and gets copied from router to router,
and the button inside it names the router it was made for. Left alone, the page
sells another router's plans. Nobody has to notice: this looks at each router
in turn and re-points a button that names a different one.

Only NetGuard's own button is rewritten, and only when it is already there.
"""
import asyncio
import logging

from sqlalchemy import select

from app.core.database import AsyncSessionLocal
from app.models.core import Device
from app.services import portal_install

logger = logging.getLogger(__name__)

FIRST_CHECK_AFTER = 60
CHECK_EVERY = 600


def check_router(device) -> bool:
    """Re-point one router's button if it names another router. True if it did."""
    from app.routers import hotspot
    from app.services.provisioning.sections import custom_portal_button

    active = portal_install.pick_hotspot(hotspot._router_hotspots(device), hotspot._saved_portal_hotspot(device))
    if not active or not portal_install.is_safe_directory(active["directory"]):
        return False
    return portal_install.repoint_buy_button(
        hotspot._router_files(device), active["directory"], str(device.id), custom_portal_button(str(device.id)))


async def _routers():
    async with AsyncSessionLocal() as db:
        devices = (await db.execute(select(Device).where(
            Device.archived_at.is_(None), Device.is_active.is_(True), Device.device_type == "router"))).scalars().all()
        # Detached: reading a router decrypts its secrets in place, which must never be saved back.
        db.expunge_all()
        return devices


async def check_all() -> int:
    fixed = 0
    for device in await _routers():
        try:
            if await asyncio.to_thread(check_router, device):
                fixed += 1
                logger.info("Buy button on %s re-pointed at its own router", device.name)
        except Exception as exc:
            # An offline router is ordinary; it is looked at again next round.
            logger.debug("Buy button check skipped for %s: %s", device.name, exc)
    return fixed


async def run_forever():
    await asyncio.sleep(FIRST_CHECK_AFTER)
    while True:
        try:
            await check_all()
        except Exception:
            logger.exception("Buy button check failed")
        await asyncio.sleep(CHECK_EVERY)
