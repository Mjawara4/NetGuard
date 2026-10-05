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

# Every action that ends a packet's journey through the input chain. A stock router's LAN guard is
# `drop`, but `reject` and `tarpit` do the same job: if we only looked for `drop`, a guard written
# as `reject` would be invisible, our tunnel accept would land BELOW it, and the router would report
# success while NetGuard could never reach it.
TERMINAL_ACTIONS = ("drop", "reject", "tarpit")
_INPUT_TERMINAL = "chain=input and (" + " or ".join(f"action={a}" for a in TERMINAL_ACTIONS) + ")"

# Must match backend/app/services/wireguard.py: NetGuard reaches each device at
# its tunnel address, so drift here breaks monitoring.
WG_INTERFACE = "wireguard-netguard"
WG_LISTEN_PORT = 13231


def _guard(menu: str, where: str, body: str) -> str:
    return f":if ([:len [{menu} find where {where}]] = 0) do={{ {body} }}"


def _if_present(menu: str, where: str, body: str) -> str:
    """`body`, but only if something matching `where` already exists in `menu`.

    The mirror image of `_guard`. Used for config we only want to touch when the
    router already has the thing it belongs to (defconf's `LAN` interface list),
    so a blank router is left alone instead of being given an object nothing
    on it references.
    """
    return f":if ([:len [{menu} find where {where}]] > 0) do={{ {body} }}"


def _once(menu: str, where: str, args: str) -> str:
    """`menu add args`, but only if nothing matching `where` exists yet.

    A factory-fresh router is not blank, and a run that failed part-way must be
    re-runnable, so every object we create is guarded on its own identity.
    """
    return _guard(menu, where, f"{menu} add {args}")


def preflight(p: ProvisionParams) -> list[str]:
    """Refuse RouterOS 6 and any router that already has a hotspot or our tunnel."""
    return [
        "# --- preflight ---",
        "# Single-statement guards, no :local: kept simple so a failure here is unambiguous. (The whole script is one",
        "# brace-enclosed block, inside which :local does persist across lines, as summary relies on.)",
        ':if ([:tonum [:pick [/system resource get version] 0 [:find [/system resource get version] "."]]] < 7) do={ :error "NetGuard: RouterOS 7 or newer is required" }',
        "# A hotspot or tunnel that is not ours means a configured router: refuse. Ours (left by an earlier",
        "# run that failed part-way) is tolerated so the script can be run again.",
        ':if ([:len [/ip hotspot find where name!="netguard"]] > 0) do={ :error "NetGuard: this router already has a hotspot; refusing to overwrite it" }',
        '# "NetGuard VPN" is TRANSITIONAL: it is what backend/app/services/wireguard.py tagged the',
        "# interface with before the two generators were aligned. Routers already in the field carry",
        "# it, and refusing them would send a customer who did exactly what the UI told them to do",
        "# (press \"Setup WireGuard VPN\", which applies that script) to a factory reset. Both strings",
        "# mean the same thing -- a tunnel NetGuard created -- and neither is a sign of a router",
        "# configured by someone else. Drop the second once no deployed router still reports it.",
        ':if ([:len [/interface wireguard find where name="wireguard-netguard" and comment!="NetGuard" and comment!="NetGuard VPN"]] > 0) do={ :error "NetGuard: wireguard-netguard already exists and is not ours; refusing to overwrite it" }',
        ':put ("NetGuard preflight: RouterOS " . [/system resource get version])',
        "# `level` is what RouterOS 7.16 exposes (a CHR rejected `nlevel`); `nlevel` is kept as a fallback for other builds.",
        ':do { :put ("NetGuard preflight: license level " . [/system license get level]) } on-error={ :do { :put ("NetGuard preflight: license level " . [/system license get nlevel]) } on-error={ :put "NetGuard preflight: license level unavailable on this build" } }',
        ':do { :put ("NetGuard preflight: device-mode " . [/system device-mode get mode]) } on-error={ :put "NetGuard preflight: device-mode unavailable on this build" }',
        ':do { :if ([/system device-mode get mode] = "home") do={ :put "NetGuard preflight: NOTE device-mode is home, so hotspot is blocked. Enabling it needs a physical button press or a cold reboot." } } on-error={}',
        ':put ("NetGuard preflight: free memory " . [/system resource get free-memory])',
        ':put ("NetGuard preflight: free disk " . [/system resource get free-hdd-space])',
        "# Capture whether this router has EVER been provisioned by us, BEFORE we create",
        "# the netguard user below. The honest test for 'fresh router' is the netguard",
        "# user's absence -- but once the api-user section creates it, that test flips to",
        "# false, so any later check would wrongly treat a fresh router as provisioned.",
        "# This caused a real bug: the admin password line, guarded on netguard absence,",
        "# ran AFTER netguard was created and so never fired -- leaving a blank password.",
        "# $ngfresh is read here, once, and stays valid for the whole braced block.",
        ':local ngfresh ([:len [/user find where name="netguard"]] = 0)',
    ]


