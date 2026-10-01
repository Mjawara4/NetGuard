# Reconstructed MikroTik RouterOS 7.16 default configuration (defconf), as a new
# hAP/L009-class router ships. Prepended in the SAME session as the script under test,
# because once `drop all not coming from LAN` is in place the router refuses NEW ssh
# connections on ether1, the harness's only path in.
#
# WHAT IS DIFFERENT FROM THE RECONSTRUCTION USED IN EARLIER ROUNDS, and the whole reason
# this file exists: the `/interface list` + `/interface list member` wiring. Rounds 1-3
# copied the defconf filter RULES but not the lists those rules key off, so
# `in-interface-list=!LAN` matched nothing and the rule looked harmless. That omission is
# exactly what hid BLOCKING 1.
#
# Everything a stock config ships, in defconf's own order:
/interface bridge add name=bridge comment=defconf
/interface bridge port add bridge=bridge interface=ether2 comment=defconf
/interface bridge port add bridge=bridge interface=ether3 comment=defconf
/interface bridge port add bridge=bridge interface=ether4 comment=defconf
/interface bridge port add bridge=bridge interface=ether5 comment=defconf
/interface bridge port add bridge=bridge interface=ether6 comment=defconf
/interface bridge port add bridge=bridge interface=ether7 comment=defconf
/interface bridge port add bridge=bridge interface=ether8 comment=defconf
# --- the interface lists the firewall keys off (THE PART EARLIER ROUNDS OMITTED) ---
/interface list add name=LAN comment=defconf
/interface list add name=WAN comment=defconf
/interface list member add list=LAN interface=bridge comment=defconf
/interface list member add list=WAN interface=ether1 comment=defconf
# --- stock addressing on the stock bridge ---
/ip address add address=192.168.88.1/24 interface=bridge comment=defconf
/ip pool add name=default-dhcp ranges=192.168.88.10-192.168.88.254
/ip dhcp-server add name=defconf address-pool=default-dhcp interface=bridge lease-time=10m comment=defconf
/ip dhcp-server network add address=192.168.88.0/24 gateway=192.168.88.1 dns-server=192.168.88.1 comment=defconf
/ip dns set allow-remote-requests=yes
# --- discovery, keyed on LAN, as defconf leaves it ---
/ip neighbor discovery-settings set discover-interface-list=LAN
/tool mac-server set allowed-interface-list=LAN
/tool mac-server mac-winbox set allowed-interface-list=LAN
# --- input chain ---
/ip firewall filter add action=accept chain=input comment="defconf: accept established,related,untracked" connection-state=established,related,untracked
/ip firewall filter add action=drop chain=input comment="defconf: drop invalid" connection-state=invalid
/ip firewall filter add action=accept chain=input comment="defconf: accept ICMP" protocol=icmp
/ip firewall filter add action=accept chain=input comment="defconf: accept to local loopback (for CAPsMAN)" dst-address=127.0.0.1
/ip firewall filter add action=drop chain=input comment="defconf: drop all not coming from LAN" in-interface-list=!LAN
# --- forward chain, fasttrack included: it is what makes RouterOS expose a builtin
#     `special dummy rule to show fasttrack counters` at index 0 ---
/ip firewall filter add action=accept chain=forward comment="defconf: accept in ipsec policy" ipsec-policy=in,ipsec
/ip firewall filter add action=accept chain=forward comment="defconf: accept out ipsec policy" ipsec-policy=out,ipsec
/ip firewall filter add action=fasttrack-connection chain=forward comment="defconf: fasttrack" connection-state=established,related
/ip firewall filter add action=accept chain=forward comment="defconf: accept established,related, untracked" connection-state=established,related,untracked
/ip firewall filter add action=drop chain=forward comment="defconf: drop invalid" connection-state=invalid
/ip firewall filter add action=drop chain=forward comment="defconf: drop all from WAN not DSTNATed" connection-nat-state=!dstnat connection-state=new in-interface-list=WAN
# --- the defconf masquerade, keyed on the WAN list ---
/ip firewall nat add action=masquerade chain=srcnat comment="defconf: masquerade" ipsec-policy=out,none out-interface-list=WAN
