import re
from app.services.provisioning.params import build_params
from app.services.provisioning import sections
from app.services.provisioning.secrets import generate_api_password, API_PASSWORD_ALPHABET

P = build_params(
    site_slug="serrekunda-counter", wg_private_key="k" * 44, wg_client_ip="10.13.13.7",
    wg_server_public_key="k" * 44, wg_server_endpoint="74.208.167.166",
    wg_server_port=51820, api_password="Xk7mQp2rTz9wLb4nHc6v",
)


def text(ls):
    return "\n".join(ls)


def line_with(ls, prefix):
    hits = [l for l in ls if l.startswith(prefix)]
    assert len(hits) == 1, (prefix, hits)
    return hits[0]


def rules():
    return [l for l in sections.firewall(P) if l.startswith("/ip firewall filter add ")]


def rule(name):
    hits = [l for l in rules() if l.endswith(f'comment="NetGuard fw: {name}"')]
    assert len(hits) == 1, (name, hits)
    return hits[0]


# Review Focus #4 -- a password RouterOS would mis-parse.
def test_generated_password_cannot_break_routeros_quoting():
    for ch in '"\'$\\;{} \n\r\t`':
        assert ch not in API_PASSWORD_ALPHABET
    for _ in range(200):
        pw = generate_api_password()
        assert len(pw) == 24
        assert re.fullmatch(r"[A-Za-z0-9]{24}", pw), pw


def test_generated_passwords_are_accepted_by_params_validation():
    for _ in range(200):
        pw = generate_api_password()
        assert build_params(
            site_slug="serrekunda-counter", wg_private_key="k" * 44,
            wg_client_ip="10.13.13.7", wg_server_public_key="k" * 44,
            wg_server_endpoint="74.208.167.166", wg_server_port=51820,
            api_password=pw,
        ).api_password == pw


def test_passwords_are_not_predictable():
    assert len({generate_api_password() for _ in range(50)}) == 50


def test_api_service_is_pinned_to_the_tunnel_not_the_world():
    ls = sections.firewall(P)
    l = line_with(ls, "/ip service set api ")
    assert l == "/ip service set api disabled=no port=8728 address=10.13.13.0/24"
    assert "0.0.0.0/0" not in text(ls)
    assert "0.0.0.0/0" not in text(sections.api_user(P))


def test_ssh_and_winbox_are_pinned_to_the_tunnel():
    ls = sections.firewall(P)
    assert line_with(ls, "/ip service set ssh ") == "/ip service set ssh address=10.13.13.0/24"
    assert line_with(ls, "/ip service set winbox ") == "/ip service set winbox address=10.13.13.0/24"


def test_router_is_not_an_open_dns_resolver():
    # allow-remote-requests=yes is required for clients, so the WAN must be shut.
    for proto in ("udp", "tcp"):
        l = rule(f"drop wan dns {proto}").split()
        assert "action=drop" in l
        assert f"protocol={proto}" in l
        assert "dst-port=53" in l
        assert "in-interface=ether1" in l
        assert "chain=input" in l


def test_wan_input_is_dropped_last_and_only_from_the_wan():
    l = rule("drop wan input").split()
    assert "action=drop" in l and "in-interface=ether1" in l and "chain=input" in l
    assert not any(t.startswith(("protocol=", "dst-port=", "connection-state=", "src-address=")) for t in l)


def test_rule_order_is_explicit_and_terminal_rule_is_last_in_effect():
    rs = rules()
    # Terminal rule is added first, and every other rule is placed before it.
    assert 'comment="NetGuard fw: drop wan input"' in rs[0]
    assert "place-before" not in rs[0]
    for r in rs[1:]:
        assert 'place-before=[find where comment="NetGuard fw: drop wan input"]' in r
    order = [re.search(r'comment="NetGuard fw: ([^"]+)"$', r).group(1) for r in rs[1:]]
    assert order == ["accept established", "drop invalid", "accept netguard tunnel",
                     "accept wireguard", "accept icmp", "drop wan dns udp", "drop wan dns tcp"]


def test_established_invalid_tunnel_and_icmp_rules():
    assert "connection-state=established,related,untracked" in rule("accept established").split()
    assert "action=accept" in rule("accept established").split()
    assert "connection-state=invalid" in rule("drop invalid").split()
    assert "action=drop" in rule("drop invalid").split()
    t = rule("accept netguard tunnel").split()
    assert "src-address=10.13.13.0/24" in t and "in-interface=wireguard-netguard" in t and "action=accept" in t and "chain=input" in t
    i = rule("accept icmp").split()
    assert "protocol=icmp" in i and "action=accept" in i


def test_hotspot_login_page_is_not_broken_by_hardening():
    ls = sections.firewall(P)
    # www serves the captive portal; disabling it would silently kill logins.
    assert not any(l.startswith("/ip service set www ") for l in ls)
    assert not any(re.search(r"set\s+www\s", l) for l in ls if not l.startswith("#"))
    for svc in ("telnet", "ftp", "api-ssl", "www-ssl"):
        assert f"/ip service set {svc} disabled=yes" in ls


def test_discovery_and_cloud_are_switched_off():
    ls = sections.firewall(P)
    assert "/ip neighbor discovery-settings set discover-interface-list=none" in ls
    assert "/tool mac-server set allowed-interface-list=none" in ls
    assert "/tool mac-server mac-winbox set allowed-interface-list=none" in ls
    assert "/ip cloud set ddns-enabled=no" in ls


def test_api_user_is_least_privilege_and_source_restricted():
    ls = sections.api_user(P)
    t = text(ls)
    g = line_with(ls, "/user group add ").split()
    assert "name=netguard" in g
    policy = next(x for x in g if x.startswith("policy=")).removeprefix("policy=").split(",")
    for granted in ("api", "read", "write", "test", "winbox"):
        assert granted in policy
    for denied in ("local", "telnet", "ssh", "ftp", "reboot", "policy", "password",
                   "sniff", "sensitive", "romon"):
        assert f"!{denied}" in policy
        assert denied not in policy  # not granted as well
    u = line_with(ls, "/user add ")
    assert "name=netguard" in u.split()
    assert "group=netguard" in u.split()
    assert "address=10.13.13.0/24" in u.split()
    assert 'password="Xk7mQp2rTz9wLb4nHc6v"' in u.split()
    assert "name=admin" not in t
    assert "group=full" not in t
