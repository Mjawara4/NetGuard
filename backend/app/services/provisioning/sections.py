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
    lines.append("# TODO PAYMENT PROVIDER: add the provider's hosts here before going live.")
    return lines


def _fw_comment(name: str) -> str:
    return f'comment="NetGuard fw: {name}"'


def firewall(p: ProvisionParams) -> list[str]:
    """Input-chain firewall, service pinning and discovery hardening.

    Apply this section LAST: it ends by dropping everything arriving on the
    WAN interface, so anything that reaches the router over that path (an SSH
    session driving the import) can no longer open new connections afterwards.
    Established connections survive because rule 1 accepts them.
    """
    drop_all = "drop wan input"
    wan = p.wan_interface
    # The terminal rule is added first, then every other rule is inserted
    # before it, in reading order. Order is therefore explicit, not
    # positional-by-accident, and does not depend on what the router already had.
    def before(_rule: str = drop_all) -> str:
        return f'place-before=[find where comment="NetGuard fw: {drop_all}"]'

    lines = [
        "# --- firewall ---",
        "# Terminal rule first; every other rule is placed before it, in order.",
        f"/ip firewall filter add chain=input action=drop in-interface={wan} {_fw_comment(drop_all)}",
        f"/ip firewall filter add chain=input action=accept connection-state=established,related,untracked {before(drop_all)} {_fw_comment('accept established')}",
        f"/ip firewall filter add chain=input action=drop connection-state=invalid {before(drop_all)} {_fw_comment('drop invalid')}",
        f"/ip firewall filter add chain=input action=accept src-address={p.wg_subnet_cidr} {before(drop_all)} {_fw_comment('accept netguard tunnel')}",
        f"/ip firewall filter add chain=input action=accept protocol=icmp {before(drop_all)} {_fw_comment('accept icmp')}",
        "# allow-remote-requests=yes is needed for LAN clients; without these the WAN could use the router as an open resolver.",
        f"/ip firewall filter add chain=input action=drop protocol=udp dst-port=53 in-interface={wan} {before(drop_all)} {_fw_comment('drop wan dns udp')}",
        f"/ip firewall filter add chain=input action=drop protocol=tcp dst-port=53 in-interface={wan} {before(drop_all)} {_fw_comment('drop wan dns tcp')}",
        "# --- service hardening ---",
        "/ip service set telnet disabled=yes",
        "/ip service set ftp disabled=yes",
        "/ip service set www-ssl disabled=yes",
        "/ip service set api-ssl disabled=yes",
        f"/ip service set ssh address={p.wg_subnet_cidr}",
        f"/ip service set winbox address={p.wg_subnet_cidr}",
        f"/ip service set api disabled=no port=8728 address={p.wg_subnet_cidr}",
        "# www is left enabled on purpose: the hotspot login page is served by it.",
        "# --- discovery and cloud ---",
        "/ip neighbor discovery-settings set discover-interface-list=none",
        "/tool mac-server set allowed-interface-list=none",
        "/tool mac-server mac-winbox set allowed-interface-list=none",
        "/ip cloud set ddns-enabled=no",
    ]
    return lines


def api_user(p: ProvisionParams) -> list[str]:
    """The least-privilege account NetGuard uses, reachable only from the tunnel."""
    policy = ("api,read,write,test,winbox,!local,!telnet,!ssh,!ftp,!reboot,"
              "!policy,!password,!sniff,!sensitive,!romon")
    return [
        "# --- NetGuard API user ---",
        "# !sensitive stops this account reading other stored credentials.",
        f"/user group add name={p.api_username} policy={policy} comment=\"NetGuard API\"",
        f"/user add name={p.api_username} group={p.api_username} "
        f'address={p.wg_subnet_cidr} password="{p.api_password}" comment="NetGuard API"',
    ]
