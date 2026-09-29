"""Validated inputs for the one-shot provisioning script.

Everything that could make a generated script dangerous or silently wrong is
rejected here, before any RouterOS text exists. The section builders in
`sections.py` then take a ProvisionParams and never re-validate.
"""
import ipaddress
import re
from dataclasses import dataclass

# Rejected, not escaped: the generated script runs with full admin rights, and
# an escaping bug in a config language with several quoting contexts is a
# hole. A site name is ours to constrain.
SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9-]{0,30}[a-z0-9]$")

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
    wan_interface: str
    bridge_name: str
    wg_private_key: str
    wg_client_ip: str
    wg_server_public_key: str
    wg_server_endpoint: str
    wg_server_port: int
    wg_subnet_cidr: str
    api_username: str
    api_password: str
    hotspot_dns_name: str


def build_params(*, site_slug: str, wg_private_key: str, wg_client_ip: str,
                 wg_server_public_key: str, wg_server_endpoint: str,
                 wg_server_port: int, api_password: str,
                 timezone: str = "Africa/Banjul",
                 lan_cidr: str = "10.15.0.0/16") -> ProvisionParams:
    if not SLUG_RE.match(site_slug or ""):
        raise ValueError(
            "site_slug must be 2-32 lowercase letters, digits or hyphens, "
            "starting and ending alphanumeric"
        )
    if timezone not in KNOWN_TIMEZONES:
        raise ValueError(f"timezone {timezone!r} is not in KNOWN_TIMEZONES")
    for name, value in (("wg_private_key", wg_private_key),
                        ("wg_server_public_key", wg_server_public_key),
                        ("api_password", api_password),
                        ("wg_server_endpoint", wg_server_endpoint)):
        if not value:
            raise ValueError(f"{name} is required")

    lan = ipaddress.ip_network(lan_cidr, strict=True)
    wg = ipaddress.ip_network(WG_SUBNET_CIDR, strict=True)
    if lan.overlaps(wg):
        raise ValueError(
            f"lan_cidr {lan_cidr} would overlap the WireGuard subnet "
            f"{WG_SUBNET_CIDR}; the router would route its own management "
            "tunnel into the customer bridge"
        )

    gateway = str(lan.network_address + 1)              # 10.15.0.1
    # Pool starts in the second /24 so the first stays free for APs,
    # switches and counter hardware.
    pool_start = str(lan.network_address + 258)          # 10.15.1.2
    pool_end = str(lan.broadcast_address - 257)          # 10.15.254.254

    return ProvisionParams(
        site_slug=site_slug, timezone=timezone,
        lan_cidr=lan_cidr, gateway=gateway,
        pool_start=pool_start, pool_end=pool_end,
        wan_interface="ether1", bridge_name="bridge-hotspot",
        wg_private_key=wg_private_key, wg_client_ip=wg_client_ip,
        wg_server_public_key=wg_server_public_key,
        wg_server_endpoint=wg_server_endpoint, wg_server_port=wg_server_port,
        wg_subnet_cidr=WG_SUBNET_CIDR,
        api_username="netguard", api_password=api_password,
        hotspot_dns_name="login.netguard.local",
    )
