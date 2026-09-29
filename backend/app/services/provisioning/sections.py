"""RouterOS config, one function per section.

Each takes a validated ProvisionParams and returns lines of RouterOS CLI.
Pure text: nothing here touches a router, which is what makes it testable.

The RouterOS syntax in this module is written from MikroTik's documentation
and is verified by `scripts/chr-smoke-test.sh`, not by these unit tests. A
unit test proves we emit what we intended; only a real RouterOS parser proves
what we intended is valid.
"""
from .params import ProvisionParams

TAG = 'comment="NetGuard"'


def preflight(p: ProvisionParams) -> list[str]:
    """Refuse RouterOS 6 and any router that already has a hotspot or our tunnel."""
    return [
        "# --- preflight ---",
        "# No :local variables here: at the top level of an imported file they are empty on the next line.",
        ':if ([:tonum [:pick [/system resource get version] 0 [:find [/system resource get version] "."]]] < 7) do={ :error "NetGuard: RouterOS 7 or newer is required" }',
        ':if ([:len [/ip hotspot find]] > 0) do={ :error "NetGuard: this router already has a hotspot; refusing to overwrite it" }',
        ':if ([:len [/interface wireguard find where name="wireguard-netguard"]] > 0) do={ :error "NetGuard: wireguard-netguard already exists; refusing to overwrite it" }',
        ':put ("NetGuard preflight: RouterOS " . [/system resource get version])',
        "# `level` is what RouterOS 7.16 exposes (a CHR rejected `nlevel`); `nlevel` is kept as a fallback for other builds.",
        ':do { :put ("NetGuard preflight: license level " . [/system license get level]) } on-error={ :do { :put ("NetGuard preflight: license level " . [/system license get nlevel]) } on-error={ :put "NetGuard preflight: license level unavailable on this build" } }',
        ':do { :put ("NetGuard preflight: device-mode " . [/system device-mode get mode]) } on-error={ :put "NetGuard preflight: device-mode unavailable on this build" }',
        ':do { :if ([/system device-mode get mode] = "home") do={ :put "NetGuard preflight: NOTE device-mode is home, so hotspot is blocked. Enabling it needs a physical button press or a cold reboot." } } on-error={}',
        ':put ("NetGuard preflight: free memory " . [/system resource get free-memory])',
        ':put ("NetGuard preflight: free disk " . [/system resource get free-hdd-space])',
    ]


def identity_and_clock(p: ProvisionParams) -> list[str]:
    return [
        "# --- identity and clock ---",
        f"/system identity set name={p.site_slug}",
        f"/system clock set time-zone-name={p.timezone}",
        "/system ntp client set enabled=yes",
        "/system ntp client servers add address=time.cloudflare.com " + TAG,
        "/system ntp client servers add address=time.google.com " + TAG,
    ]


def _port_if_present(name: str, bridge: str) -> str:
    return (
        f':if ([:len [/interface find where name="{name}"]] > 0) do={{ '
        f"/interface bridge port add bridge={bridge} interface={name} {TAG} }}"
    )


def bridge(p: ProvisionParams) -> list[str]:
    lines = [
        "# --- bridge ---",
        f"/interface bridge add name={p.bridge_name} {TAG}",
        "# ether1 is the WAN uplink and stays out of the bridge.",
        "# The SFP port is left out too: it is the likely distribution uplink.",
        "# Each port is guarded so a board with fewer ports still gets a working bridge.",
    ]
    for n in range(2, 9):
        lines.append(_port_if_present(f"ether{n}", p.bridge_name))
    # Built-in radio: wifi-qcom boards name it wifi1/wifi2.
    # Older boards using the legacy wireless package name it wlan1.
    for name in ("wifi1", "wifi2", "wlan1"):
        lines.append(_port_if_present(name, p.bridge_name))
    return lines


def addressing(p: ProvisionParams) -> list[str]:
    prefix = p.lan_cidr.split("/")[1]
    network = p.lan_cidr
    return [
        "# --- addressing and DHCP ---",
        f"/ip pool add name=hotspot-pool ranges={p.pool_start}-{p.pool_end} {TAG}",
        f"/ip address add address={p.gateway}/{prefix} interface={p.bridge_name} {TAG}",
        f"/ip dhcp-server add name=hotspot-dhcp interface={p.bridge_name} "
        f"address-pool=hotspot-pool lease-time=4h authoritative=yes disabled=no {TAG}",
        f"/ip dhcp-server network add address={network} gateway={p.gateway} "
        f"dns-server={p.gateway} {TAG}",
    ]


def dns_and_nat(p: ProvisionParams) -> list[str]:
    return [
        "# --- DNS and NAT ---",
        "/ip dns set allow-remote-requests=yes servers=1.1.1.1,8.8.8.8 cache-size=4096KiB",
        f"/ip firewall nat add chain=srcnat action=masquerade "
        f"out-interface={p.wan_interface} {TAG}",
    ]


def hotspot_server(p: ProvisionParams) -> list[str]:
    # No ssl-certificate and no https login: there is no domain, so no trusted
    # cert. Captive-portal detection works over plain HTTP.
    return [
        "# --- hotspot server ---",
        "# /ip hotspot and /ip hotspot profile have no comment property on RouterOS 7.16 (CHR rejected it), so both are untagged.",
        f"/ip hotspot profile add name=netguard hotspot-address={p.gateway} "
        f"dns-name={p.hotspot_dns_name} login-by=http-chap,mac-cookie "
        "http-cookie-lifetime=3d",
        f"/ip hotspot add name=netguard interface={p.bridge_name} "
        f"address-pool=hotspot-pool profile=netguard "
        f"idle-timeout=5m keepalive-timeout=2m login-timeout=5m disabled=no",
    ]


_TIER_COMMON = (
    "add-mac-cookie=yes mac-cookie-timeout=3d idle-timeout=5m keepalive-timeout=2m"
)


def voucher_profiles(p: ProvisionParams) -> list[str]:
    lines = [
        "# --- voucher tiers ---",
        "# /ip hotspot user profile has no comment property on RouterOS 7.16 (CHR rejected it), so tiers are untagged.",
        "# No rate-limit on any tier, by decision: tiers differ by duration and sharing only.",
        "# shared-users=4 means a 500-session licence ceiling is as few as 125 vouchers.",
        "# RouterOS ships a `default` user profile, so it is updated, not added.",
        f"/ip hotspot user profile set [find where name=default] shared-users=4 {_TIER_COMMON}",
    ]
    for name, timeout, shared in (("1-Hour", "1h", 1), ("24-Hours", "24h", 2), ("7-Days", "7d", 4)):
        lines.append(
            f"/ip hotspot user profile add name={name} session-timeout={timeout} "
            f"shared-users={shared} {_TIER_COMMON}"
        )
    return lines


def walled_garden(p: ProvisionParams) -> list[str]:
    lines = ["# --- walled garden ---",
             "# Hosts the phone probes to detect a captive portal; blocked, the portal never pops."]
    for host in ("connectivitycheck.gstatic.com", "captive.apple.com",
                 "www.msftconnecttest.com", p.hotspot_dns_name):
        lines.append(f"/ip hotspot walled-garden add dst-host={host} {TAG}")
    lines.append(
        "/ip hotspot walled-garden ip add dst-address=162.159.200.1 "
        f"action=accept {TAG}"
    )
    lines.append("# TODO PAYMENT PROVIDER: add the provider's hosts here before going live.")
    return lines
