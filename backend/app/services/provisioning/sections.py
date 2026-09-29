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

# Must match backend/app/services/wireguard.py: NetGuard reaches each device at
# its tunnel address, so drift here breaks monitoring.
WG_INTERFACE = "wireguard-netguard"
WG_LISTEN_PORT = 13231


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
        "# Scoped to the tunnel interface: matching on source address alone would accept a",
        "# 10.13.13.x source spoofed from the WAN or LAN, and skip the DNS drops below.",
        f"/ip firewall filter add chain=input action=accept src-address={p.wg_subnet_cidr} in-interface={WG_INTERFACE} {before(drop_all)} {_fw_comment('accept netguard tunnel')}",
        "# Explicit accept for the WireGuard port. Without it the tunnel only survives the WAN drop",
        "# while conntrack holds the flow: udp-timeout is 30s and persistent-keepalive is 25s, a 5s",
        "# margin. A lapsed keepalive would leave ~25s where a server-initiated packet is dropped.",
        "# WireGuard silently ignores unauthenticated packets, so the exposure is negligible.",
        f"/ip firewall filter add chain=input action=accept protocol=udp dst-port={WG_LISTEN_PORT} in-interface={wan} {before(drop_all)} {_fw_comment('accept wireguard')}",
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


def wireguard(p: ProvisionParams) -> list[str]:
    """The tunnel home.

    Mirrors WireGuardService.generate_mikrotik_script in
    backend/app/services/wireguard.py: interface name, listen port, MTU,
    keepalive and the /32 route to the server must stay in step with it,
    because NetGuard reaches the device at its tunnel address.

    One deliberate difference: allowed-address is the tunnel subnet, not
    0.0.0.0/0, so this peer can never become a default route.
    """
    prefix = p.wg_subnet_cidr.split("/")[1]
    network = p.wg_subnet_cidr.split("/")[0]
    server_ip = network.rsplit(".", 1)[0] + ".1"
    return [
        "# --- wireguard ---",
        f'/interface wireguard add name={WG_INTERFACE} listen-port={WG_LISTEN_PORT} mtu=1420 '
        f'private-key="{p.wg_private_key}" {TAG}',
        f"/ip address add address={p.wg_client_ip}/{prefix} interface={WG_INTERFACE} network={network} {TAG}",
        "# persistent-keepalive=25s is load-bearing. It must stay below the 30s conntrack UDP",
        "# timeout: the router initiates the tunnel and the firewall's `established` rule lets",
        "# replies in, so a keepalive slower than 30s lets the flow expire. Do not tune it up.",
        f'/interface wireguard peers add interface={WG_INTERFACE} public-key="{p.wg_server_public_key}" '
        f"endpoint-address={p.wg_server_endpoint} endpoint-port={p.wg_server_port} "
        f"allowed-address={p.wg_subnet_cidr} persistent-keepalive=25s {TAG}",
        f"/ip route add dst-address={server_ip}/32 gateway={WG_INTERFACE} distance=1 "
        f"routing-table=main scope=30 target-scope=10 {TAG}",
    ]


def capsman(p: ProvisionParams) -> list[str]:
    """CAPsMAN controller on the /interface wifi (wifi-qcom) stack.

    Deliberately NOT legacy /caps-man. The new stack is local-forwarding-only:
    client traffic stays on each AP and is bridged there, instead of being
    tunnelled through the controller. That is what makes 100+ APs viable on a
    2-core router. Do not "modernise" this back to /caps-man, which allows
    manager-forwarding and would put every client's traffic through this box.
    """
    return [
        "# --- capsman ---",
        "# The /interface wifi stack is local-forwarding-only: each AP bridges its own clients, so traffic never tunnels through this router.",
        "# Do not port this to legacy /caps-man, which would put every client through the controller.",
        "# ACCEPTED RISK: require-peer-certificate=no means APs are NOT authenticated. Anyone with LAN or",
        "# bridge access can adopt as a CAP. What a rogue CAP receives is only the site SSID and the hotspot",
        "# datapath, nothing credential-shaped, and client traffic never traverses the controller.",
        "# Accepted because per-AP certificates are not viable at 100+ APs per self-provisioned site, and",
        "# would end 'plug an AP into any port and it adopts'. Bounded by interfaces= below: the controller",
        "# listens on the LAN bridge only, never the WAN.",
        f"/interface wifi capsman set enabled=yes interfaces={p.bridge_name} upgrade-policy=none require-peer-certificate=no",
        f"/interface wifi datapath add name=netguard-datapath bridge={p.bridge_name}",
        f"/interface wifi configuration add name=netguard-config ssid={p.site_slug} datapath=netguard-datapath",
        "# One provisioning rule matching any radio: an AP adopts with no per-AP work.",
        "/interface wifi provisioning add action=create-dynamic-enabled master-configuration=netguard-config",
    ]
