import re
from app.services.provisioning.params import build_params
from provision_helpers import sections

P = build_params(
    site_slug="serrekunda-counter",
    wg_private_key="cHJpdmF0ZS1rZXktbm90LXJlYWwtcGFkZGluZy0zYiE=", wg_client_ip="10.13.13.7",
    wg_server_public_key="c2VydmVyLS1rZXktbm90LXJlYWwtcGFkZGluZy0zYiE=",
    wg_server_endpoint="74.208.167.166", wg_server_port=51820,
    api_password="Xk7mQp2rTz9wLb4nHc6v", admin_password="Qw8ZeRtY3uIoP5aSdF1g",
)


def text(ls):
    return "\n".join(ls)


def cmds(ls, prefix):
    hits = [l for l in ls if l.startswith(prefix)]
    assert len(hits) == 1, (prefix, hits)
    return hits[0].split()


def test_wireguard_matches_the_conventions_monitoring_depends_on():
    ls = sections.wireguard(P)
    i = cmds(ls, "/interface wireguard add ")
    assert {"name=wireguard-netguard", "listen-port=13231", "mtu=1420"} <= set(i)
    peer = cmds(ls, "/interface wireguard peers add ")
    assert {"persistent-keepalive=25s", "endpoint-address=74.208.167.166",
            "endpoint-port=51820", "interface=wireguard-netguard"} <= set(peer)


def test_wireguard_peer_is_scoped_to_the_tunnel():
    ls = sections.wireguard(P)
    assert "allowed-address=10.13.13.0/24" in cmds(ls, "/interface wireguard peers add ")
    assert "0.0.0.0/0" not in text(ls)


def test_router_gets_its_tunnel_address_and_a_route_to_the_server():
    ls = sections.wireguard(P)
    a = cmds(ls, "/ip address add ")
    assert "address=10.13.13.7/24" in a and "interface=wireguard-netguard" in a
    r = cmds(ls, "/ip route add ")
    assert "dst-address=10.13.13.1/32" in r and "gateway=wireguard-netguard" in r


def test_keepalive_rationale_is_written_where_it_will_be_read():
    t = text(sections.wireguard(P))
    assert "30s conntrack UDP" in t


def test_capsman_uses_the_modern_stack_only():
    ls = sections.capsman(P)
    cmd = [l for l in ls if l.startswith("/")]
    assert cmd and all(l.startswith("/interface wifi ") for l in cmd)
    assert "/caps-man" not in "\n".join(cmd)
    assert "local-forwarding-only" in text(ls)


def test_capsman_puts_clients_on_the_hotspot_bridge():
    d = cmds(sections.capsman(P), "/interface wifi datapath add ")
    assert f"bridge={P.bridge_name}" in d
    assert P.bridge_name == "bridge-hotspot"


def test_capsman_provisions_any_ap_without_per_ap_work():
    prov = cmds(sections.capsman(P), "/interface wifi provisioning add ")
    assert "action=create-dynamic-enabled" in prov
    assert "master-configuration=netguard-config" in prov
    # No radio-mac / identity / supported-bands filter: any radio matches.
    assert not any(t.startswith(("radio-mac=", "identity-regexp=", "supported-bands=")) for t in prov)


def test_capsman_listens_on_the_lan_bridge_not_the_wan():
    c = cmds(sections.capsman(P), "/interface wifi capsman set ")
    assert "enabled=yes" in c and f"interfaces={P.bridge_name}" in c


# Carried from the Task 6 review.
def fw_rules():
    return [l for l in sections.firewall(P) if l.startswith("/ip firewall filter add ")]


def fw_index(name):
    for n, r in enumerate(fw_rules()):
        if r.endswith(f'comment="NetGuard fw: {name}"'):
            return n
    raise AssertionError(name)


def test_wireguard_port_has_an_explicit_accept_before_the_wan_drop():
    r = fw_rules()[fw_index("accept wireguard")].split()
    assert {"chain=input", "protocol=udp", "dst-port=13231", "in-interface=ether1",
            "action=accept"} <= set(r)
    rs = fw_rules()
    assert "place-before=[find where comment=\"NetGuard fw: drop wan input\"]" in rs[fw_index("accept wireguard")]
    assert fw_index("accept wireguard") > fw_index("drop wan input")  # terminal is added first, this is placed before it


