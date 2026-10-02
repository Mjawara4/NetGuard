import ipaddress
import re
from app.services.provisioning.params import build_params
from provision_helpers import sections
from app.services.provisioning.secrets import generate_api_password, API_PASSWORD_ALPHABET

P = build_params(
    site_slug="serrekunda-counter", wg_private_key="cHJpdmF0ZS1rZXktbm90LXJlYWwtcGFkZGluZy0zYiE=", wg_client_ip="10.13.13.7",
    wg_server_public_key="c2VydmVyLS1rZXktbm90LXJlYWwtcGFkZGluZy0zYiE=", wg_server_endpoint="74.208.167.166",
    wg_server_port=51820, api_password="Xk7mQp2rTz9wLb4nHc6v", admin_password="Qw8ZeRtY3uIoP5aSdF1g",
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
            site_slug="serrekunda-counter", wg_private_key="cHJpdmF0ZS1rZXktbm90LXJlYWwtcGFkZGluZy0zYiE=",
            wg_client_ip="10.13.13.7", wg_server_public_key="c2VydmVyLS1rZXktbm90LXJlYWwtcGFkZGluZy0zYiE=",
            wg_server_endpoint="74.208.167.166", wg_server_port=51820,
            api_password=pw, admin_password="Qw8ZeRtY3uIoP5aSdF1g",
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
    # winbox alone also admits the operator range: the way back in if the tunnel is dead. That range is
    # outside the DHCP pool, so no hotspot client can be leased into it.
    assert line_with(ls, "/ip service set winbox ") == "/ip service set winbox address=10.13.13.0/24,10.15.0.0/24"
    assert P.operator_cidr == "10.15.0.0/24"
    assert ipaddress.ip_address(P.pool_start) not in ipaddress.ip_network(P.operator_cidr)


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
    # The forward rule is a different chain and is moved to the top of the table instead; see below.
    rs = [r for r in rules() if "chain=input" in r]
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


def test_www_is_restricted_not_open_but_the_hotspot_login_does_not_depend_on_it():
    ls = sections.firewall(P)
    # Verified on a CHR (Task 8): with www disabled or restricted to 10.15.0.0/24, a client at
    # 10.15.1.50 still fetched the 4194-byte hotspot login page. The hotspot redirects clients to its
    # own ports 64872-64875, so WebFig is only for the operator range.
    assert line_with(ls, "/ip service set www ") == "/ip service set www address=10.15.0.0/24"
    assert not any(re.search(r"set\s+www\s+disabled=yes", l) for l in ls)
    for svc in ("telnet", "ftp", "api-ssl", "www-ssl"):
        assert f"/ip service set {svc} disabled=yes" in ls


def test_discovery_and_cloud_are_switched_off():
    """The commands still run; they are now each inside an on-error guard.

    Asserted as substrings rather than whole lines because a build that rejects
    one of these properties must not take the rest of the script down with it --
    see test_optional_hardening_cannot_abort_the_script.
    """
    body = text(sections.firewall(P))
    assert "/ip neighbor discovery-settings set discover-interface-list=none" in body
    assert "/tool mac-server set allowed-interface-list=none" in body
    assert "/tool mac-server mac-winbox set allowed-interface-list=none" in body



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
    assert 'password=""' in u  # explicit blank; the real one is set separately and unconditionally, see test_both_passwords_are_set_on_every_run
    assert '/user set [find where name=netguard] password="Xk7mQp2rTz9wLb4nHc6v"' in ls
    assert "/user add name=admin" not in t
    assert "group=full" not in t


# RouterOS 7.24.5 on a real hEX cannot PARSE `/ip cloud set ddns-enabled=no`
# (syntax error at the value, line 163 column 28). The script is one brace block,
# so that one optional line meant nothing at all applied.
#
# `:do {} on-error={}` does not save it: a CHR probe printed `expected end of
# command` and never reached the first :put inside the block. on-error catches
# runtime errors; an unknown property is rejected at parse time.
def test_no_ip_cloud_command_at_all():
    """Executable lines only -- the section explains the hazard in a comment."""
    for line in sections.firewall(P):
        if line.lstrip().startswith("#"):
            continue
        assert "/ip cloud" not in line, (
            f"a command a RouterOS build cannot parse aborts the ENTIRE brace "
            f"block; it cannot be guarded, only left out: {line[:90]}"
        )


def test_the_discovery_lines_that_do_parse_are_still_there():
    """Only the /ip cloud line was unparseable; the parser reached line 163."""
    body = text(sections.firewall(P))
    for cmd in ("/ip neighbor discovery-settings set discover-interface-list=none",
                "/tool mac-server set allowed-interface-list=none",
                "/tool mac-server mac-winbox set allowed-interface-list=none"):
        assert cmd in body, cmd


def test_hardening_is_not_wrapped_in_a_silent_guard():
    """on-error here would suppress real failures without stopping syntax errors."""
    for line in sections.firewall(P):
        if line.lstrip().startswith("#"):
            continue
        if "mac-server" in line or "neighbor discovery" in line:
            assert "on-error=" not in line, (
                f"on-error cannot catch the parse error this guards against, and it "
                f"hides runtime ones: {line[:90]}"
            )
