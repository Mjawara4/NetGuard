import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import HTTPException

from app.models.core import Device
from app.routers import hotspot
from app.services.portal_install import NETGUARD_PAGE_MARKER

pytestmark = pytest.mark.asyncio

CUSTOM = "<html><body><h1>Kumbija WiFi</h1></body></html>"


HOTSPOTS = [
    {"name": "staff", "interface": "bridge-staff", "profile": "p1", "disabled": False, "directory": "hotspot"},
    {"name": "guests", "interface": "bridge-guests", "profile": "p2", "disabled": False, "directory": "test"},
]


class Files:
    def __init__(self, files=None, unreadable=()):
        self.files, self.unreadable, self.writes = dict(files or {}), set(unreadable), []

    def exists(self, name):
        return name in self.files

    def read(self, name):
        return None if name in self.unreadable else self.files.get(name)

    def write(self, name, contents):
        self.writes.append(name)
        self.files[name] = contents


def _setup(monkeypatch, files, template=None):
    device = Device(id=uuid.uuid4(), site_id=uuid.uuid4(), name="r", ip_address="10.0.0.1")
    device.voucher_template = template
    db = MagicMock()
    db.commit = AsyncMock()
    monkeypatch.setattr(hotspot, "_portal_device", AsyncMock(return_value=device))
    monkeypatch.setattr(hotspot, "_active_hotspot_directory", lambda d: "test")
    monkeypatch.setattr(hotspot, "_router_files", lambda d: files)
    monkeypatch.setattr(hotspot, "_router_hotspots", lambda d: HOTSPOTS)
    return device, db


async def test_a_router_with_no_saved_choice_is_the_owners_not_netguards(monkeypatch):
    device, db = _setup(monkeypatch, Files())
    out = await hotspot.get_portal_config(str(device.id), db=db, actor=None)
    assert out["mode"] == "custom"


async def test_choosing_custom_only_records_the_choice(monkeypatch):
    files = Files({"test/login.html": CUSTOM})
    device, db = _setup(monkeypatch, files, {"portal_mode": "netguard"})
    await hotspot.set_portal_mode(str(device.id), hotspot.PortalModeUpdate(mode="custom"), db=db, actor=None)
    assert files.writes == []
    assert device.voucher_template["portal_mode"] == "custom"


async def test_choosing_netguard_installs_its_page_and_keeps_the_owners(monkeypatch):
    files = Files({"test/login.html": CUSTOM})
    device, db = _setup(monkeypatch, files, {"profile_pricing": {"3-Hours": {"price": 10}}})
    out = await hotspot.set_portal_mode(str(device.id), hotspot.PortalModeUpdate(mode="netguard"), db=db, actor=None)
    assert out["mode"] == "netguard"
    page = files.files["test/login.html"]
    assert NETGUARD_PAGE_MARKER in page and "3-Hours" in page
    # Written through the API, not a script: RouterOS variables must be literal.
    assert "$(link-login-only)" in page and "\\$(" not in page
    assert files.files["test/login.netguard-backup.html"] == CUSTOM
    assert device.voucher_template["portal_mode"] == "netguard"
    assert device.voucher_template["profile_pricing"] == {"3-Hours": {"price": 10}}


async def test_choosing_netguard_is_refused_when_the_owners_page_cannot_be_kept(monkeypatch):
    files = Files({"test/login.html": CUSTOM}, unreadable={"test/login.html"})
    device, db = _setup(monkeypatch, files, {"portal_mode": "custom"})
    with pytest.raises(HTTPException) as error:
        await hotspot.set_portal_mode(str(device.id), hotspot.PortalModeUpdate(mode="netguard"), db=db, actor=None)
    assert error.value.status_code == 409
    assert files.writes == []
    assert device.voucher_template["portal_mode"] == "custom"
    db.commit.assert_not_awaited()