def identity_and_clock(p: ProvisionParams) -> list[str]:
    return [
        "# --- identity and clock ---",
        f"/system identity set name={p.site_slug}",
        f"/system clock set time-zone-name={p.timezone}",
        "/system ntp client set enabled=yes",
        _once("/system ntp client servers", 'address="time.cloudflare.com"', "address=time.cloudflare.com " + TAG),
        _once("/system ntp client servers", 'address="time.google.com"', "address=time.google.com " + TAG),
    ]


def _port_if_present(name: str, bridge: str) -> str:
    # A stock router already holds ether2-ether5 (and its radios) in a bridge
    # called `bridge`, and RouterOS refuses a port that is already a bridge
    # port. So move it: remove it from whichever bridge has it, then add it.
    # Skipped when it is already on ours, so a re-run does not bounce the port.
    return (
        f':if ([:len [/interface find where name="{name}"]] > 0) do={{ '
        f':if ([:len [/interface bridge port find where interface="{name}" bridge="{bridge}"]] = 0) do={{ '
        f'/interface bridge port remove [find where interface="{name}"]; '
        f"/interface bridge port add bridge={bridge} interface={name} {TAG} }} }}"
    )


def bridge(p: ProvisionParams) -> list[str]:
    lines = [
        "# --- bridge ---",
        ':put "NetGuard: moving ports into bridge-hotspot. If your session drops now, that is expected: the router keeps running this script. Reconnect on a 10.15.x address."',
        _once("/interface bridge", f'name="{p.bridge_name}"', f"name={p.bridge_name} {TAG}"),
        # WHY THIS IS NOT OPTIONAL. A factory-fresh (defconf) router's input chain ends with
        # `drop all not coming from LAN`, which matches `in-interface-list=!LAN`, and defconf's
        # `LAN` interface list has exactly one member: the bridge named `bridge`. We create our
        # own bridge and move every customer port onto it, so without the line below the hotspot
        # bridge is in no interface list and that rule drops EVERYTHING arriving on it: no DHCP
        # lease, no DNS to the gateway, no captive portal -- after the script has printed
        # "provisioning complete". It also kills the documented operator WinBox path from
        # 10.15.0.0/24, which arrives on this bridge too.
        # Chosen over emitting an accept rule above the stock drop: this is where RouterOS
        # expects "this interface is a LAN interface" to be recorded, so an operator reading
        # /interface list later sees the truth instead of a NetGuard rule duplicating the list's
        # job; it fixes every LAN-keyed rule at once, not just that one drop; and it keeps the
        # stock and NetGuard `drop invalid` rules in force for client traffic, which any accept
        # placed above the stock drop would necessarily skip past (the first terminal input rule
        # on defconf is `drop invalid`, which is what our place-before selector targets).
        # Discovery is unaffected: the firewall section sets discover-interface-list=none and
        # mac-server allowed-interface-list=none, so LAN membership cannot re-expose either.
        # The `WAN` list is untouched.
        "# A stock router drops input that is not `in-interface-list=LAN`, and its LAN list holds only",
        "# the bridge named `bridge`. Put our bridge in that list or every client is dropped: no DHCP,",
        "# no DNS, no portal, and no operator WinBox. Guarded on the list existing, because a blank",
        "# router has no interface lists and nothing on it references LAN.",
        _if_present(
            "/interface list", 'name="LAN"',
            _once("/interface list member", f'list="LAN" interface="{p.bridge_name}"',
                  f"list=LAN interface={p.bridge_name} {TAG}"),
        ),
        "# ether1 is the WAN uplink and stays out of the bridge.",
        "# The SFP port is left out too: it is the likely distribution uplink.",
        "# Each port is guarded so a board with fewer ports still gets a working bridge.",
        "# Each port is moved out of any existing bridge first (stock routers ship one).",
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
        _once("/ip pool", 'name="hotspot-pool"',
              f"name=hotspot-pool ranges={p.pool_start}-{p.pool_end} {TAG}"),
        _once("/ip address", f'address="{p.gateway}/{prefix}" interface="{p.bridge_name}"',
              f"address={p.gateway}/{prefix} interface={p.bridge_name} {TAG}"),
        _once("/ip dhcp-server", 'name="hotspot-dhcp"',
              f"name=hotspot-dhcp interface={p.bridge_name} "
              f"address-pool=hotspot-pool lease-time=4h authoritative=yes disabled=no {TAG}"),
        _once("/ip dhcp-server network", f'address="{network}"',
              f"address={network} gateway={p.gateway} dns-server={p.gateway} {TAG}"),
    ]


