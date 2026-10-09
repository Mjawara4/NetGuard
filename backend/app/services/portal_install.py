"""Changing a router's captive-portal login page without losing the owner's.

The login page belongs to whoever runs the hotspot. NetGuard may add one marked
Buy button to it, or replace it when the owner explicitly chooses NetGuard's
portal -- and in both cases keeps a copy of the owner's page first, and changes
nothing at all if it cannot.

`files` is anything with exists(name), read(name) -> str | None and
write(name, contents); read returns None when the router has the file but will
not hand over its contents.
"""

import re

NETGUARD_PAGE_MARKER = "<!-- NETGUARD-PORTAL -->"
# Pages NetGuard installed before the marker existed.
_LEGACY_NETGUARD_TEXT = "Choose a plan and pay securely with Modem Pay."
_BUTTON_RE = re.compile(r"<!-- NETGUARD-BUY-START -->.*?<!-- NETGUARD-BUY-END -->", re.DOTALL)


# What a folder name may contain: it ends up quoted inside the setup script.
_SAFE_DIRECTORY_RE = re.compile(r"[A-Za-z0-9._-]+(/[A-Za-z0-9._-]+)*")


def is_safe_directory(directory) -> bool:
    return bool(directory) and ".." not in directory and bool(_SAFE_DIRECTORY_RE.fullmatch(directory))


class PortalError(Exception):
    """The portal was left exactly as it was; the message says why."""


def login_name(directory: str) -> str:
    return f"{directory}/login.html"


def backup_name(directory: str) -> str:
    return f"{directory}/login.netguard-backup.html"


def is_netguard_page(html) -> bool:
    return bool(html) and (NETGUARD_PAGE_MARKER in html or _LEGACY_NETGUARD_TEXT in html)


def portal_folders(names) -> list[str]:
    """Folders on the router that hold a login page, i.e. could be a portal.

    A portal's own sub-folders (xml/ carries a login.html too) are not portals.
    """
    holding = {name[:-len("/login.html")] for name in names if name.endswith("/login.html")}
    return sorted(d for d in holding
                  if is_safe_directory(d) and d.rsplit("/", 1)[0] not in holding - {d})


def pick_hotspot(hotspots, saved: str = ""):
    """The hotspot NetGuard's portal work applies to on a router with several.

    The one the owner named if the router still has it, else the first that is
    enabled, else the first. None when the router has no hotspot.
    """
    by_name = next((h for h in hotspots if saved and h.get("name") == saved), None)
    return by_name or next((h for h in hotspots if not h.get("disabled")), None) or (hotspots[0] if hotspots else None)


def attention(mode: str, chosen: str, status: dict):
    """Why the router is not showing what the owner chose, or None.

    Nothing is changed on the strength of this: it is only shown to the owner.
    """
    if chosen and status.get("directory") != chosen:
        return "wrong_folder"
    if mode == "custom" and status.get("login_page") == "netguard":
        return "netguard_page"
    if status.get("buy_button") == "other":
        return "other_router_button"
    return None


_BUTTON_ROUTER_RE = re.compile(r"/buy\?router=([^&\"'\s]+)")


def buy_button(html, device_id: str) -> str:
    """Whose Buy button a page carries: "none", "this" router's or an "other" one's.

    A portal folder outlives a router reset and can be copied between routers,
    and it carries its button with it. A button for another router sends
    customers to that router's plans, or to nothing once it has been removed.
    """
    block = _BUTTON_RE.search(html or "")
    if not block:
        return "none"
    owners = set(_BUTTON_ROUTER_RE.findall(block.group(0)))
    return "this" if owners == {str(device_id)} else "other"


def without_buy_button(html: str) -> str:
    return _BUTTON_RE.sub("", html)


def with_buy_button(html: str, button: str) -> str:
    html = without_buy_button(html)
    pos = html.lower().rfind("</body>")
    return html[:pos] + button + html[pos:] if pos >= 0 else html + button


def _users_backup(files, directory):
    """The owner's saved page, or None. A copy of NetGuard's page is not one."""
    saved = files.read(backup_name(directory))
    return saved if saved and not is_netguard_page(saved) else None


def describe(files, directory: str, device_id: str = "") -> dict:
    name = login_name(directory)
    html = None
    if not files.exists(name):
        page = "missing"
    else:
        html = files.read(name)
        page = "unreadable" if html is None else "netguard" if is_netguard_page(html) else "custom"
    return {"directory": directory, "login_page": page,
            "has_backup": _users_backup(files, directory) is not None,
            "buy_button": buy_button(html, device_id) if page == "custom" else "none"}


def _write_verified(files, name: str, contents: str) -> None:
    files.write(name, contents)
    if files.read(name) != contents:
        raise PortalError(f"The router did not store {name} intact")


def _keep_users_page(files, directory: str, page: str) -> None:
    """Save the owner's page (minus our button) unless a copy already exists."""
    if _users_backup(files, directory) is not None:
        return
    try:
        _write_verified(files, backup_name(directory), without_buy_button(page))
    except PortalError as exc:
        raise PortalError(f"{exc}; your login page was not changed") from exc


def install_custom(files, directory: str, button: str) -> dict:
    name = login_name(directory)
    if not files.exists(name):
        raise PortalError(f"{name} was not found on the router")
    current = files.read(name)
    if current is None:
        raise PortalError("The router did not return your login page, so nothing was changed")
    if is_netguard_page(current):
        original = _users_backup(files, directory)
        if original is None:
            raise PortalError(
                f"{name} is NetGuard's own page and the router has no copy of yours. "
                "Point the hotspot at the folder holding your portal, then try again.")
    else:
        original = without_buy_button(current)
        _keep_users_page(files, directory, current)
    updated = with_buy_button(original, button)
    if updated != current:
        _write_verified(files, name, updated)
    return {"directory": directory, "backup": backup_name(directory)}


def repoint_buy_button(files, directory: str, device_id: str, button: str) -> bool:
    """Make a Buy button that belongs to another router this router's. True if it did.

    A page with no button is left without one: adding it is the owner's call.
    """
    if describe(files, directory, device_id)["buy_button"] != "other":
        return False
    install_custom(files, directory, button)
    return True


def install_netguard(files, directory: str, page: str) -> dict:
    name = login_name(directory)
    if files.exists(name):
        current = files.read(name)
        if current is None:
            raise PortalError(
                "The router did not return your current login page, so NetGuard could not "
                "keep a copy of it. Nothing was changed.")
        if not is_netguard_page(current):
            _keep_users_page(files, directory, current)
    files.write(name, page)
    return {"directory": directory, "backup": backup_name(directory)}


def restore(files, directory: str) -> dict:
    original = _users_backup(files, directory)
    if original is None:
        raise PortalError("The router has no saved copy of your own login page")
    _write_verified(files, login_name(directory), original)
    return {"directory": directory}
