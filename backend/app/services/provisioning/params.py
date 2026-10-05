"""Validated inputs for the one-shot provisioning script.

Everything that could make a generated script dangerous or silently wrong is
rejected here, before any RouterOS text exists. The section builders in
`sections.py` then take a ProvisionParams and never re-validate.
"""
import base64
import binascii
import ipaddress
import re
from dataclasses import dataclass

# Rejected, not escaped: the generated script runs with full admin rights, and
# an escaping bug in a config language with several quoting contexts is a
# hole. A site name is ours to constrain.
# Use fullmatch() not match() with this pattern: Python's $ anchor matches
# before a trailing newline, so ^..$ would accept "counter\n". fullmatch()
# requires the entire string to match, rejecting newlines at the end.
SLUG_RE = re.compile(r"[a-z0-9][a-z0-9-]{0,30}[a-z0-9]")

# Zones plausible for this deployment. Kept explicit rather than pulling in a
# tz database: RouterOS rejects an unknown zone mid-script, after earlier
# sections have already applied.
KNOWN_TIMEZONES = frozenset({
    "Africa/Banjul", "Africa/Dakar", "Africa/Bissau", "Africa/Conakry",
    "Africa/Freetown", "Africa/Abidjan", "Africa/Accra", "Africa/Lagos",
    "Europe/London", "UTC",
})

WG_SUBNET_CIDR = "10.13.13.0/24"


@dataclass(frozen=True)
class ProvisionParams:
    site_slug: str
    timezone: str
    lan_cidr: str
    gateway: str
    pool_start: str
    pool_end: str
    operator_cidr: str
    wan_interface: str
    bridge_name: str
    wg_private_key: str
    wg_client_ip: str
    wg_server_public_key: str
    wg_server_endpoint: str
    wg_server_port: int
    wg_subnet_cidr: str
    api_username: str
    hotspot_login_user: str
    hotspot_login_password: str
    api_password: str
    # None means "leave the router's admin password alone". It is never stored,
    # The password for the netguard-recovery break-glass account. None means the
    # script leaves recovery alone (a re-run), because the value is never stored
    # and a reused script cannot reproduce the one the installer wrote down.
    recovery_password: str | None
    hotspot_dns_name: str
    device_id: str | None
    portal_plans: tuple[tuple[str, str, str], ...]


