# --- preflight ---
# No :local variables here: at the top level of an imported file they are empty on the next line.
:if ([:tonum [:pick [/system resource get version] 0 [:find [/system resource get version] "."]]] < 7) do={ :error "NetGuard: RouterOS 7 or newer is required" }
:if ([:len [/ip hotspot find]] > 0) do={ :error "NetGuard: this router already has a hotspot; refusing to overwrite it" }
:if ([:len [/interface wireguard find where name="wireguard-netguard"]] > 0) do={ :error "NetGuard: wireguard-netguard already exists; refusing to overwrite it" }
:put ("NetGuard preflight: RouterOS " . [/system resource get version])
# `level` is what RouterOS 7.16 exposes (a CHR rejected `nlevel`); `nlevel` is kept as a fallback for other builds.
:do { :put ("NetGuard preflight: license level " . [/system license get level]) } on-error={ :do { :put ("NetGuard preflight: license level " . [/system license get nlevel]) } on-error={ :put "NetGuard preflight: license level unavailable on this build" } }
:do { :put ("NetGuard preflight: device-mode " . [/system device-mode get mode]) } on-error={ :put "NetGuard preflight: device-mode unavailable on this build" }
:do { :if ([/system device-mode get mode] = "home") do={ :put "NetGuard preflight: NOTE device-mode is home, so hotspot is blocked. Enabling it needs a physical button press or a cold reboot." } } on-error={}
:put ("NetGuard preflight: free memory " . [/system resource get free-memory])
:put ("NetGuard preflight: free disk " . [/system resource get free-hdd-space])

# --- identity and clock ---
/system identity set name=serrekunda-counter
/system clock set time-zone-name=Africa/Banjul
/system ntp client set enabled=yes
/system ntp client servers add address=time.cloudflare.com comment="NetGuard"
/system ntp client servers add address=time.google.com comment="NetGuard"

# --- bridge ---
/interface bridge add name=bridge-hotspot comment="NetGuard"
# ether1 is the WAN uplink and stays out of the bridge.
# The SFP port is left out too: it is the likely distribution uplink.
# Each port is guarded so a board with fewer ports still gets a working bridge.
:if ([:len [/interface find where name="ether2"]] > 0) do={ /interface bridge port add bridge=bridge-hotspot interface=ether2 comment="NetGuard" }
:if ([:len [/interface find where name="ether3"]] > 0) do={ /interface bridge port add bridge=bridge-hotspot interface=ether3 comment="NetGuard" }
:if ([:len [/interface find where name="ether4"]] > 0) do={ /interface bridge port add bridge=bridge-hotspot interface=ether4 comment="NetGuard" }
:if ([:len [/interface find where name="ether5"]] > 0) do={ /interface bridge port add bridge=bridge-hotspot interface=ether5 comment="NetGuard" }
:if ([:len [/interface find where name="ether6"]] > 0) do={ /interface bridge port add bridge=bridge-hotspot interface=ether6 comment="NetGuard" }
:if ([:len [/interface find where name="ether7"]] > 0) do={ /interface bridge port add bridge=bridge-hotspot interface=ether7 comment="NetGuard" }
:if ([:len [/interface find where name="ether8"]] > 0) do={ /interface bridge port add bridge=bridge-hotspot interface=ether8 comment="NetGuard" }
:if ([:len [/interface find where name="wifi1"]] > 0) do={ /interface bridge port add bridge=bridge-hotspot interface=wifi1 comment="NetGuard" }
:if ([:len [/interface find where name="wifi2"]] > 0) do={ /interface bridge port add bridge=bridge-hotspot interface=wifi2 comment="NetGuard" }
:if ([:len [/interface find where name="wlan1"]] > 0) do={ /interface bridge port add bridge=bridge-hotspot interface=wlan1 comment="NetGuard" }

# --- addressing and DHCP ---
/ip pool add name=hotspot-pool ranges=10.15.1.2-10.15.254.254 comment="NetGuard"
/ip address add address=10.15.0.1/16 interface=bridge-hotspot comment="NetGuard"
/ip dhcp-server add name=hotspot-dhcp interface=bridge-hotspot address-pool=hotspot-pool lease-time=4h authoritative=yes disabled=no comment="NetGuard"
/ip dhcp-server network add address=10.15.0.0/16 gateway=10.15.0.1 dns-server=10.15.0.1 comment="NetGuard"