async def test_install_custom_adds_the_button_to_the_folder_in_use(monkeypatch):
    files = Files({"test/login.html": CUSTOM})
    device, db = _setup(monkeypatch, files)
    out = await hotspot.install_custom_portal_support(str(device.id), db=db, actor=None)
    assert out["directory"] == "test"
    assert "NETGUARD-BUY-START" in files.files["test/login.html"]
    assert f"router={device.id}" in files.files["test/login.html"]
    assert files.files["test/login.netguard-backup.html"] == CUSTOM
    assert device.voucher_template["portal_mode"] == "custom"


async def test_install_custom_reports_a_refusal_as_a_conflict(monkeypatch):
    files = Files({"test/login.html": CUSTOM}, unreadable={"test/login.html"})
    device, db = _setup(monkeypatch, files)
    with pytest.raises(HTTPException) as error:
        await hotspot.install_custom_portal_support(str(device.id), db=db, actor=None)
    assert error.value.status_code == 409
    assert files.writes == []


async def test_restore_puts_the_owners_page_back_and_marks_the_router_custom(monkeypatch):
    files = Files({"test/login.html": "<!-- NETGUARD-PORTAL -->", "test/login.netguard-backup.html": CUSTOM})
    device, db = _setup(monkeypatch, files, {"portal_mode": "netguard"})
    await hotspot.restore_custom_portal(str(device.id), db=db, actor=None)
    assert files.files["test/login.html"] == CUSTOM
    assert device.voucher_template["portal_mode"] == "custom"


async def test_status_says_what_the_router_is_actually_serving(monkeypatch):
    files = Files({"test/login.html": CUSTOM})
    device, db = _setup(monkeypatch, files)
    _folders(monkeypatch, ["test/login.html"], active="test")
    out = await hotspot.get_portal_status(str(device.id), db=db, actor=None)
    assert out == {"directory": "test", "login_page": "custom", "has_backup": False,
                   "folders": ["test"], "chosen_directory": "", "attention": None,
                   "hotspot": "staff",
                   "hotspots": [{"name": "staff", "interface": "bridge-staff", "directory": "hotspot", "disabled": False},
                                {"name": "guests", "interface": "bridge-guests", "directory": "test", "disabled": False}]}


def test_large_pages_are_read_with_get_not_print(monkeypatch):
    # `/file print` omits `contents` above ~4 KB; `/file get value-name=contents`
    # returns the whole file. Real portal pages are 20 KB and more.
    device = Device(id=uuid.uuid4(), site_id=uuid.uuid4(), name="r", ip_address="10.0.0.1")
    big = "<html>" + "x" * 20000 + "</html>"
    resource = MagicMock()

    def call(command, arguments=None, queries=None):
        if command == "print":
            return [{"id": b"*7", "name": b"test/login.html"}]
        assert (command, arguments) == ("get", {".id": b"*7", "value-name": b"contents"})
        return MagicMock(done_message={"ret": big.encode()})

    resource.call.side_effect = call
    connection = MagicMock()
    connection.get_api.return_value.get_binary_resource.return_value = resource
    monkeypatch.setattr(hotspot, "_portal_api", lambda d: connection)

    assert hotspot._router_files(device).read("test/login.html") == big
    connection.disconnect.assert_called()


def test_a_missing_file_reads_as_absent(monkeypatch):
    device = Device(id=uuid.uuid4(), site_id=uuid.uuid4(), name="r", ip_address="10.0.0.1")
    resource = MagicMock()
    resource.call.return_value = []
    connection = MagicMock()
    connection.get_api.return_value.get_binary_resource.return_value = resource
    monkeypatch.setattr(hotspot, "_portal_api", lambda d: connection)
    files = hotspot._router_files(device)
    assert files.exists("test/login.html") is False
    assert files.read("test/login.html") is None


