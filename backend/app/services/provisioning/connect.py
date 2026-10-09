"""The connect-only script: join a router that already runs a hotspot.

The full script builds a network and so refuses a configured router. This one
is for that router. It adds NetGuard's way in -- the tunnel, the API user, one
accept rule, the payment hosts -- and changes nothing the owner set up: not
their bridge, addressing, DHCP, hotspot server, profiles, firewall drops, other
services or login page. The dashboard adds the Buy button afterwards, on request.

Same delivery rules as the full script (see script.py): one brace block, and a
change here is not trusted until it has run on a CHR under /import and --paste.
"""
from . import sections
from .params import ProvisionParams
from .sections import TAG, WG_INTERFACE, WG_LISTEN_PORT, _INPUT_TERMINAL, _fw_above_stock, _fw_comment, _once


def preflight(p: ProvisionParams) -> list[str]:
    return [
        "# --- preflight ---",
        ':if ([:tonum [:pick [/system resource get version] 0 [:find [/system resource get version] "."]]] < 7) do={ :error "NetGuard: RouterOS 7 or newer is required" }',
        "# This script only connects a hotspot that is already there.",
        ':if ([:len [/ip hotspot find]] = 0) do={ :error "NetGuard: this router has no hotspot; use the full setup script from the NetGuard dashboard instead" }',
        f':if ([:len [/interface wireguard find where name="{WG_INTERFACE}" and comment!="NetGuard" and comment!="NetGuard VPN"]] > 0) do={{ :error "NetGuard: {WG_INTERFACE} already exists and is not ours; refusing to overwrite it" }}',
        "# NetGuard reaches the router at an address in this range; a network of the owner's on the",
        "# same range would make the two indistinguishable.",
        f':if ([:len [/ip address find where network in {p.wg_subnet_cidr} and interface!="{WG_INTERFACE}"]] > 0) do={{ :error "NetGuard: this router already uses {p.wg_subnet_cidr}, which NetGuard needs for its tunnel" }}',
        ':put ("NetGuard preflight: RouterOS " . [/system resource get version])',
    ]


def wireguard(p: ProvisionParams) -> list[str]:
    """The full script's tunnel, on a listen port nothing else on the router holds.

    13231 is RouterOS's own default for a first WireGuard interface, so a
    configured router may well be using it. The router dials out, so the port
    NetGuard's interface listens on is free to differ.
    """
    interface, *rest = sections.wireguard(p)[1:]
    return [
        "# --- wireguard ---",
        f":local ngPort {WG_LISTEN_PORT}",
        f':if ([:len [/interface wireguard find where name="{WG_INTERFACE}"]] > 0) do={{ :set ngPort [/interface wireguard get [find where name="{WG_INTERFACE}"] listen-port] }} '
        f'else={{ :while ([:len [/interface wireguard find where listen-port=$ngPort and name!="{WG_INTERFACE}"]] > 0) do={{ :set ngPort ($ngPort + 1) }} }}',
        interface.replace(f"listen-port={WG_LISTEN_PORT}", "listen-port=$ngPort"),
        *rest,
    ]


def access(p: ProvisionParams) -> list[str]:
    """Let NetGuard in over the tunnel without closing anything to anyone else."""
    return [
        "# --- NetGuard's way in ---",
        "# One accept, placed above the router's own first drop so that drop cannot hide it.",
        "# Scoped to the tunnel interface. No rule of the owner's is moved, changed or removed.",
        _fw_above_stock(f"chain=input action=accept src-address={p.wg_subnet_cidr} in-interface={WG_INTERFACE}",
                        "accept netguard tunnel", _INPUT_TERMINAL),
        "# The API: added to whatever may already use it (a voucher tool, the owner's scripts).",
        "# Off -> on for the tunnel only. On for everyone (no list) -> left exactly as it is.",
        "# On for a list -> the tunnel range is appended. The port is never changed.",
        f":if ([/ip service get api disabled]) do={{ /ip service set api disabled=no address={p.wg_subnet_cidr} }} else={{ "
        ":local ngApi [/ip service get api address]; "
        f':if ([:len $ngApi] > 0 && [:typeof [:find [:tostr $ngApi] "{p.wg_subnet_cidr}"]] = "nil") do={{ '
        f"/ip service set api address=($ngApi , {p.wg_subnet_cidr}) }} }}",
    ]


def walled_garden(p: ProvisionParams) -> list[str]:
    return sections.walled_garden(p, payment_only=True)


def api_user(p: ProvisionParams) -> list[str]:
    # No break-glass account: a full-access login is not ours to add to someone's router.
    return [l for l in sections.api_user(p) if "netguard-recovery" not in l and "break-glass" not in l
            and "admin password you set" not in l]


def summary(p: ProvisionParams) -> list[str]:
    return [
        "# --- summary ---",
        ":delay 8s",
        ':put ""',
        ':put "===== NetGuard connected to this router ====="',
        ':put ("Board:            " . [/system resource get board-name] . "  RouterOS " . [/system resource get version])',
        ':foreach h in=[/ip hotspot find] do={ :put ("Hotspot:          " . [/ip hotspot get $h name] . " on " . [/ip hotspot get $h interface] . " (unchanged)") }',
        f':put "API user:         {p.api_username}  (password: see the NetGuard dashboard)"',
        ':if ([/ip service get api port] != 8728) do={ :put ("API port:         " . [/ip service get api port] . "  -- NOT the default; set this port for the router in NetGuard") }',
        f':put "Tunnel address:   {p.wg_client_ip}  ({WG_INTERFACE} to {p.wg_server_endpoint}:{p.wg_server_port})"',
        f':do {{ :if ([:len [/interface wireguard peers get [find where interface="{WG_INTERFACE}"] last-handshake]] > 0) do={{ :put "Tunnel status:    UP (handshake seen)" }} else={{ :put "Tunnel status:    NOT UP YET - check the uplink; it can take a minute" }} }} on-error={{ :put "Tunnel status:    NOT UP YET - check the uplink; it can take a minute" }}',
        ':put "Your network, hotspot, firewall and login page were not changed."',
        ':put "Next: open this router in NetGuard, set prices, then add the Buy button from the Captive Portal card."',
    ]


SECTION_ORDER = (preflight, walled_garden, api_user, wireguard, access, summary)


def build_connect_script(p: ProvisionParams) -> str:
    out: list[str] = ["{"]
    for fn in SECTION_ORDER:
        out.extend(fn(p))
        out.append("")
    out[-1] = "}"
    out.append("")
    return "\n".join(out)