def dns_and_nat(p: ProvisionParams) -> list[str]:
    return [
        "# --- DNS and NAT ---",
        "/ip dns set allow-remote-requests=yes servers=1.1.1.1,8.8.8.8 cache-size=4096KiB",
        _once("/ip firewall nat", 'comment="NetGuard"',
              f"chain=srcnat action=masquerade out-interface={p.wan_interface} {TAG}"),
    ]


def hotspot_server(p: ProvisionParams) -> list[str]:
    # No ssl-certificate and no https login: there is no domain, so no trusted
    # cert. Captive-portal detection works over plain HTTP.
    return [
        "# --- hotspot server ---",
        "# /ip hotspot and /ip hotspot profile have no comment property on RouterOS 7.16 (CHR rejected it), so both are untagged.",
        _once("/ip hotspot profile", 'name="netguard"',
              f"name=netguard hotspot-address={p.gateway} "
              f"dns-name={p.hotspot_dns_name} login-by=http-chap,mac-cookie "
              "http-cookie-lifetime=3d"),
        _once("/ip hotspot", 'name="netguard"',
              f"name=netguard interface={p.bridge_name} "
              f"address-pool=hotspot-pool profile=netguard "
              f"idle-timeout=5m keepalive-timeout=2m login-timeout=5m disabled=no"),
        # The operator range bypasses the portal.
        #
        # On a real install the installer's own laptop on ether2 is a hotspot client
        # like any phone, so it was handed the login page -- while WinBox is opened
        # only to this range, which sits deliberately BELOW the DHCP pool
        # (pool starts at .1.2). Without this binding an operator has to fight the
        # captive portal to administer the router they just set up.
        #
        # Keyed off p.operator_cidr, the same value the WinBox and www allowances
        # use, so the bypass and the management allowance cannot drift apart: a
        # mismatch between them is an operator locked out with no clue why.
        # The CIDR form is accepted and stored verbatim (verified on a CHR).
        _once("/ip hotspot ip-binding", f'address="{p.operator_cidr}"',
              f"address={p.operator_cidr} type=bypassed comment=\"NetGuard admin\""),
    ]


_TIER_COMMON = (
    "add-mac-cookie=yes mac-cookie-timeout=3d idle-timeout=5m keepalive-timeout=2m"
)