# --- DNS and NAT ---
/ip dns set allow-remote-requests=yes servers=1.1.1.1,8.8.8.8 cache-size=4096KiB
/ip firewall nat add chain=srcnat action=masquerade out-interface=ether1 comment="NetGuard"

# --- hotspot server ---
# /ip hotspot and /ip hotspot profile have no comment property on RouterOS 7.16 (CHR rejected it), so both are untagged.
/ip hotspot profile add name=netguard hotspot-address=10.15.0.1 dns-name=login.netguard.local login-by=http-chap,mac-cookie http-cookie-lifetime=3d
/ip hotspot add name=netguard interface=bridge-hotspot address-pool=hotspot-pool profile=netguard idle-timeout=5m keepalive-timeout=2m login-timeout=5m disabled=no

# --- voucher tiers ---
# /ip hotspot user profile has no comment property on RouterOS 7.16 (CHR rejected it), so tiers are untagged.
# No rate-limit on any tier, by decision: tiers differ by duration and sharing only.
# shared-users=4 means a 500-session licence ceiling is as few as 125 vouchers.
# RouterOS ships a `default` user profile, so it is updated, not added.
/ip hotspot user profile set [find where name=default] shared-users=4 add-mac-cookie=yes mac-cookie-timeout=3d idle-timeout=5m keepalive-timeout=2m
/ip hotspot user profile add name=1-Hour session-timeout=1h shared-users=1 add-mac-cookie=yes mac-cookie-timeout=3d idle-timeout=5m keepalive-timeout=2m
/ip hotspot user profile add name=24-Hours session-timeout=24h shared-users=2 add-mac-cookie=yes mac-cookie-timeout=3d idle-timeout=5m keepalive-timeout=2m
/ip hotspot user profile add name=7-Days session-timeout=7d shared-users=4 add-mac-cookie=yes mac-cookie-timeout=3d idle-timeout=5m keepalive-timeout=2m

# --- walled garden ---
# Hosts the phone probes to detect a captive portal; blocked, the portal never pops.
/ip hotspot walled-garden add dst-host=connectivitycheck.gstatic.com comment="NetGuard"
/ip hotspot walled-garden add dst-host=captive.apple.com comment="NetGuard"
/ip hotspot walled-garden add dst-host=www.msftconnecttest.com comment="NetGuard"
/ip hotspot walled-garden add dst-host=login.netguard.local comment="NetGuard"
# TODO PAYMENT PROVIDER: add the provider's hosts here before going live.

# --- NetGuard API user ---
# !sensitive stops this account reading other stored credentials.
/user group add name=netguard policy=api,read,write,test,winbox,!local,!telnet,!ssh,!ftp,!reboot,!policy,!password,!sniff,!sensitive,!romon comment="NetGuard API"
/user add name=netguard group=netguard address=10.13.13.0/24 password="Xk7mQp2rTz9wLb4nHc6v" comment="NetGuard API"

# --- wireguard ---
/interface wireguard add name=wireguard-netguard listen-port=13231 mtu=1420 private-key="cHJpdmF0ZS1rZXktbm90LXJlYWwtcGFkZGluZy0zYiE=" comment="NetGuard"
/ip address add address=10.13.13.7/24 interface=wireguard-netguard network=10.13.13.0 comment="NetGuard"
# persistent-keepalive=25s is load-bearing. It must stay below the 30s conntrack UDP
# timeout: the router initiates the tunnel and the firewall's `established` rule lets
# replies in, so a keepalive slower than 30s lets the flow expire. Do not tune it up.
/interface wireguard peers add interface=wireguard-netguard public-key="c2VydmVyLS1rZXktbm90LXJlYWwtcGFkZGluZy0zYiE=" endpoint-address=74.208.167.166 endpoint-port=51820 allowed-address=10.13.13.0/24 persistent-keepalive=25s comment="NetGuard"
/ip route add dst-address=10.13.13.1/32 gateway=wireguard-netguard distance=1 routing-table=main scope=30 target-scope=10 comment="NetGuard"