async def test_saving_the_voucher_template_never_changes_the_portal_choice(monkeypatch):
    # The template form knows nothing about the portal. Saving prices used to
    # rewrite the whole record and silently flip the router back to "netguard".
    device = Device(id=uuid.uuid4(), site_id=uuid.uuid4(), name="r", ip_address="10.0.0.1")
    device.voucher_template = {"portal_mode": "custom", "header_text": "old"}
    result = MagicMock()
    result.scalars.return_value.first.return_value = device
    db = MagicMock()
    db.execute = AsyncMock(return_value=result)
    db.commit = AsyncMock()
    actor = hotspot.User(role=hotspot.UserRole.SUPER_ADMIN)

    await hotspot.update_voucher_template(
        str(device.id), hotspot.VoucherTemplate(header_text="new"), db=db, actor=actor)
    assert device.voucher_template["header_text"] == "new"
    assert device.voucher_template["portal_mode"] == "custom"


async def test_a_template_save_cannot_switch_a_router_to_netguards_portal(monkeypatch):
    device = Device(id=uuid.uuid4(), site_id=uuid.uuid4(), name="r", ip_address="10.0.0.1")
    device.voucher_template = None
    result = MagicMock()
    result.scalars.return_value.first.return_value = device
    db = MagicMock()
    db.execute = AsyncMock(return_value=result)
    db.commit = AsyncMock()
    actor = hotspot.User(role=hotspot.UserRole.SUPER_ADMIN)

    await hotspot.update_voucher_template(
        str(device.id), hotspot.VoucherTemplate(portal_mode="netguard"), db=db, actor=actor)
    assert device.voucher_template.get("portal_mode") != "netguard"


# --- the owner's portal folder ---

def _folders(monkeypatch, names, active="hotspot"):
    state = {"active": active, "set": []}
    monkeypatch.setattr(hotspot, "_active_hotspot_directory", lambda d: state["active"])
    monkeypatch.setattr(hotspot, "_router_file_names", lambda d: names)

    def set_dir(device, directory):
        state["set"].append(directory)
        state["active"] = directory

    monkeypatch.setattr(hotspot, "_set_hotspot_directory", set_dir)
    return state


NAMES = ["hotspot/login.html", "test/login.html", "test/xml/login.html"]


async def test_status_lists_the_portal_folders_and_the_owners_choice(monkeypatch):
    files = Files({"test/login.html": CUSTOM})
    device, db = _setup(monkeypatch, files, {"portal_directory": "test"})
    _folders(monkeypatch, NAMES, active="test")
    out = await hotspot.get_portal_status(str(device.id), db=db, actor=None)
    assert out["folders"] == ["hotspot", "test"]
    assert out["chosen_directory"] == "test"
    assert out["attention"] is None


async def test_status_flags_a_router_that_went_back_to_another_folder(monkeypatch):
    files = Files({"hotspot/login.html": NETGUARD_PAGE_MARKER, "test/login.html": CUSTOM})
    device, db = _setup(monkeypatch, files, {"portal_directory": "test"})
    _folders(monkeypatch, NAMES, active="hotspot")
    out = await hotspot.get_portal_status(str(device.id), db=db, actor=None)
    assert out["directory"] == "hotspot"
    assert out["attention"] == "wrong_folder"


async def test_choosing_a_folder_points_the_hotspot_at_it_and_remembers_it(monkeypatch):
    files = Files({"test/login.html": CUSTOM})
    device, db = _setup(monkeypatch, files, {"profile_pricing": {"3-Hours": {"price": 10}}})
    state = _folders(monkeypatch, NAMES)
    out = await hotspot.set_portal_folder(str(device.id), hotspot.PortalFolderUpdate(directory="test"), db=db, actor=None)
    assert state["set"] == ["test"]
    assert out["directory"] == "test"
    assert device.voucher_template["portal_directory"] == "test"
    assert device.voucher_template["portal_mode"] == "custom"
    assert device.voucher_template["profile_pricing"] == {"3-Hours": {"price": 10}}
    assert files.writes == []