def voucher_profiles(p: ProvisionParams) -> list[str]:
    lines = [
        "# --- voucher tiers ---",
        "# /ip hotspot user profile has no comment property on RouterOS 7.16 (CHR rejected it), so tiers are untagged.",
        "# No rate-limit on any tier, by decision: tiers differ by duration and sharing only.",
        "# shared-users=1 on every profile: one voucher is one device at a time. A 500-session",
        "# licence ceiling is then 500 vouchers in use at once.",
        "# RouterOS ships a `default` user profile, so it is updated, not added.",
        f"/ip hotspot user profile set [find where name=default] shared-users=1 {_TIER_COMMON}",
    ]
    # One device per voucher on every tier (shared-users=1); tiers differ by duration only.
    for name, timeout, shared in (("3-Hours", "3h", 1), ("24-Hours", "24h", 1), ("7-Days", "7d", 1), ("30-Days", "30d", 1)):
        lines.append(_once(
            "/ip hotspot user profile", f'name="{name}"',
            f"name={name} session-timeout={timeout} shared-users={shared} {_TIER_COMMON}",
        ))

    # A standing hotspot login, so the site can be tested and staff can get on
    # without minting a voucher. On the `default` profile: no session timeout,
    # so it does not expire mid-shift.
    #
    # SECURITY: this is a real credential on a public captive portal. The
    # default pair is `admin`/`root`, which is the first thing anyone tries --
    # anyone who guesses it gets free internet on the customer's connection.
    # It is a parameter precisely so a site can be given its own; change it
    # per customer rather than shipping the default to a live deployment.
    lines.append("# A standing login for staff and testing. Change it per site: the default")
    lines.append("# pair is guessable, and this account does not expire.")
    lines.append(_once(
        "/ip hotspot user", f'name="{p.hotspot_login_user}"',
        f"name={p.hotspot_login_user} password={p.hotspot_login_password} profile=default comment=\"NetGuard\"",
    ))
    return lines


def walled_garden(p: ProvisionParams) -> list[str]:
    lines = ["# --- walled garden ---",
             "# Hosts the phone probes to detect a captive portal; blocked, the portal never pops."]
    for host in ("connectivitycheck.gstatic.com", "captive.apple.com",
                 "www.msftconnecttest.com", p.hotspot_dns_name,
                 "app.netguard.fun", "api.modempay.com", "checkout.modempay.com"):
        lines.append(_once("/ip hotspot walled-garden", f'dst-host="{host}"',
                           f"dst-host={host} {TAG}"))
    return lines