# --- capsman ---
# The /interface wifi stack is local-forwarding-only: each AP bridges its own clients, so traffic never tunnels through this router.
# Do not port this to legacy /caps-man, which would put every client through the controller.
# ACCEPTED RISK: require-peer-certificate=no means APs are NOT authenticated. Anyone with LAN or
# bridge access can adopt as a CAP. What a rogue CAP receives is only the site SSID and the hotspot
# datapath, nothing credential-shaped, and client traffic never traverses the controller.
# Accepted because per-AP certificates are not viable at 100+ APs per self-provisioned site, and
# would end 'plug an AP into any port and it adopts'. Bounded by interfaces= below: the controller
# listens on the LAN bridge only, never the WAN.
/interface wifi capsman set enabled=yes interfaces=bridge-hotspot upgrade-policy=none require-peer-certificate=no
/interface wifi datapath add name=netguard-datapath bridge=bridge-hotspot comment="NetGuard"
/interface wifi configuration add name=netguard-config ssid=serrekunda-counter datapath=netguard-datapath comment="NetGuard"
# One provisioning rule matching any radio: an AP adopts with no per-AP work.
/interface wifi provisioning add action=create-dynamic-enabled master-configuration=netguard-config comment="NetGuard"

# --- firewall ---
# Terminal rule first; every other rule is placed before it, in order.
/ip firewall filter add chain=input action=drop in-interface=ether1 comment="NetGuard fw: drop wan input"
/ip firewall filter add chain=input action=accept connection-state=established,related,untracked place-before=[find where comment="NetGuard fw: drop wan input"] comment="NetGuard fw: accept established"
/ip firewall filter add chain=input action=drop connection-state=invalid place-before=[find where comment="NetGuard fw: drop wan input"] comment="NetGuard fw: drop invalid"
# Scoped to the tunnel interface: matching on source address alone would accept a
# 10.13.13.x source spoofed from the WAN or LAN, and skip the DNS drops below.
/ip firewall filter add chain=input action=accept src-address=10.13.13.0/24 in-interface=wireguard-netguard place-before=[find where comment="NetGuard fw: drop wan input"] comment="NetGuard fw: accept netguard tunnel"
# Explicit accept for the WireGuard port. Without it the tunnel only survives the WAN drop
# while conntrack holds the flow: udp-timeout is 30s and persistent-keepalive is 25s, a 5s
# margin. A lapsed keepalive would leave ~25s where a server-initiated packet is dropped.
# WireGuard silently ignores unauthenticated packets, so the exposure is negligible.
/ip firewall filter add chain=input action=accept protocol=udp dst-port=13231 in-interface=ether1 place-before=[find where comment="NetGuard fw: drop wan input"] comment="NetGuard fw: accept wireguard"
/ip firewall filter add chain=input action=accept protocol=icmp place-before=[find where comment="NetGuard fw: drop wan input"] comment="NetGuard fw: accept icmp"
# allow-remote-requests=yes is needed for LAN clients; without these the WAN could use the router as an open resolver.
/ip firewall filter add chain=input action=drop protocol=udp dst-port=53 in-interface=ether1 place-before=[find where comment="NetGuard fw: drop wan input"] comment="NetGuard fw: drop wan dns udp"
/ip firewall filter add chain=input action=drop protocol=tcp dst-port=53 in-interface=ether1 place-before=[find where comment="NetGuard fw: drop wan input"] comment="NetGuard fw: drop wan dns tcp"
# --- service hardening ---
/ip service set telnet disabled=yes
/ip service set ftp disabled=yes
/ip service set www-ssl disabled=yes
/ip service set api-ssl disabled=yes
/ip service set ssh address=10.13.13.0/24
/ip service set winbox address=10.13.13.0/24
/ip service set api disabled=no port=8728 address=10.13.13.0/24
# www is left enabled on purpose: the hotspot login page is served by it.
# --- discovery and cloud ---
/ip neighbor discovery-settings set discover-interface-list=none
/tool mac-server set allowed-interface-list=none
/tool mac-server mac-winbox set allowed-interface-list=none
/ip cloud set ddns-enabled=no

# --- summary ---
:put ""
:put "===== NetGuard provisioning complete ====="
:put ("Board:            " . [/system resource get board-name] . "  RouterOS " . [/system resource get version])
:do { :put ("License level:    " . [/system license get level] . "  (level 4 = 200 hotspot users, level 5 = 500, level 6 = unlimited)") } on-error={ :put "License level:    unavailable on this build" }
:put "LAN:              10.15.0.0/16  gateway 10.15.0.1"
:put "DHCP range:       10.15.1.2 - 10.15.254.254"
:put "Voucher profiles: 1-Hour, 24-Hours, 7-Days"
:put "API user:         netguard  (password: see the NetGuard dashboard)"
:put "Tunnel address:   10.13.13.7  (wireguard-netguard to 74.208.167.166:51820)"
:put "The firewall now drops new connections arriving on the WAN port."