def test_wireguard_accept_follows_the_wan_interface_param():
    p = build_params(site_slug="x-site", wg_private_key="cHJpdmF0ZS1rZXktbm90LXJlYWwtcGFkZGluZy0zYiE=", wg_client_ip="10.13.13.7",
                     wg_server_public_key="c2VydmVyLS1rZXktbm90LXJlYWwtcGFkZGluZy0zYiE=", wg_server_endpoint="74.208.167.166",
                     wg_server_port=51820, api_password="Xk7mQp2rTz9wLb4nHc6v", admin_password="Qw8ZeRtY3uIoP5aSdF1g")
    import dataclasses
    p = dataclasses.replace(p, wan_interface="sfp1")
    r = [l for l in sections.firewall(p) if l.endswith('NetGuard fw: accept wireguard"')][0]
    assert "in-interface=sfp1" in r.split() and "ether1" not in r


def test_tunnel_accept_is_scoped_to_the_tunnel_interface():
    r = fw_rules()[fw_index("accept netguard tunnel")].split()
    assert "src-address=10.13.13.0/24" in r
    assert "in-interface=wireguard-netguard" in r


def test_api_user_comment_is_present_on_group_and_user():
    ls = sections.api_user(P)
    for prefix in ("/user group add ", "/user add "):
        (line,) = [l for l in ls if l.startswith(prefix)]
        assert line.endswith(' comment="NetGuard API"'), line


def test_capsman_does_not_require_peer_certificates_by_decision():
    c = cmds(sections.capsman(P), "/interface wifi capsman set ")
    assert "require-peer-certificate=no" in c, (
        "require-peer-certificate is 'no' by decision, not oversight: per-AP certificates are not "
        "viable for 100+ self-provisioned APs and would break plug-in-any-port adoption. The risk "
        "(any LAN/bridge host can adopt as a CAP) is bounded by interfaces=<bridge>, and documented "
        "in sections.capsman. Do not flip this without changing that decision."
    )
    assert "ACCEPTED RISK" in text(sections.capsman(P))


def test_capsman_ssid_is_the_site_slug():
    # The name customers see on their phones.
    cfg = cmds(sections.capsman(P), "/interface wifi configuration add ")
    assert "ssid=serrekunda-counter" in cfg


def _wg_generator_tokens():
    """key=value tokens per command, parsed from WireGuardService's own script."""
    from app.services.wireguard import WireGuardService
    script = WireGuardService.generate_mikrotik_script(
        "cHJpdmF0ZS1rZXktbm90LXJlYWwtcGFkZGluZy0zYiE=", "10.13.13.7",
        "c2VydmVyLS1rZXktbm90LXJlYWwtcGFkZGluZy0zYiE=", "74.208.167.166", 51820)
    out, menu = {}, None
    for line in script.replace("\\\n", " ").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("/"):
            menu = line
            continue
        if line.startswith("add "):
            out[menu] = dict(t.split("=", 1) for t in line.split() if "=" in t)
    return out


def test_sections_wireguard_has_not_drifted_from_the_wireguard_service():
    # NetGuard reaches each device at its tunnel address; provisioned and
    # re-keyed routers must agree on these values.
    theirs = _wg_generator_tokens()
    ours = sections.wireguard(P)

    def mine(prefix):
        return dict(t.split("=", 1) for t in cmds(ours, prefix) if "=" in t)

    iface = mine("/interface wireguard add ")
    peer = mine("/interface wireguard peers add ")
    route = mine("/ip route add ")
    addr = mine("/ip address add ")
    t_iface, t_peer = theirs["/interface wireguard"], theirs["/interface wireguard peers"]
    t_route, t_addr = theirs["/ip route"], theirs["/ip address"]
    for k in ("name", "listen-port", "mtu"):
        assert iface[k] == t_iface[k], k
    for k in ("allowed-address", "interface", "persistent-keepalive"):
        assert peer[k] == t_peer[k], k
    for k in ("dst-address", "gateway", "distance", "routing-table", "scope", "target-scope"):
        assert route[k] == t_route[k], k
    for k in ("address", "interface", "network"):
        assert addr[k] == t_addr[k].replace("{client_ip}", "10.13.13.7"), k