def portal_page(p: ProvisionParams) -> list[str]:
    """Install the default portal page; custom portals use the dashboard snippet."""
    if not p.device_id:
        return ["# --- captive portal page ---", "# No device id supplied; leaving the existing login page unchanged."]
    buy_url = f"https://app.netguard.fun/buy?router={p.device_id}&mac=\\$(mac)&ip=\\$(ip)"
    # Dollar signs are escaped for the provisioning script so RouterOS writes
    # the hotspot variables literally; the hotspot renderer expands them per client.
    html = (
        '<!doctype html><html><head><meta name="viewport" content="width=device-width,initial-scale=1">'
        '<title>WiFi Login</title></head><body><h1>WiFi Login</h1>'
        '\\$(if chap-id)<form name="sendin" action="\\$(link-login-only)" method="post">'
        '<input type="hidden" name="username"><input type="hidden" name="password">'
        '<input type="hidden" name="dst" value="\\$(link-orig)"></form>'
        '<script src="/md5.js"></script><script>function doLogin(){document.sendin.username.value='
        'document.login.username.value;document.sendin.password.value=hexMD5("\\$(chap-id)"+'
        'document.login.username.value+"\\$(chap-challenge)");document.sendin.submit();return false}</script>'
        '\\$(endif)'
        '<form name="login" action="\\$(link-login-only)" method="post" '
        'onsubmit="return typeof doLogin===\'function\'?doLogin():true">'
        '<input type="hidden" name="dst" value="\\$(link-orig)">'
        '<label>Voucher code <input name="username" autocomplete="username"></label>'
        '<input type="hidden" name="password" value="">'
        '<button type="submit">Connect</button></form>'
        f'<p><a href="{buy_url}">Buy WiFi</a></p></body></html>'
    )
    escaped = html.replace('"', '\\"')
    return [
        "# --- captive portal page ---",
        ':if ([:len [/file find where name="hotspot/login.html"]] = 0) do={ '
        f'/file add name="hotspot/login.html" contents="{escaped}" '
        f'}} else={{ /file set [find where name="hotspot/login.html"] contents="{escaped}" }}',
    ]


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

    fwmenu = "/ip firewall filter"

    def fw(args: str, name: str) -> str:
        return _once(fwmenu, f'comment="NetGuard fw: {name}"',
                     f"{args} {before()} {_fw_comment(name)}")

    def fw_above_stock(args: str, name: str, where: str, fallback: str = "") -> str:
        """Add the rule ABOVE the first rule of the router's own that matches `where`.

        Never by index. `destination=0` is not ours to claim: a stock config with the fasttrack rule
        carries a builtin `special dummy rule to show fasttrack counters` at index 0 and a move past it
        fails (`failure: cannot move builtin`), which aborts the whole block. So: find the first
        rule that is neither dynamic (that dummy, and the hotspot's own) nor ours, and use
        place-before. If there is none (a blank router) fall back to `fallback`, which appends or
        goes before our own terminal rule. Needed because a stock `drop all not coming from LAN`
        would otherwise drop tunnel traffic before our accept is reached.
        """
        find = f'[{fwmenu} find where {where} and !dynamic and !(comment~"^NetGuard fw")]'
        c = _fw_comment(name)
        add = f"{fwmenu} add {args}"
        body = (f":local t {find}; :if ([:len $t] > 0) do={{ {add} place-before=[:pick $t 0] {c} }} "
                f"else={{ {add}{fallback} {c} }}")
        return _guard(fwmenu, f'comment="NetGuard fw: {name}"', body)

    lines = [
        "# --- firewall ---",
        "# Terminal rule first; every other rule is placed before it, in order.",
        _once("/ip firewall filter", f'comment="NetGuard fw: {drop_all}"',
              f"chain=input action=drop in-interface={wan} {_fw_comment(drop_all)}"),
        fw("chain=input action=accept connection-state=established,related,untracked", "accept established"),
        fw("chain=input action=drop connection-state=invalid", "drop invalid"),
        "# Scoped to the tunnel interface: matching on source address alone would accept a",
        "# 10.13.13.x source spoofed from the WAN or LAN, and skip the DNS drops below.",
        fw_above_stock(f"chain=input action=accept src-address={p.wg_subnet_cidr} in-interface={WG_INTERFACE}",
                       "accept netguard tunnel", _INPUT_TERMINAL, f" {before()}"),
        "# Explicit accept for the WireGuard port. Without it the tunnel only survives the WAN drop",
        "# while conntrack holds the flow: udp-timeout is 30s and persistent-keepalive is 25s, a 5s",
        "# margin. A lapsed keepalive would leave ~25s where a server-initiated packet is dropped.",
        "# WireGuard silently ignores unauthenticated packets, so the exposure is negligible.",
        fw_above_stock(f"chain=input action=accept protocol=udp dst-port={WG_LISTEN_PORT} in-interface={wan}",
                       "accept wireguard", _INPUT_TERMINAL, f" {before()}"),
        fw("chain=input action=accept protocol=icmp", "accept icmp"),
        "# allow-remote-requests=yes is needed for LAN clients; without these the WAN could use the router as an open resolver.",
        fw(f"chain=input action=drop protocol=udp dst-port=53 in-interface={wan}", "drop wan dns udp"),
        fw(f"chain=input action=drop protocol=tcp dst-port=53 in-interface={wan}", "drop wan dns tcp"),
        "# Forward chain: the input rules above protect the router, not the LAN. Without this, an upstream",
        "# that can route to the LAN subnet reaches customers' devices. Only NEW connections from the WAN",
        "# are dropped (LAN-initiated flows and their replies are `established`). It goes above the router's",
        "# own first forward rule so no earlier accept (e.g. a stock config's ipsec accepts) can bypass it.",
        fw_above_stock(f"chain=forward action=drop connection-state=new in-interface={wan}",
                       "drop wan forward", "chain=forward"),
        "# --- service hardening ---",
        "/ip service set telnet disabled=yes",
        "/ip service set ftp disabled=yes",
        "/ip service set www-ssl disabled=yes",
        "/ip service set api-ssl disabled=yes",
        f"/ip service set ssh address={p.wg_subnet_cidr}",
        "# winbox is also reachable from the operator range 10.15.0.0/24, which lies outside the DHCP pool",
        "# (hotspot clients cannot be leased into it). It is the way back in if the tunnel is dead -- but",
        "# only because the bridge section puts bridge-hotspot in the LAN interface list. On a stock router",
        "# WinBox from 10.15.0.5 arrives on bridge-hotspot, and `drop all not coming from LAN` would drop it",
        "# (as it would every client's DHCP and DNS) if that bridge were in no list. What limits WinBox is",
        "# this address pinning, not the filter.",
        f"/ip service set winbox address={p.wg_subnet_cidr},{p.operator_cidr}",
        f"/ip service set api disabled=no port=8728 address={p.wg_subnet_cidr}",
        "# www (WebFig) is NOT what serves the hotspot login page: the hotspot redirects clients to its own",
        "# ports (64872-64875), verified on a CHR with www disabled. So it is kept only for the operator range.",
        f"/ip service set www address={p.operator_cidr}",
        "# --- discovery and cloud ---",
        "# NO `/ip cloud set ddns-enabled=no` here, deliberately.",
        "#",
        "# It is a SYNTAX error on RouterOS 7.24.5 on a real hEX (reported at the value,",
        "# line 163 column 28). Because this script is one brace block, that single",
        "# unsupported property on a line nothing depends on meant NOTHING applied: no",
        "# bridge, no addressing, no hotspot, no API user -- while the summary still",
        "# printed, because a rejected block leaves later lines to run on their own.",
        "#",
        "# Wrapping it in `:do {} on-error={}` does NOT help, and that was measured, not",
        "# assumed: a CHR running the probe printed `expected end of command` and did not",
        "# reach even the first :put inside the block. on-error catches RUNTIME errors;",
        "# an unknown property is rejected when the block is PARSED, before anything runs.",
        "# The only safe place for a command a build might not parse is out of the script.",
        "#",
        "# Cost of leaving it out: MikroTik cloud DDNS is not explicitly disabled. It is",
        "# off by default on a factory router, so this was belt-and-braces, and it is not",
        "# worth the risk of aborting every other line. The three below parse on both",
        "# 7.16.2 and 7.24.5 -- the parser reached line 163, so it accepted 160-162.",
        "/ip neighbor discovery-settings set discover-interface-list=none",
        "/tool mac-server set allowed-interface-list=none",
        "/tool mac-server mac-winbox set allowed-interface-list=none",
    ]
    return lines