async def test_a_folder_without_a_login_page_is_refused(monkeypatch):
    device, db = _setup(monkeypatch, Files(), {"portal_directory": "test"})
    state = _folders(monkeypatch, NAMES)
    with pytest.raises(HTTPException) as error:
        await hotspot.set_portal_folder(str(device.id), hotspot.PortalFolderUpdate(directory="skins"), db=db, actor=None)
    assert error.value.status_code == 409
    assert state["set"] == []
    assert device.voucher_template["portal_directory"] == "test"
    db.commit.assert_not_awaited()


async def test_adding_the_buy_button_remembers_the_folder_it_was_added_in(monkeypatch):
    files = Files({"test/login.html": CUSTOM})
    device, db = _setup(monkeypatch, files)
    await hotspot.install_custom_portal_support(str(device.id), db=db, actor=None)
    assert device.voucher_template["portal_directory"] == "test"


async def test_saving_the_voucher_template_keeps_the_portal_folder(monkeypatch):
    device, db = _setup(monkeypatch, Files(), {"portal_mode": "custom", "portal_directory": "test"})
    result = MagicMock()
    result.scalars.return_value.first.return_value = device
    db.execute = AsyncMock(return_value=result)
    actor = hotspot.User(role=hotspot.UserRole.SUPER_ADMIN)
    await hotspot.update_voucher_template(str(device.id), hotspot.VoucherTemplate(), db=db, actor=actor)
    assert device.voucher_template["portal_directory"] == "test"


# --- which hotspot, on a router with several ---

async def test_choosing_a_hotspot_is_remembered_and_writes_nothing_to_the_router(monkeypatch):
    files = Files({"test/login.html": CUSTOM})
    device, db = _setup(monkeypatch, files, {"portal_mode": "custom", "portal_directory": "hotspot"})
    out = await hotspot.set_portal_hotspot(str(device.id), hotspot.PortalHotspotUpdate(name="guests"), db=db, actor=None)
    assert out == {"status": "saved", "hotspot": "guests", "directory": "test"}
    assert device.voucher_template["portal_hotspot"] == "guests"
    assert device.voucher_template["portal_mode"] == "custom"
    # The folder remembered for the other hotspot does not carry over.
    assert "portal_directory" not in device.voucher_template
    assert files.writes == []


async def test_a_hotspot_the_router_does_not_have_is_refused(monkeypatch):
    device, db = _setup(monkeypatch, Files(), {"portal_hotspot": "staff"})
    with pytest.raises(HTTPException) as error:
        await hotspot.set_portal_hotspot(str(device.id), hotspot.PortalHotspotUpdate(name="nope"), db=db, actor=None)
    assert error.value.status_code == 409
    assert device.voucher_template["portal_hotspot"] == "staff"
    db.commit.assert_not_awaited()


def test_the_portal_folder_is_read_from_the_hotspot_the_owner_chose(monkeypatch):
    device = Device(id=uuid.uuid4(), site_id=uuid.uuid4(), name="r", ip_address="10.0.0.1")
    monkeypatch.setattr(hotspot, "_router_hotspots", lambda d: HOTSPOTS)
    assert hotspot._active_hotspot_directory(device) == "hotspot"
    device.voucher_template = {"portal_hotspot": "guests"}
    assert hotspot._active_hotspot_directory(device) == "test"


async def test_saving_the_voucher_template_keeps_the_chosen_hotspot(monkeypatch):
    device, db = _setup(monkeypatch, Files(), {"portal_hotspot": "guests"})
    result = MagicMock()
    result.scalars.return_value.first.return_value = device
    db.execute = AsyncMock(return_value=result)
    await hotspot.update_voucher_template(
        str(device.id), hotspot.VoucherTemplate(), db=db, actor=hotspot.User(role=hotspot.UserRole.SUPER_ADMIN))
    assert device.voucher_template["portal_hotspot"] == "guests"
