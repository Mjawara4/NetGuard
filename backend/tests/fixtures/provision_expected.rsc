{
# --- preflight ---
# Single-statement guards, no :local: kept simple so a failure here is unambiguous. (The whole script is one
# brace-enclosed block, inside which :local does persist across lines, as summary relies on.)
:if ([:tonum [:pick [/system resource get version] 0 [:find [/system resource get version] "."]]] < 7) do={ :error "NetGuard: RouterOS 7 or newer is required" }
# A hotspot or tunnel that is not ours means a configured router: refuse. Ours (left by an earlier
# run that failed part-way) is tolerated so the script can be run again.
:if ([:len [/ip hotspot find where name!="netguard"]] > 0) do={ :error "NetGuard: this router already has a hotspot; refusing to overwrite it. Use the existing hotspot script from the NetGuard dashboard instead" }
# "NetGuard VPN" is TRANSITIONAL: it is what backend/app/services/wireguard.py tagged the
# interface with before the two generators were aligned. Routers already in the field carry
# it, and refusing them would send a customer who did exactly what the UI told them to do
# (press "Setup WireGuard VPN", which applies that script) to a factory reset. Both strings
# mean the same thing -- a tunnel NetGuard created -- and neither is a sign of a router
# configured by someone else. Drop the second once no deployed router still reports it.
:if ([:len [/interface wireguard find where name="wireguard-netguard" and comment!="NetGuard" and comment!="NetGuard VPN"]] > 0) do={ :error "NetGuard: wireguard-netguard already exists and is not ours; refusing to overwrite it" }
:put ("NetGuard preflight: RouterOS " . [/system resource get version])
# `level` is what RouterOS 7.16 exposes (a CHR rejected `nlevel`); `nlevel` is kept as a fallback for other builds.
:do { :put ("NetGuard preflight: license level " . [/system license get level]) } on-error={ :do { :put ("NetGuard preflight: license level " . [/system license get nlevel]) } on-error={ :put "NetGuard preflight: license level unavailable on this build" } }
:do { :put ("NetGuard preflight: device-mode " . [/system device-mode get mode]) } on-error={ :put "NetGuard preflight: device-mode unavailable on this build" }
:do { :if ([/system device-mode get mode] = "home") do={ :put "NetGuard preflight: NOTE device-mode is home, so hotspot is blocked. Enabling it needs a physical button press or a cold reboot." } } on-error={}
:put ("NetGuard preflight: free memory " . [/system resource get free-memory])
:put ("NetGuard preflight: free disk " . [/system resource get free-hdd-space])
# Capture whether this router has EVER been provisioned by us, BEFORE we create
# the netguard user below. The honest test for 'fresh router' is the netguard
# user's absence -- but once the api-user section creates it, that test flips to
# false, so any later check would wrongly treat a fresh router as provisioned.
# This caused a real bug: the admin password line, guarded on netguard absence,
# ran AFTER netguard was created and so never fired -- leaving a blank password.
# $ngfresh is read here, once, and stays valid for the whole braced block.
:local ngfresh ([:len [/user find where name="netguard"]] = 0)

# --- identity and clock ---
/system identity set name=serrekunda-counter
/system clock set time-zone-name=Africa/Banjul
/system ntp client set enabled=yes
:if ([:len [/system ntp client servers find where address="time.cloudflare.com"]] = 0) do={ /system ntp client servers add address=time.cloudflare.com comment="NetGuard" }
:if ([:len [/system ntp client servers find where address="time.google.com"]] = 0) do={ /system ntp client servers add address=time.google.com comment="NetGuard" }

# --- bridge ---
:put "NetGuard: moving ports into bridge-hotspot. If your session drops now, that is expected: the router keeps running this script. Reconnect on a 10.15.x address."
:if ([:len [/interface bridge find where name="bridge-hotspot"]] = 0) do={ /interface bridge add name=bridge-hotspot comment="NetGuard" }
# A stock router drops input that is not `in-interface-list=LAN`, and its LAN list holds only
# the bridge named `bridge`. Put our bridge in that list or every client is dropped: no DHCP,
# no DNS, no portal, and no operator WinBox. Guarded on the list existing, because a blank
# router has no interface lists and nothing on it references LAN.
:if ([:len [/interface list find where name="LAN"]] > 0) do={ :if ([:len [/interface list member find where list="LAN" interface="bridge-hotspot"]] = 0) do={ /interface list member add list=LAN interface=bridge-hotspot comment="NetGuard" } }
# ether1 is the WAN uplink and stays out of the bridge.
# The SFP port is left out too: it is the likely distribution uplink.
# Each port is guarded so a board with fewer ports still gets a working bridge.
# Each port is moved out of any existing bridge first (stock routers ship one).
:if ([:len [/interface find where name="ether2"]] > 0) do={ :if ([:len [/interface bridge port find where interface="ether2" bridge="bridge-hotspot"]] = 0) do={ /interface bridge port remove [find where interface="ether2"]; /interface bridge port add bridge=bridge-hotspot interface=ether2 comment="NetGuard" } }
:if ([:len [/interface find where name="ether3"]] > 0) do={ :if ([:len [/interface bridge port find where interface="ether3" bridge="bridge-hotspot"]] = 0) do={ /interface bridge port remove [find where interface="ether3"]; /interface bridge port add bridge=bridge-hotspot interface=ether3 comment="NetGuard" } }
:if ([:len [/interface find where name="ether4"]] > 0) do={ :if ([:len [/interface bridge port find where interface="ether4" bridge="bridge-hotspot"]] = 0) do={ /interface bridge port remove [find where interface="ether4"]; /interface bridge port add bridge=bridge-hotspot interface=ether4 comment="NetGuard" } }
:if ([:len [/interface find where name="ether5"]] > 0) do={ :if ([:len [/interface bridge port find where interface="ether5" bridge="bridge-hotspot"]] = 0) do={ /interface bridge port remove [find where interface="ether5"]; /interface bridge port add bridge=bridge-hotspot interface=ether5 comment="NetGuard" } }
:if ([:len [/interface find where name="ether6"]] > 0) do={ :if ([:len [/interface bridge port find where interface="ether6" bridge="bridge-hotspot"]] = 0) do={ /interface bridge port remove [find where interface="ether6"]; /interface bridge port add bridge=bridge-hotspot interface=ether6 comment="NetGuard" } }
:if ([:len [/interface find where name="ether7"]] > 0) do={ :if ([:len [/interface bridge port find where interface="ether7" bridge="bridge-hotspot"]] = 0) do={ /interface bridge port remove [find where interface="ether7"]; /interface bridge port add bridge=bridge-hotspot interface=ether7 comment="NetGuard" } }
:if ([:len [/interface find where name="ether8"]] > 0) do={ :if ([:len [/interface bridge port find where interface="ether8" bridge="bridge-hotspot"]] = 0) do={ /interface bridge port remove [find where interface="ether8"]; /interface bridge port add bridge=bridge-hotspot interface=ether8 comment="NetGuard" } }
:if ([:len [/interface find where name="wifi1"]] > 0) do={ :if ([:len [/interface bridge port find where interface="wifi1" bridge="bridge-hotspot"]] = 0) do={ /interface bridge port remove [find where interface="wifi1"]; /interface bridge port add bridge=bridge-hotspot interface=wifi1 comment="NetGuard" } }
:if ([:len [/interface find where name="wifi2"]] > 0) do={ :if ([:len [/interface bridge port find where interface="wifi2" bridge="bridge-hotspot"]] = 0) do={ /interface bridge port remove [find where interface="wifi2"]; /interface bridge port add bridge=bridge-hotspot interface=wifi2 comment="NetGuard" } }
:if ([:len [/interface find where name="wlan1"]] > 0) do={ :if ([:len [/interface bridge port find where interface="wlan1" bridge="bridge-hotspot"]] = 0) do={ /interface bridge port remove [find where interface="wlan1"]; /interface bridge port add bridge=bridge-hotspot interface=wlan1 comment="NetGuard" } }

# --- addressing and DHCP ---
:if ([:len [/ip pool find where name="hotspot-pool"]] = 0) do={ /ip pool add name=hotspot-pool ranges=10.15.1.2-10.15.254.254 comment="NetGuard" }
:if ([:len [/ip address find where address="10.15.0.1/16" interface="bridge-hotspot"]] = 0) do={ /ip address add address=10.15.0.1/16 interface=bridge-hotspot comment="NetGuard" }
:if ([:len [/ip dhcp-server find where name="hotspot-dhcp"]] = 0) do={ /ip dhcp-server add name=hotspot-dhcp interface=bridge-hotspot address-pool=hotspot-pool lease-time=4h authoritative=yes disabled=no comment="NetGuard" }
:if ([:len [/ip dhcp-server network find where address="10.15.0.0/16"]] = 0) do={ /ip dhcp-server network add address=10.15.0.0/16 gateway=10.15.0.1 dns-server=10.15.0.1 comment="NetGuard" }

# --- DNS and NAT ---
/ip dns set allow-remote-requests=yes servers=1.1.1.1,8.8.8.8 cache-size=4096KiB
:if ([:len [/ip firewall nat find where comment="NetGuard"]] = 0) do={ /ip firewall nat add chain=srcnat action=masquerade out-interface=ether1 comment="NetGuard" }

# --- hotspot server ---
# /ip hotspot and /ip hotspot profile have no comment property on RouterOS 7.16 (CHR rejected it), so both are untagged.
:if ([:len [/ip hotspot profile find where name="netguard"]] = 0) do={ /ip hotspot profile add name=netguard hotspot-address=10.15.0.1 dns-name=login.netguard.local login-by=http-chap,mac-cookie http-cookie-lifetime=3d }
:if ([:len [/ip hotspot find where name="netguard"]] = 0) do={ /ip hotspot add name=netguard interface=bridge-hotspot address-pool=hotspot-pool profile=netguard idle-timeout=5m keepalive-timeout=2m login-timeout=5m disabled=no }
:if ([:len [/ip hotspot ip-binding find where address="10.15.0.0/24"]] = 0) do={ /ip hotspot ip-binding add address=10.15.0.0/24 type=bypassed comment="NetGuard admin" }

# --- voucher tiers ---
# /ip hotspot user profile has no comment property on RouterOS 7.16 (CHR rejected it), so tiers are untagged.
# No rate-limit on any tier, by decision: tiers differ by duration and sharing only.
# shared-users=1 on every profile: one voucher is one device at a time. A 500-session
# licence ceiling is then 500 vouchers in use at once.
# RouterOS ships a `default` user profile, so it is updated, not added.
/ip hotspot user profile set [find where name=default] shared-users=1 add-mac-cookie=yes mac-cookie-timeout=3d idle-timeout=5m keepalive-timeout=2m
:if ([:len [/ip hotspot user profile find where name="3-Hours"]] = 0) do={ /ip hotspot user profile add name=3-Hours session-timeout=3h shared-users=1 add-mac-cookie=yes mac-cookie-timeout=3d idle-timeout=5m keepalive-timeout=2m }
:if ([:len [/ip hotspot user profile find where name="24-Hours"]] = 0) do={ /ip hotspot user profile add name=24-Hours session-timeout=24h shared-users=1 add-mac-cookie=yes mac-cookie-timeout=3d idle-timeout=5m keepalive-timeout=2m }
:if ([:len [/ip hotspot user profile find where name="7-Days"]] = 0) do={ /ip hotspot user profile add name=7-Days session-timeout=7d shared-users=1 add-mac-cookie=yes mac-cookie-timeout=3d idle-timeout=5m keepalive-timeout=2m }
:if ([:len [/ip hotspot user profile find where name="30-Days"]] = 0) do={ /ip hotspot user profile add name=30-Days session-timeout=30d shared-users=1 add-mac-cookie=yes mac-cookie-timeout=3d idle-timeout=5m keepalive-timeout=2m }
# A standing login for staff and testing. Change it per site: the default
# pair is guessable, and this account does not expire.
:if ([:len [/ip hotspot user find where name="admin"]] = 0) do={ /ip hotspot user add name=admin password=root profile=default comment="NetGuard" }

# --- walled garden ---
# Hosts the phone probes to detect a captive portal; blocked, the portal never pops.
:if ([:len [/ip hotspot walled-garden find where dst-host="connectivitycheck.gstatic.com"]] = 0) do={ /ip hotspot walled-garden add dst-host=connectivitycheck.gstatic.com comment="NetGuard" }
:if ([:len [/ip hotspot walled-garden find where dst-host="captive.apple.com"]] = 0) do={ /ip hotspot walled-garden add dst-host=captive.apple.com comment="NetGuard" }
:if ([:len [/ip hotspot walled-garden find where dst-host="www.msftconnecttest.com"]] = 0) do={ /ip hotspot walled-garden add dst-host=www.msftconnecttest.com comment="NetGuard" }
:if ([:len [/ip hotspot walled-garden find where dst-host="login.netguard.local"]] = 0) do={ /ip hotspot walled-garden add dst-host=login.netguard.local comment="NetGuard" }
:if ([:len [/ip hotspot walled-garden find where dst-host="app.netguard.fun"]] = 0) do={ /ip hotspot walled-garden add dst-host=app.netguard.fun comment="NetGuard" }
:if ([:len [/ip hotspot walled-garden find where dst-host="api.modempay.com"]] = 0) do={ /ip hotspot walled-garden add dst-host=api.modempay.com comment="NetGuard" }
:if ([:len [/ip hotspot walled-garden find where dst-host="checkout.modempay.com"]] = 0) do={ /ip hotspot walled-garden add dst-host=checkout.modempay.com comment="NetGuard" }
:if ([:len [/ip hotspot walled-garden find where dst-host="test.checkout.modempay.com"]] = 0) do={ /ip hotspot walled-garden add dst-host=test.checkout.modempay.com comment="NetGuard" }
:if ([:len [/ip hotspot walled-garden find where dst-host="cdnjs.cloudflare.com"]] = 0) do={ /ip hotspot walled-garden add dst-host=cdnjs.cloudflare.com comment="NetGuard" }
:if ([:len [/ip hotspot walled-garden find where dst-host="fonts.googleapis.com"]] = 0) do={ /ip hotspot walled-garden add dst-host=fonts.googleapis.com comment="NetGuard" }
:if ([:len [/ip hotspot walled-garden find where dst-host="fonts.gstatic.com"]] = 0) do={ /ip hotspot walled-garden add dst-host=fonts.gstatic.com comment="NetGuard" }
:if ([:len [/ip hotspot walled-garden find where dst-host="na-gateway.mastercard.com"]] = 0) do={ /ip hotspot walled-garden add dst-host=na-gateway.mastercard.com comment="NetGuard" }
:if ([:len [/ip hotspot walled-garden find where dst-host="ye1.i.lencr.org"]] = 0) do={ /ip hotspot walled-garden add dst-host=ye1.i.lencr.org comment="NetGuard" }
:if ([:len [/ip hotspot walled-garden find where dst-host="ye1.c.lencr.org"]] = 0) do={ /ip hotspot walled-garden add dst-host=ye1.c.lencr.org comment="NetGuard" }
:if ([:len [/ip hotspot walled-garden ip find where dst-host="app.netguard.fun" and protocol="tcp" and dst-port="443"]] = 0) do={ /ip hotspot walled-garden ip add dst-host=app.netguard.fun protocol=tcp dst-port=443 action=accept comment="NetGuard" }
:if ([:len [/ip hotspot walled-garden ip find where dst-host="api.modempay.com" and protocol="tcp" and dst-port="443"]] = 0) do={ /ip hotspot walled-garden ip add dst-host=api.modempay.com protocol=tcp dst-port=443 action=accept comment="NetGuard" }
:if ([:len [/ip hotspot walled-garden ip find where dst-host="checkout.modempay.com" and protocol="tcp" and dst-port="443"]] = 0) do={ /ip hotspot walled-garden ip add dst-host=checkout.modempay.com protocol=tcp dst-port=443 action=accept comment="NetGuard" }
:if ([:len [/ip hotspot walled-garden ip find where dst-host="test.checkout.modempay.com" and protocol="tcp" and dst-port="443"]] = 0) do={ /ip hotspot walled-garden ip add dst-host=test.checkout.modempay.com protocol=tcp dst-port=443 action=accept comment="NetGuard" }
:if ([:len [/ip hotspot walled-garden ip find where dst-host="cdnjs.cloudflare.com" and protocol="tcp" and dst-port="443"]] = 0) do={ /ip hotspot walled-garden ip add dst-host=cdnjs.cloudflare.com protocol=tcp dst-port=443 action=accept comment="NetGuard" }
:if ([:len [/ip hotspot walled-garden ip find where dst-host="fonts.googleapis.com" and protocol="tcp" and dst-port="443"]] = 0) do={ /ip hotspot walled-garden ip add dst-host=fonts.googleapis.com protocol=tcp dst-port=443 action=accept comment="NetGuard" }
:if ([:len [/ip hotspot walled-garden ip find where dst-host="fonts.gstatic.com" and protocol="tcp" and dst-port="443"]] = 0) do={ /ip hotspot walled-garden ip add dst-host=fonts.gstatic.com protocol=tcp dst-port=443 action=accept comment="NetGuard" }
:if ([:len [/ip hotspot walled-garden ip find where dst-host="na-gateway.mastercard.com" and protocol="tcp" and dst-port="443"]] = 0) do={ /ip hotspot walled-garden ip add dst-host=na-gateway.mastercard.com protocol=tcp dst-port=443 action=accept comment="NetGuard" }
:if ([:len [/ip hotspot walled-garden ip find where dst-host="ye1.i.lencr.org" and protocol="tcp" and dst-port="443"]] = 0) do={ /ip hotspot walled-garden ip add dst-host=ye1.i.lencr.org protocol=tcp dst-port=443 action=accept comment="NetGuard" }
:if ([:len [/ip hotspot walled-garden ip find where dst-host="ye1.c.lencr.org" and protocol="tcp" and dst-port="443"]] = 0) do={ /ip hotspot walled-garden ip add dst-host=ye1.c.lencr.org protocol=tcp dst-port=443 action=accept comment="NetGuard" }
:if ([:len [/ip hotspot walled-garden ip find where dst-host="ye1.i.lencr.org" and protocol="tcp" and dst-port="80"]] = 0) do={ /ip hotspot walled-garden ip add dst-host=ye1.i.lencr.org protocol=tcp dst-port=80 action=accept comment="NetGuard" }
:if ([:len [/ip hotspot walled-garden ip find where dst-host="ye1.c.lencr.org" and protocol="tcp" and dst-port="80"]] = 0) do={ /ip hotspot walled-garden ip add dst-host=ye1.c.lencr.org protocol=tcp dst-port=80 action=accept comment="NetGuard" }

# --- captive portal page ---
# Written into the folder the hotspot actually serves, which need not be hotspot/.
:local ngPortalDir [/ip hotspot profile get [find where name="netguard"] html-directory]
:local ngLogin ($ngPortalDir . "/login.html")
# RouterOS creates a new hotspot's default pages a moment after the server is
# added; replacing login.html before it appears fails with 'file already exists'.
:local ngWait 0
:while ([:len [/file find where name=$ngLogin]] = 0 && $ngWait < 20) do={ :delay 500ms; :set ngWait ($ngWait + 1) }
:if ([:len [/file find where name=$ngLogin]] = 0) do={ /file add name=$ngLogin contents="<!doctype html><!-- NETGUARD-PORTAL --><html><head><meta charset=\"utf-8\"><meta name=\"viewport\" content=\"width=device-width,initial-scale=1\"><title>Buy WiFi</title><style>*{box-sizing:border-box}body{margin:0;background:#0d110f;color:#fff;font-family:Arial,sans-serif}.box{max-width:500px;margin:7vh auto;padding:32px;background:#171d1a;box-shadow:0 18px 50px #0008;text-align:center}.wifi{font-size:44px;color:#8d3caf}h1{font-size:34px;margin:8px 0}p{color:#aeb6b2}.plans{display:grid;gap:12px;margin:24px 0;text-align:left}.plan{display:flex;align-items:center;justify-content:space-between;padding:17px;color:#fff;text-decoration:none;border:1px solid #46504b;border-radius:10px}.plan:hover{border-color:#8d3caf}.plan span{display:grid;gap:5px}.plan small{color:#aeb6b2;font-size:16px}.plan em,.buy,button{background:#8737aa;color:#fff;border:0;border-radius:9px;padding:12px 18px;font-weight:bold;text-decoration:none;font-style:normal}.voucher{border-top:1px solid #343c38;margin-top:26px;padding-top:20px}input{width:60%;padding:12px;margin:8px;border-radius:7px;border:1px solid #68726d;background:#0d110f;color:#fff}@media(max-width:540px){.box{margin:0;min-height:100vh;padding:28px 20px}}</style></head><body><main class=\"box\"><div class=\"wifi\"><svg aria-hidden=\"true\" viewBox=\"0 0 24 24\" width=\"52\" height=\"52\" fill=\"none\" stroke=\"currentColor\" stroke-width=\"2\" stroke-linecap=\"round\"><path d=\"M5 12.6a10 10 0 0 1 14 0M8.5 16a5 5 0 0 1 7 0M12 20h.01\"/></svg></div><h1>Buy WiFi</h1><p>Choose a plan and pay securely with Modem Pay.</p><div class=\"plans\"></div>\$(if chap-id)<form name=\"sendin\" action=\"\$(link-login-only)\" method=\"post\"><input type=\"hidden\" name=\"username\"><input type=\"hidden\" name=\"password\"><input type=\"hidden\" name=\"dst\" value=\"\$(link-orig)\"></form><script src=\"/md5.js\"></script><script>function doLogin(){var login=document.forms[\"login\"],sendin=document.forms[\"sendin\"],v=login.elements.namedItem(\"username\").value;sendin.elements.namedItem(\"username\").value=v;sendin.elements.namedItem(\"password\").value=hexMD5(\"\$(chap-id)\"+v+\"\$(chap-challenge)\");sendin.submit();return false}</script>\$(endif)<div class=\"voucher\"><p>Already have a voucher?</p><form name=\"login\" action=\"\$(link-login-only)\" method=\"post\" onsubmit=\"return typeof doLogin==='function'?doLogin():true\"><input type=\"hidden\" name=\"dst\" value=\"\$(link-orig)\"><label>Voucher code <input name=\"username\" autocomplete=\"username\"></label><input type=\"hidden\" name=\"password\" value=\"\"><button type=\"submit\">Connect</button></form></div><p><a class=\"buy\" href=\"https://app.netguard.fun/buy?router=11111111-1111-1111-1111-111111111111&mac=\$(mac)&ip=\$(ip)&login=\$(link-login-only)\">View all plans</a></p><script>(function(){var q=new URLSearchParams(location.search),v=q.get(\"voucher\"),d=q.get(\"dst\");if(!v)return;var login=document.forms[\"login\"],sendin=document.forms[\"sendin\"];login.elements.namedItem(\"username\").value=v;login.elements.namedItem(\"password\").value=v;if(d){login.elements.namedItem(\"dst\").value=d;if(sendin)sendin.elements.namedItem(\"dst\").value=d;}if(typeof doLogin===\"function\")doLogin();else login.submit();})();</script></main></body></html>" } else={ /file set [find where name=$ngLogin] contents="<!doctype html><!-- NETGUARD-PORTAL --><html><head><meta charset=\"utf-8\"><meta name=\"viewport\" content=\"width=device-width,initial-scale=1\"><title>Buy WiFi</title><style>*{box-sizing:border-box}body{margin:0;background:#0d110f;color:#fff;font-family:Arial,sans-serif}.box{max-width:500px;margin:7vh auto;padding:32px;background:#171d1a;box-shadow:0 18px 50px #0008;text-align:center}.wifi{font-size:44px;color:#8d3caf}h1{font-size:34px;margin:8px 0}p{color:#aeb6b2}.plans{display:grid;gap:12px;margin:24px 0;text-align:left}.plan{display:flex;align-items:center;justify-content:space-between;padding:17px;color:#fff;text-decoration:none;border:1px solid #46504b;border-radius:10px}.plan:hover{border-color:#8d3caf}.plan span{display:grid;gap:5px}.plan small{color:#aeb6b2;font-size:16px}.plan em,.buy,button{background:#8737aa;color:#fff;border:0;border-radius:9px;padding:12px 18px;font-weight:bold;text-decoration:none;font-style:normal}.voucher{border-top:1px solid #343c38;margin-top:26px;padding-top:20px}input{width:60%;padding:12px;margin:8px;border-radius:7px;border:1px solid #68726d;background:#0d110f;color:#fff}@media(max-width:540px){.box{margin:0;min-height:100vh;padding:28px 20px}}</style></head><body><main class=\"box\"><div class=\"wifi\"><svg aria-hidden=\"true\" viewBox=\"0 0 24 24\" width=\"52\" height=\"52\" fill=\"none\" stroke=\"currentColor\" stroke-width=\"2\" stroke-linecap=\"round\"><path d=\"M5 12.6a10 10 0 0 1 14 0M8.5 16a5 5 0 0 1 7 0M12 20h.01\"/></svg></div><h1>Buy WiFi</h1><p>Choose a plan and pay securely with Modem Pay.</p><div class=\"plans\"></div>\$(if chap-id)<form name=\"sendin\" action=\"\$(link-login-only)\" method=\"post\"><input type=\"hidden\" name=\"username\"><input type=\"hidden\" name=\"password\"><input type=\"hidden\" name=\"dst\" value=\"\$(link-orig)\"></form><script src=\"/md5.js\"></script><script>function doLogin(){var login=document.forms[\"login\"],sendin=document.forms[\"sendin\"],v=login.elements.namedItem(\"username\").value;sendin.elements.namedItem(\"username\").value=v;sendin.elements.namedItem(\"password\").value=hexMD5(\"\$(chap-id)\"+v+\"\$(chap-challenge)\");sendin.submit();return false}</script>\$(endif)<div class=\"voucher\"><p>Already have a voucher?</p><form name=\"login\" action=\"\$(link-login-only)\" method=\"post\" onsubmit=\"return typeof doLogin==='function'?doLogin():true\"><input type=\"hidden\" name=\"dst\" value=\"\$(link-orig)\"><label>Voucher code <input name=\"username\" autocomplete=\"username\"></label><input type=\"hidden\" name=\"password\" value=\"\"><button type=\"submit\">Connect</button></form></div><p><a class=\"buy\" href=\"https://app.netguard.fun/buy?router=11111111-1111-1111-1111-111111111111&mac=\$(mac)&ip=\$(ip)&login=\$(link-login-only)\">View all plans</a></p><script>(function(){var q=new URLSearchParams(location.search),v=q.get(\"voucher\"),d=q.get(\"dst\");if(!v)return;var login=document.forms[\"login\"],sendin=document.forms[\"sendin\"];login.elements.namedItem(\"username\").value=v;login.elements.namedItem(\"password\").value=v;if(d){login.elements.namedItem(\"dst\").value=d;if(sendin)sendin.elements.namedItem(\"dst\").value=d;}if(typeof doLogin===\"function\")doLogin();else login.submit();})();</script></main></body></html>" }

# --- NetGuard API user ---
# !sensitive stops this account reading other stored credentials.
:if ([:len [/user group find where name="netguard"]] = 0) do={ /user group add name=netguard policy=api,read,write,test,winbox,!local,!telnet,!ssh,!ftp,!reboot,!policy,!password,!sniff,!sensitive,!romon comment="NetGuard API" }
:if ([:len [/user find where name="netguard"]] = 0) do={ /user add name=netguard group=netguard address=10.13.13.0/24 password="" comment="NetGuard API" }
/user set [find where name=netguard] password="Xk7mQp2rTz9wLb4nHc6v"
# --- break-glass account ---
# A second full-access login, set once on a fresh router and never changed, so losing
# the admin password you set is not a factory reset. Shown once in NetGuard, never stored.
:if ([:len [/user find where name="netguard-recovery"]] = 0) do={ :if ($ngfresh) do={ /user add name=netguard-recovery group=full password="Qw8ZeRtY3uIoP5aSdF1g" comment="NetGuard break-glass -- set once, never rotated" } }

# --- wireguard ---
:if ([:len [/interface wireguard find where name="wireguard-netguard"]] = 0) do={ /interface wireguard add name=wireguard-netguard listen-port=13231 mtu=1420 private-key="cHJpdmF0ZS1rZXktbm90LXJlYWwtcGFkZGluZy0zYiE=" comment="NetGuard" }
:if ([:len [/ip address find where address="10.13.13.7/24" interface="wireguard-netguard"]] = 0) do={ /ip address add address=10.13.13.7/24 interface=wireguard-netguard network=10.13.13.0 comment="NetGuard" }
# persistent-keepalive=25s is load-bearing. It must stay below the 30s conntrack UDP
# timeout: the router initiates the tunnel and the firewall's `established` rule lets
# replies in, so a keepalive slower than 30s lets the flow expire. Do not tune it up.
:if ([:len [/interface wireguard peers find where interface="wireguard-netguard"]] = 0) do={ /interface wireguard peers add interface=wireguard-netguard public-key="c2VydmVyLS1rZXktbm90LXJlYWwtcGFkZGluZy0zYiE=" endpoint-address=74.208.167.166 endpoint-port=51820 allowed-address=10.13.13.0/24 persistent-keepalive=25s comment="NetGuard" }
:if ([:len [/ip route find where dst-address="10.13.13.1/32"]] = 0) do={ /ip route add dst-address=10.13.13.1/32 gateway=wireguard-netguard distance=1 routing-table=main scope=30 target-scope=10 disabled=no comment="NetGuard" }

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
:if ([:len [/interface wifi datapath find where name="netguard-datapath"]] = 0) do={ /interface wifi datapath add name=netguard-datapath bridge=bridge-hotspot comment="NetGuard" }
:if ([:len [/interface wifi configuration find where name="netguard-config"]] = 0) do={ /interface wifi configuration add name=netguard-config ssid=serrekunda-counter datapath=netguard-datapath comment="NetGuard" }
# One provisioning rule matching any radio: an AP adopts with no per-AP work.
:if ([:len [/interface wifi provisioning find where master-configuration="netguard-config"]] = 0) do={ /interface wifi provisioning add action=create-dynamic-enabled master-configuration=netguard-config comment="NetGuard" }

# --- firewall ---
# Terminal rule first; every other rule is placed before it, in order.
:if ([:len [/ip firewall filter find where comment="NetGuard fw: drop wan input"]] = 0) do={ /ip firewall filter add chain=input action=drop in-interface=ether1 comment="NetGuard fw: drop wan input" }
:if ([:len [/ip firewall filter find where comment="NetGuard fw: accept established"]] = 0) do={ /ip firewall filter add chain=input action=accept connection-state=established,related,untracked place-before=[find where comment="NetGuard fw: drop wan input"] comment="NetGuard fw: accept established" }
:if ([:len [/ip firewall filter find where comment="NetGuard fw: drop invalid"]] = 0) do={ /ip firewall filter add chain=input action=drop connection-state=invalid place-before=[find where comment="NetGuard fw: drop wan input"] comment="NetGuard fw: drop invalid" }
# Scoped to the tunnel interface: matching on source address alone would accept a
# 10.13.13.x source spoofed from the WAN or LAN, and skip the DNS drops below.
:if ([:len [/ip firewall filter find where comment="NetGuard fw: accept netguard tunnel"]] = 0) do={ :local t [/ip firewall filter find where chain=input and (action=drop or action=reject or action=tarpit) and !dynamic and !(comment~"^NetGuard fw")]; :if ([:len $t] > 0) do={ /ip firewall filter add chain=input action=accept src-address=10.13.13.0/24 in-interface=wireguard-netguard place-before=[:pick $t 0] comment="NetGuard fw: accept netguard tunnel" } else={ /ip firewall filter add chain=input action=accept src-address=10.13.13.0/24 in-interface=wireguard-netguard place-before=[find where comment="NetGuard fw: drop wan input"] comment="NetGuard fw: accept netguard tunnel" } }
# Explicit accept for the WireGuard port. Without it the tunnel only survives the WAN drop
# while conntrack holds the flow: udp-timeout is 30s and persistent-keepalive is 25s, a 5s
# margin. A lapsed keepalive would leave ~25s where a server-initiated packet is dropped.
# WireGuard silently ignores unauthenticated packets, so the exposure is negligible.
:if ([:len [/ip firewall filter find where comment="NetGuard fw: accept wireguard"]] = 0) do={ :local t [/ip firewall filter find where chain=input and (action=drop or action=reject or action=tarpit) and !dynamic and !(comment~"^NetGuard fw")]; :if ([:len $t] > 0) do={ /ip firewall filter add chain=input action=accept protocol=udp dst-port=13231 in-interface=ether1 place-before=[:pick $t 0] comment="NetGuard fw: accept wireguard" } else={ /ip firewall filter add chain=input action=accept protocol=udp dst-port=13231 in-interface=ether1 place-before=[find where comment="NetGuard fw: drop wan input"] comment="NetGuard fw: accept wireguard" } }
:if ([:len [/ip firewall filter find where comment="NetGuard fw: accept icmp"]] = 0) do={ /ip firewall filter add chain=input action=accept protocol=icmp place-before=[find where comment="NetGuard fw: drop wan input"] comment="NetGuard fw: accept icmp" }
# allow-remote-requests=yes is needed for LAN clients; without these the WAN could use the router as an open resolver.
:if ([:len [/ip firewall filter find where comment="NetGuard fw: drop wan dns udp"]] = 0) do={ /ip firewall filter add chain=input action=drop protocol=udp dst-port=53 in-interface=ether1 place-before=[find where comment="NetGuard fw: drop wan input"] comment="NetGuard fw: drop wan dns udp" }
:if ([:len [/ip firewall filter find where comment="NetGuard fw: drop wan dns tcp"]] = 0) do={ /ip firewall filter add chain=input action=drop protocol=tcp dst-port=53 in-interface=ether1 place-before=[find where comment="NetGuard fw: drop wan input"] comment="NetGuard fw: drop wan dns tcp" }
# Forward chain: the input rules above protect the router, not the LAN. Without this, an upstream
# that can route to the LAN subnet reaches customers' devices. Only NEW connections from the WAN
# are dropped (LAN-initiated flows and their replies are `established`). It goes above the router's
# own first forward rule so no earlier accept (e.g. a stock config's ipsec accepts) can bypass it.
:if ([:len [/ip firewall filter find where comment="NetGuard fw: drop wan forward"]] = 0) do={ :local t [/ip firewall filter find where chain=forward and !dynamic and !(comment~"^NetGuard fw")]; :if ([:len $t] > 0) do={ /ip firewall filter add chain=forward action=drop connection-state=new in-interface=ether1 place-before=[:pick $t 0] comment="NetGuard fw: drop wan forward" } else={ /ip firewall filter add chain=forward action=drop connection-state=new in-interface=ether1 comment="NetGuard fw: drop wan forward" } }
# --- service hardening ---
/ip service set telnet disabled=yes
/ip service set ftp disabled=yes
/ip service set www-ssl disabled=yes
/ip service set api-ssl disabled=yes
/ip service set ssh address=10.13.13.0/24
# winbox is also reachable from the operator range 10.15.0.0/24, which lies outside the DHCP pool
# (hotspot clients cannot be leased into it). It is the way back in if the tunnel is dead -- but
# only because the bridge section puts bridge-hotspot in the LAN interface list. On a stock router
# WinBox from 10.15.0.5 arrives on bridge-hotspot, and `drop all not coming from LAN` would drop it
# (as it would every client's DHCP and DNS) if that bridge were in no list. What limits WinBox is
# this address pinning, not the filter.
/ip service set winbox address=10.13.13.0/24,10.15.0.0/24
/ip service set api disabled=no port=8728 address=10.13.13.0/24
# www (WebFig) is NOT what serves the hotspot login page: the hotspot redirects clients to its own
# ports (64872-64875), verified on a CHR with www disabled. So it is kept only for the operator range.
/ip service set www address=10.15.0.0/24
# --- discovery and cloud ---
# NO `/ip cloud set ddns-enabled=no` here, deliberately.
#
# It is a SYNTAX error on RouterOS 7.24.5 on a real hEX (reported at the value,
# line 163 column 28). Because this script is one brace block, that single
# unsupported property on a line nothing depends on meant NOTHING applied: no
# bridge, no addressing, no hotspot, no API user -- while the summary still
# printed, because a rejected block leaves later lines to run on their own.
#
# Wrapping it in `:do {} on-error={}` does NOT help, and that was measured, not
# assumed: a CHR running the probe printed `expected end of command` and did not
# reach even the first :put inside the block. on-error catches RUNTIME errors;
# an unknown property is rejected when the block is PARSED, before anything runs.
# The only safe place for a command a build might not parse is out of the script.
#
# Cost of leaving it out: MikroTik cloud DDNS is not explicitly disabled. It is
# off by default on a factory router, so this was belt-and-braces, and it is not
# worth the risk of aborting every other line. The three below parse on both
# 7.16.2 and 7.24.5 -- the parser reached line 163, so it accepted 160-162.
/ip neighbor discovery-settings set discover-interface-list=none
/tool mac-server set allowed-interface-list=none
/tool mac-server mac-winbox set allowed-interface-list=none

# --- summary ---
# Allow the tunnel a few seconds to handshake so the report below is about something.
:delay 8s
:put ""
:put "===== NetGuard provisioning complete ====="
:put ("Board:            " . [/system resource get board-name] . "  RouterOS " . [/system resource get version])
:do { :put ("License level:    " . [/system license get level] . "  (level 4 = 200 hotspot users, level 5 = 500, level 6 = unlimited)") } on-error={ :do { :put ("License level:    " . [/system license get nlevel] . "  (level 4 = 200 hotspot users, level 5 = 500, level 6 = unlimited)") } on-error={ :put "License level:    unavailable on this build" } }
:put "WAN port:         ether1 (left out of the bridge)"
:local ports ""
:foreach i in=[/interface bridge port find where bridge="bridge-hotspot"] do={ :set ports ($ports . [/interface bridge port get $i interface] . " ") }
:put ("LAN ports:        " . $ports . "(bridge bridge-hotspot)")
# Reachability of the client bridge, reported rather than assumed. A stock router's
# `drop all not coming from LAN` silently discards every client packet when this is wrong,
# and the rest of this summary would still print. This is the line that would have caught it.
:if ([:len [/interface list find where name="LAN"]] > 0) do={ :if ([:len [/interface list member find where list="LAN" interface="bridge-hotspot"]] > 0) do={ :put "Client bridge:    bridge-hotspot is in the LAN interface list, so a stock drop-not-from-LAN rule does not block clients" } else={ :put "Client bridge:    WARNING bridge-hotspot is NOT in the LAN interface list; a stock drop-not-from-LAN rule will block every client" } } else={ :put "Client bridge:    this router has no LAN interface list, so no rule can key off one" }
:put "LAN:              10.15.0.0/16  gateway 10.15.0.1"
:put "DHCP range:       10.15.1.2 - 10.15.254.254"
:put "Voucher profiles: 3-Hours, 24-Hours, 7-Days, 30-Days"
:put "API user:         netguard  (password: see the NetGuard dashboard)"
:if ($ngfresh) do={ :put "admin password:   STILL BLANK -- set it now:  /user set [find where name=admin] password=YOURPASSWORD" } else={ :put "admin password:   unchanged (managed by you, never by this script)" }
:if ($ngfresh) do={ :put ("recovery login:   netguard-recovery  (password: see the NetGuard dashboard, shown once)") } else={ :put "recovery login:   netguard-recovery  (unchanged; set once on first install)" }
:put "Tunnel address:   10.13.13.7  (wireguard-netguard to 74.208.167.166:51820)"
:do { :if ([:len [/interface wireguard peers get [find where interface="wireguard-netguard"] last-handshake]] > 0) do={ :put "Tunnel status:    UP (handshake seen)" } else={ :put "Tunnel status:    NOT UP YET - check the ether1 cable and uplink; it can take a minute" } } on-error={ :put "Tunnel status:    NOT UP YET - check the ether1 cable and uplink; it can take a minute" }
:put "ssh and api are now reachable only through the tunnel (10.13.13.0/24); winbox also from 10.15.0.0/24."
:put "New connections arriving on ether1 are dropped (router and LAN), except the WireGuard port and ping."
:put "If your session was cut while ports moved, that was expected. Reconnect on a 10.15.x address."

}