def api_user(p: ProvisionParams) -> list[str]:
    """The least-privilege account NetGuard uses, reachable only from the tunnel."""
    policy = ("api,read,write,test,winbox,!local,!telnet,!ssh,!ftp,!reboot,"
              "!policy,!password,!sniff,!sensitive,!romon")
    return [
        "# --- NetGuard API user ---",
        "# !sensitive stops this account reading other stored credentials.",
        _once("/user group", f'name="{p.api_username}"',
              f'name={p.api_username} policy={policy} comment="NetGuard API"'),
        # Created with an EMPTY password and then always `set` below, so a re-run applies whatever password
        # was just generated. Guarding the add alone left a re-run with a new password unapplied, and
        # NetGuard holding a credential the router did not have. (Blank only until the next line; the
        # account is bound to the tunnel subnet.) The empty password must be explicit: omitting it makes
        # /import fail (`missing value(s) of argument(s) password`) and makes an interactive paste PROMPT,
        # swallowing the next pasted line as the password.
        _once("/user", f'name="{p.api_username}"',
              f'name={p.api_username} group={p.api_username} '
              f'address={p.wg_subnet_cidr} password="" comment="NetGuard API"'),
        f'/user set [find where name={p.api_username}] password="{p.api_password}"',
    ] + _recovery_account_lines(p)


