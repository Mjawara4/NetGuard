
:delay 5s
:put "===== VERIFY ====="
:put ("BRIDGEHOTSPOT-IN-LAN=" . [:len [/interface list member find where list="LAN" interface="bridge-hotspot"]])
:put ("LAN-MEMBER-COUNT=" . [:len [/interface list member find where list="LAN"]])
:foreach i in=[/interface list member find where list="LAN"] do={ :put ("LAN-MEMBER=" . [/interface list member get $i interface]) }
:put ("WAN-MEMBER-COUNT=" . [:len [/interface list member find where list="WAN"]])
:foreach i in=[/interface list member find where list="WAN"] do={ :put ("WAN-MEMBER=" . [/interface list member get $i interface]) }
:put ("COUNT ports-bridge-hotspot=" . [:len [/interface bridge port find where bridge="bridge-hotspot"]])
:put ("PORTS-ON-DEFCONF-BRIDGE=" . [:len [/interface bridge port find where bridge="bridge"]])
:put ("TUNNEL-ACCEPT-POS=" . [:pick [/ip firewall filter find where comment="NetGuard fw: accept netguard tunnel"] 0])
:put ("WG-ACCEPT-POS=" . [:pick [/ip firewall filter find where comment="NetGuard fw: accept wireguard"] 0])
:put ("STOCK-DROPALL-COUNT=" . [:len [/ip firewall filter find where comment~"not coming from LAN"]])
:foreach i in=[/ip firewall filter find where comment~"not coming from LAN"] do={ :put ("STOCK-DROPALL-POS=" . $i) }
:put ("ROUTE-DISABLED=" . [/ip route get [find where dst-address="10.13.13.1/32"] disabled])
:put ("WG-IFACE-COMMENT=" . [/interface wireguard get [find where name="wireguard-netguard"] comment])
:put ("NETGUARD-FW-RULE-COUNT=" . [:len [/ip firewall filter find where comment~"^NetGuard fw"]])
:put "----- input chain in table order (non-dynamic) -----"
# One brace block: a loose `:local` does not survive into the next /import command.
{ :local n 0; :foreach i in=[/ip firewall filter find where chain=input and !dynamic] do={ :put ("ORDER-INPUT " . $n . " | " . [/ip firewall filter get $i action] . " | " . [/ip firewall filter get $i comment]); :set n ($n + 1) } }
:put ("WINBOX-ADDR=" . [/ip service get [find where name="winbox"] address])
:put "===== END VERIFY ====="