def build_params(*, site_slug: str, wg_private_key: str, wg_client_ip: str,
                 wg_server_public_key: str, wg_server_endpoint: str,
                 wg_server_port: int, api_password: str,
                 recovery_password: str | None = None,
                 hotspot_login_user: str = "admin",
                 hotspot_login_password: str = "root",
                 device_id: str | None = None,
                 portal_plans: tuple[tuple[str, str, str], ...] = (),
                 timezone: str = "Africa/Banjul",
                 lan_cidr: str = "10.15.0.0/16") -> ProvisionParams:
    # Validate site slug: use fullmatch to reject trailing newlines
    if not SLUG_RE.fullmatch(site_slug or ""):
        raise ValueError(
            "site_slug must be 2-32 lowercase letters, digits or hyphens, "
            "starting and ending alphanumeric"
        )

    if timezone not in KNOWN_TIMEZONES:
        raise ValueError(f"timezone {timezone!r} is not in KNOWN_TIMEZONES")

    # Validate required fields
    for name, value in (("wg_private_key", wg_private_key),
                        ("wg_server_public_key", wg_server_public_key),
                        ("api_password", api_password),
                        ("wg_server_endpoint", wg_server_endpoint)):
        if not value:
            raise ValueError(f"{name} is required")

    # Validate LAN CIDR
    lan = ipaddress.ip_network(lan_cidr, strict=True)

    # Reject IPv6 networks (MikroTik hotspot is IPv4-only and depends on NAT)
    if lan.version != 4:
        raise ValueError(
            f"lan_cidr must be IPv4; IPv6 is not supported "
            "(MikroTik hotspot depends on NAT, which RouterOS does not support for IPv6)"
        )

    wg = ipaddress.ip_network(WG_SUBNET_CIDR, strict=True)
    if lan.overlaps(wg):
        raise ValueError(
            f"lan_cidr {lan_cidr} would overlap the WireGuard subnet "
            f"{WG_SUBNET_CIDR}; the router would route its own management "
            "tunnel into the customer bridge"
        )

    # Validate LAN is large enough for a sensible pool (at least 1024 addresses = /22 or larger)
    if lan.num_addresses < 1024:
        raise ValueError(
            f"lan_cidr {lan_cidr} must have at least 1024 addresses (prefix /22 or larger)"
        )

    # Validate WireGuard client IP
    try:
        wg_client = ipaddress.ip_address(wg_client_ip)
    except ValueError:
        raise ValueError(f"wg_client_ip {wg_client_ip!r} is not a valid IPv4 address")

    if wg_client.version != 4:
        raise ValueError(f"wg_client_ip must be IPv4, not IPv6")

    wg_subnet = ipaddress.ip_network(WG_SUBNET_CIDR)
    if wg_client not in wg_subnet:
        raise ValueError(
            f"wg_client_ip {wg_client_ip} must be inside the WireGuard subnet {WG_SUBNET_CIDR}"
        )

    # Validate WireGuard server endpoint (IPv4 or hostname)
    # Hostname pattern: alphanumeric, dots, hyphens
    # Use fullmatch() to reject trailing newlines ($ alone would accept them before a newline)
    if not re.compile(r"[A-Za-z0-9.-]+").fullmatch(wg_server_endpoint):
        raise ValueError(
            f"wg_server_endpoint {wg_server_endpoint!r} must be a valid IPv4 address or hostname"
        )

    # Try to parse as IPv4; if it fails, must be a valid hostname (already checked by regex above)
    try:
        ipaddress.ip_address(wg_server_endpoint)
    except ValueError:
        # It's not an IP, so it should be a valid hostname (already validated by regex)
        pass

    # Validate WireGuard keys: base64 of exactly 32 bytes. Length alone is not
    # enough: a 33-byte value passes a "long enough" check and RouterOS then
    # rejects it mid-script (`failure: invalid private key`).
    # Use fullmatch() to reject trailing newlines ($ alone would accept them before a newline)
    base64_pattern = re.compile(r"[A-Za-z0-9+/=]+")
    for name, key in (("wg_private_key", wg_private_key),
                      ("wg_server_public_key", wg_server_public_key)):
        if not base64_pattern.fullmatch(key):
            raise ValueError(f"{name} must be base64-encoded")
        try:
            raw = base64.b64decode(key, validate=True)
        except (binascii.Error, ValueError):
            raise ValueError(f"{name} must be base64-encoded")
        if len(raw) != 32:
            raise ValueError(
                f"{name} must decode to exactly 32 bytes, got {len(raw)}"
            )

    # Validate the two passwords (alphanumeric only; see secrets.py for why).
    # Use fullmatch() to reject trailing newlines ($ alone would accept them before a newline)
    # recovery_password is optional: None means the script leaves netguard-recovery
    # alone (a re-run). An empty string is NOT the same thing and stays an error --
    # it would put `password=""` on a full-access account.
    checked = [("api_password", api_password)]
    if recovery_password is not None:
        checked.append(("recovery_password", recovery_password))
    for name, pw in checked:
        if not re.compile(r"[A-Za-z0-9]+").fullmatch(pw):
            raise ValueError(f"{name} must contain only alphanumeric characters")
    # Distinct, so each secret appears exactly once in the script and one
    # leaked credential is not the other.
    if recovery_password is not None and api_password == recovery_password:
        raise ValueError("recovery_password must differ from api_password")

    # The hotspot login reaches the router inside a quoted RouterOS argument, so a
    # quote, space, semicolon or newline would either break the parse or create a
    # different account than the one reported. Same reasoning as api_password.
    for name, value in (("hotspot_login_user", hotspot_login_user),
                        ("hotspot_login_password", hotspot_login_password)):
        if not value:
            raise ValueError(f"{name} is required")
        if not re.compile(r"[A-Za-z0-9_.-]+").fullmatch(value):
            raise ValueError(
                f"{name} must contain only letters, digits, underscore, dot or hyphen"
            )

    # Validate WireGuard server port (reject bool; bool is subclass of int in Python)
    if isinstance(wg_server_port, bool) or not isinstance(wg_server_port, int) or wg_server_port < 1 or wg_server_port > 65535:
        raise ValueError(
            f"wg_server_port must be an integer between 1 and 65535, got {wg_server_port}"
        )

    # Compute pool boundaries
    gateway = str(lan.network_address + 1)              # 10.15.0.1
    # Pool starts in the second /24 so the first stays free for APs,
    # switches and counter hardware.
    pool_start = str(lan.network_address + 258)          # 10.15.1.2
    pool_end = str(lan.broadcast_address - 257)          # 10.15.254.254

    # The first /24 is outside the DHCP pool: an operator can address into it
    # statically, a hotspot client is never leased into it.
    operator_cidr = f"{lan.network_address}/24"

    # Validate pool invariants
    pool_start_ip = ipaddress.ip_address(pool_start)
    pool_end_ip = ipaddress.ip_address(pool_end)

    if pool_start_ip >= pool_end_ip:
        raise ValueError(
            f"LAN {lan_cidr} too small: computed pool would be invalid "
            f"({pool_start} >= {pool_end})"
        )

    if not (pool_start_ip in lan and pool_end_ip in lan):
        raise ValueError(
            f"LAN {lan_cidr}: computed pool ({pool_start}-{pool_end}) outside the network"
        )

    if pool_start_ip in wg_subnet or pool_end_ip in wg_subnet:
        raise ValueError(
            f"LAN {lan_cidr}: computed pool ({pool_start}-{pool_end}) overlaps "
            f"WireGuard subnet {WG_SUBNET_CIDR}"
        )

    return ProvisionParams(
        site_slug=site_slug, timezone=timezone,
        lan_cidr=lan_cidr, gateway=gateway,
        pool_start=pool_start, pool_end=pool_end,
        operator_cidr=operator_cidr,
        wan_interface="ether1", bridge_name="bridge-hotspot",
        wg_private_key=wg_private_key, wg_client_ip=wg_client_ip,
        wg_server_public_key=wg_server_public_key,
        wg_server_endpoint=wg_server_endpoint, wg_server_port=wg_server_port,
        wg_subnet_cidr=WG_SUBNET_CIDR,
        api_username="netguard", api_password=api_password,
        recovery_password=recovery_password,
        hotspot_login_user=hotspot_login_user,
        hotspot_login_password=hotspot_login_password,
        hotspot_dns_name="login.netguard.local",
        device_id=device_id,
        portal_plans=portal_plans,
    )