def _recovery_account_lines(p: ProvisionParams) -> list[str]:
    """The netguard-recovery break-glass account.

    The router's `admin` password is deliberately NOT touched by this script: it
    belongs to the operator, who sets it themselves. But that leaves exactly one
    full-access account, and the operator's whole access to the router rides on a
    password this script never records. When it is lost, the only way back is a
    factory reset -- which on a customer site is a visit. That happened.

    netguard-recovery is a second full-access account, independent of `admin`:
    random, shown once in the dashboard, and set ONCE on a fresh router and never
    changed afterwards. Losing one password still leaves the other.

    Gated on $ngfresh, captured in preflight BEFORE the netguard user above
    existed, so it fires on a genuinely fresh or factory-reset router and is
    skipped on a re-run (where the value cannot be reproduced anyway). Access is
    the same as admin -- governed by /ip service (winbox from the operator range
    and the tunnel, ssh from the tunnel) -- so it is a usable break-glass, not an
    account reachable by hotspot clients.
    """
    if not p.recovery_password:
        return [
            "# netguard-recovery: left UNCHANGED. No new password was generated for this run.",
        ]
    return [
        "# --- break-glass account ---",
        "# A second full-access login, set once on a fresh router and never changed, so losing",
        "# the admin password you set is not a factory reset. Shown once in NetGuard, never stored.",
        # Existence guard OUTER (so it satisfies "every add is guarded on its own menu"
        # and never duplicates), $ngfresh guard INNER (so it is created only on a truly
        # fresh router and a re-run leaves the operator's saved password alone).
        f':if ([:len [/user find where name="netguard-recovery"]] = 0) do={{ :if ($ngfresh) do={{ /user add name=netguard-recovery group=full password="{p.recovery_password}" comment="NetGuard break-glass -- set once, never rotated" }} }}',
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
        _once("/interface wireguard", f'name="{WG_INTERFACE}"',
              f'name={WG_INTERFACE} listen-port={WG_LISTEN_PORT} mtu=1420 '
              f'private-key="{p.wg_private_key}" {TAG}'),
        _once("/ip address", f'address="{p.wg_client_ip}/{prefix}" interface="{WG_INTERFACE}"',
              f"address={p.wg_client_ip}/{prefix} interface={WG_INTERFACE} network={network} {TAG}"),
        "# persistent-keepalive=25s is load-bearing. It must stay below the 30s conntrack UDP",
        "# timeout: the router initiates the tunnel and the firewall's `established` rule lets",
        "# replies in, so a keepalive slower than 30s lets the flow expire. Do not tune it up.",
        _once("/interface wireguard peers", f'interface="{WG_INTERFACE}"',
              f'interface={WG_INTERFACE} public-key="{p.wg_server_public_key}" '
              f"endpoint-address={p.wg_server_endpoint} endpoint-port={p.wg_server_port} "
              f"allowed-address={p.wg_subnet_cidr} persistent-keepalive=25s {TAG}"),
        # `disabled=no` is explicit so it is comparable with wireguard.py's route, which
        # states it. A route that silently came up disabled would leave NetGuard unable to
        # reach the device while every other check passed.
        _once("/ip route", f'dst-address="{server_ip}/32"',
              f"dst-address={server_ip}/32 gateway={WG_INTERFACE} distance=1 "
              f"routing-table=main scope=30 target-scope=10 disabled=no {TAG}"),
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
        _once("/interface wifi datapath", 'name="netguard-datapath"',
              f"name=netguard-datapath bridge={p.bridge_name} {TAG}"),
        _once("/interface wifi configuration", 'name="netguard-config"',
              f"name=netguard-config ssid={p.site_slug} datapath=netguard-datapath {TAG}"),
        "# One provisioning rule matching any radio: an AP adopts with no per-AP work.",
        _once("/interface wifi provisioning", 'master-configuration="netguard-config"',
              f"action=create-dynamic-enabled master-configuration=netguard-config {TAG}"),
    ]


