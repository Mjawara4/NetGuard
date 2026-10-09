import uuid
from unittest.mock import AsyncMock

from app.models.core import Device
from app.routers import hotspot
from app.services import portal_keeper
from app.services.provisioning.sections import custom_portal_button

CUSTOM = "<html><body><h1>Kumbija WiFi</h1></body></html>"

OTHER = "2563d54e-924b-49ee-8b32-ca0c79a1c75f"
BACKUP = "test/login.netguard-backup.html"


class Files:
    def __init__(self, files=None):
        self.files = dict(files or {})
        self.writes = []

    def exists(self, name):
        return name in self.files

    def read(self, name):
        return self.files.get(name)

    def write(self, name, contents):
        self.writes.append(name)
        self.files[name] = contents


def _page(router):
    return CUSTOM.replace("</body>", custom_portal_button(router) + "</body>")


def _router(monkeypatch, files, hotspots=({"name": "hs", "directory": "test", "disabled": False},)):
    device = Device(id=uuid.uuid4(), name="r", ip_address="10.0.0.1")
    monkeypatch.setattr(hotspot, "_router_files", lambda d: files)
    monkeypatch.setattr(hotspot, "_router_hotspots", lambda d: list(hotspots))
    return device


def test_a_button_for_another_router_is_repointed_and_the_owners_page_kept(monkeypatch):
    files = Files({"test/login.html": _page(OTHER)})
    device = _router(monkeypatch, files)
    assert portal_keeper.check_router(device) is True
    assert files.files["test/login.html"] == _page(str(device.id))
    assert files.files[BACKUP] == CUSTOM


def test_a_router_whose_button_is_its_own_is_not_written_to(monkeypatch):
    device = _router(monkeypatch, None)
    files = Files({"test/login.html": _page(str(device.id))})
    monkeypatch.setattr(hotspot, "_router_files", lambda d: files)
    assert portal_keeper.check_router(device) is False
    assert files.writes == []


def test_a_page_without_a_button_is_never_given_one(monkeypatch):
    files = Files({"test/login.html": CUSTOM})
    assert portal_keeper.check_router(_router(monkeypatch, files)) is False
    assert files.writes == []


def test_a_router_without_a_hotspot_is_left_alone(monkeypatch):
    files = Files({"test/login.html": _page(OTHER)})
    assert portal_keeper.check_router(_router(monkeypatch, files, hotspots=())) is False
    assert files.writes == []


async def test_an_offline_router_does_not_stop_the_others_being_checked(monkeypatch):
    a, b = Device(id=uuid.uuid4(), name="a"), Device(id=uuid.uuid4(), name="b")
    monkeypatch.setattr(portal_keeper, "_routers", AsyncMock(return_value=[a, b]))

    def check(device):
        if device is a:
            raise OSError("unreachable")
        return True

    monkeypatch.setattr(portal_keeper, "check_router", check)
    assert await portal_keeper.check_all() == 1