def summary(p: ProvisionParams) -> list[str]:
    """What the installer reads last, and what stays on screen.

    Deliberately prints neither the API password nor the admin password. Both
    are on the NetGuard dashboard, and a script pasted into a terminal can be
    scrolled back or logged by whoever is at the counter. Each secret appears
    once, in the command that applies it.
    """
    return [
        "# --- summary ---",
        "# Allow the tunnel a few seconds to handshake so the report below is about something.",
        ":delay 8s",
        ':put ""',
        ':put "===== NetGuard provisioning complete ====="',
        ':put ("Board:            " . [/system resource get board-name] . "  RouterOS " . [/system resource get version])',
        # Same two-property dance as preflight, and for the same reason: a real hEX on
        # RouterOS 7.24.5 exposes `nlevel` and rejects `level`, while a 7.16 CHR does the
        # opposite. Trying only one printed "unavailable" on hardware that knew the answer
        # -- and this is the line that tells an installer whether they are capped at 200
        # users or 500, which decides whether the board suits the site at all.
        ':do { :put ("License level:    " . [/system license get level] . "  (level 4 = 200 hotspot users, level 5 = 500, level 6 = unlimited)") } on-error={ :do { :put ("License level:    " . [/system license get nlevel] . "  (level 4 = 200 hotspot users, level 5 = 500, level 6 = unlimited)") } on-error={ :put "License level:    unavailable on this build" } }',
        f':put "WAN port:         {p.wan_interface} (left out of the bridge)"',
        ':local ports ""',
        f':foreach i in=[/interface bridge port find where bridge="{p.bridge_name}"] do={{ :set ports ($ports . [/interface bridge port get $i interface] . " ") }}',
        f':put ("LAN ports:        " . $ports . "(bridge {p.bridge_name})")',
        "# Reachability of the client bridge, reported rather than assumed. A stock router's",
        "# `drop all not coming from LAN` silently discards every client packet when this is wrong,",
        "# and the rest of this summary would still print. This is the line that would have caught it.",
        f':if ([:len [/interface list find where name="LAN"]] > 0) do={{ :if ([:len [/interface list member find where list="LAN" interface="{p.bridge_name}"]] > 0) do={{ :put "Client bridge:    {p.bridge_name} is in the LAN interface list, so a stock drop-not-from-LAN rule does not block clients" }} else={{ :put "Client bridge:    WARNING {p.bridge_name} is NOT in the LAN interface list; a stock drop-not-from-LAN rule will block every client" }} }} else={{ :put "Client bridge:    this router has no LAN interface list, so no rule can key off one" }}',
        f':put "LAN:              {p.lan_cidr}  gateway {p.gateway}"',
        f':put "DHCP range:       {p.pool_start} - {p.pool_end}"',
        ':put "Voucher profiles: 3-Hours, 24-Hours, 7-Days, 30-Days"',
        f':put "API user:         {p.api_username}  (password: see the NetGuard dashboard)"',
        # The admin password is the operator's own and is NEVER touched here. On a
        # fresh router it is still the factory BLANK, reachable over winbox from the
        # operator range -- so warn, loudly and only when fresh, to set it now. There
        # is no way to read a password back in RouterOS, so this keys off $ngfresh.
        ':if ($ngfresh) do={ :put "admin password:   STILL BLANK -- set it now:  /user set [find where name=admin] password=YOURPASSWORD" } else={ :put "admin password:   unchanged (managed by you, never by this script)" }',
        ':if ($ngfresh) do={ :put ("recovery login:   netguard-recovery  (password: see the NetGuard dashboard, shown once)") } else={ :put "recovery login:   netguard-recovery  (unchanged; set once on first install)" }',
        f':put "Tunnel address:   {p.wg_client_ip}  ({WG_INTERFACE} to {p.wg_server_endpoint}:{p.wg_server_port})"',
        f':do {{ :if ([:len [/interface wireguard peers get [find where interface="{WG_INTERFACE}"] last-handshake]] > 0) do={{ :put "Tunnel status:    UP (handshake seen)" }} else={{ :put "Tunnel status:    NOT UP YET - check the {p.wan_interface} cable and uplink; it can take a minute" }} }} on-error={{ :put "Tunnel status:    NOT UP YET - check the {p.wan_interface} cable and uplink; it can take a minute" }}',
        f':put "ssh and api are now reachable only through the tunnel ({p.wg_subnet_cidr}); winbox also from {p.operator_cidr}."',
        f':put "New connections arriving on {p.wan_interface} are dropped (router and LAN), except the WireGuard port and ping."',
        f':put "If your session was cut while ports moved, that was expected. Reconnect on a {p.lan_cidr.split(".")[0]}.{p.lan_cidr.split(".")[1]}.x address."',
    ]
