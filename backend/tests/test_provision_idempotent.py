"""A factory-fresh router is not blank, and a failed run must be re-runnable.

Confirmed on RouterOS 7.16.2 (Task 8 review): a stock router already has
ether2-ether5 in a bridge called `bridge`, so a plain `bridge port add` fails
mid-script. These tests read the RAW section output (not the unwrapped view the
older tests use) because the guards are the thing under test. The behaviour
itself is proven on a CHR; see the Task 8 report.
"""
import re

import pytest

from app.services.provisioning.params import build_params
from app.services.provisioning import sections

KEY = "cHJpdmF0ZS1rZXktbm90LXJlYWwtcGFkZGluZy0zYiE="
PUB = "c2VydmVyLS1rZXktbm90LXJlYWwtcGFkZGluZy0zYiE="
OK = dict(
    site_slug="serrekunda-counter", wg_private_key=KEY, wg_client_ip="10.13.13.7",
    wg_server_public_key=PUB, wg_server_endpoint="74.208.167.166", wg_server_port=51820,
    api_password="Xk7mQp2rTz9wLb4nHc6v", admin_password="Qw8ZeRtY3uIoP5aSdF1g",
)
P = build_params(**OK)
BUILDERS = ("identity_and_clock", "bridge", "addressing", "dns_and_nat", "hotspot_server",
            "voucher_profiles", "walled_garden", "api_user", "wireguard", "capsman", "firewall")


def raw_lines():
    return [l for name in BUILDERS for l in getattr(sections, name)(P)]


def test_every_created_object_is_guarded_on_its_own_existence():
    seen = 0
    for l in raw_lines():
        if l.startswith("#") or " add " not in l:
            continue
        seen += 1
        m = re.match(r":if \(\[:len \[(/[a-z -]+?) find where [^\]]+\]\] (=|>) 0\) do=\{ ", l)
        assert m, f"unguarded add: {l}"
        # The guard must look at the same menu the add creates in (a copy-paste slip would
        # silently guard against the wrong table). Bridge ports guard on /interface first.
        if m.group(2) == "=":
            assert f" {m.group(1)} add " in l, l
            # ...and it must look for the very thing the add creates. A guard on the wrong
            # name is always empty, so the object is re-created on every run and collides.
            find = re.search(r" find where ([^\]]+)\]\]", l).group(1)
            add = l.split(" add ", 1)[1].replace('"', "")
            for key, val in re.findall(r'(\S+?)=("[^"]*"|\S+)', find):
                assert f"{key}={val.strip(chr(34))}" in add, (key, val, l)
    assert seen >= 40, seen


def test_ports_are_moved_out_of_any_existing_bridge_before_being_added():
    ports = [l for l in sections.bridge(P) if "/interface bridge port add" in l]
    assert len(ports) == 10  # ether2-8 plus wifi1, wifi2, wlan1
    for l in ports:
        name = re.search(r"interface=(\w+) ", l).group(1)
        remove = l.index(f'/interface bridge port remove [find where interface="{name}"]')
        add = l.index("/interface bridge port add ")
        assert remove < add, l
        # Skipped when already ours, so a re-run does not bounce a live port.
        assert f'interface="{name}" bridge="bridge-hotspot"]] = 0' in l, l


def test_the_bridge_itself_is_created_only_if_missing():
    l = next(l for l in sections.bridge(P) if "/interface bridge add" in l)
    assert 'find where name="bridge-hotspot"]] = 0' in l


def test_preflight_refuses_a_foreign_hotspot_but_tolerates_our_own_leftovers():
    t = "\n".join(sections.preflight(P))
    assert '/ip hotspot find where name!="netguard"' in t
    assert 'wireguard find where name="wireguard-netguard" and comment!="NetGuard"' in t
    assert ":error" in t


def test_forward_drop_rule_is_first_and_only_matches_new_wan_connections():
    l = next(l for l in sections.firewall(P) if "chain=forward" in l and not l.startswith("#"))
    assert "action=drop" in l and "connection-state=new" in l and "in-interface=ether1" in l
    assert 'comment="NetGuard fw: drop wan forward"' in l
    # Moved to the top of the table so a stock router's earlier accepts cannot bypass it.
    assert '/ip firewall filter move [find where comment="NetGuard fw: drop wan forward"] destination=0' in l


def test_forward_rule_follows_the_wan_interface_param():
    p = build_params(**OK)
    from dataclasses import replace
    l = next(l for l in sections.firewall(replace(p, wan_interface="ether9")) if "chain=forward" in l and not l.startswith("#"))
    assert "in-interface=ether9" in l


def test_admin_gets_its_own_password_and_it_is_the_only_place_it_appears():
    text = "\n".join(raw_lines())
    assert text.count(P.admin_password) == 1
    assert f'/user set [find where name=admin] password="{P.admin_password}"' in text
    assert P.admin_password != P.api_password
    assert P.admin_password not in "\n".join(sections.summary(P))


def test_admin_password_must_differ_from_the_api_password():
    with pytest.raises(ValueError, match="admin_password"):
        build_params(**{**OK, "admin_password": OK["api_password"]})


@pytest.mark.parametrize("bad", ["", 'a"b', "with space", "semi;colon", "trailing\n"])
def test_admin_password_is_validated_like_the_api_password(bad):
    with pytest.raises(ValueError, match="admin_password"):
        build_params(**{**OK, "admin_password": bad})


def test_wireguard_keys_must_decode_to_exactly_32_bytes():
    import base64
    for n in (24, 31, 33, 36):
        bad = base64.b64encode(b"k" * n).decode()
        for field in ("wg_private_key", "wg_server_public_key"):
            with pytest.raises(ValueError, match=field):
                build_params(**{**OK, field: bad})
    good = base64.b64encode(b"k" * 32).decode()
    build_params(**{**OK, "wg_private_key": good, "wg_server_public_key": good})


def test_a_33_byte_key_that_the_old_length_check_accepted_is_now_rejected():
    # Passed the old ">= 40 chars, base64" check; RouterOS then failed mid-script with
    # `failure: invalid private key`.
    import base64
    key = base64.b64encode(b"private-key-not-real-padding-32b!").decode()
    assert len(key) >= 40
    with pytest.raises(ValueError, match="32 bytes"):
        build_params(**{**OK, "wg_private_key": key})


def test_www_is_kept_for_the_operator_range_only():
    l = [l for l in sections.firewall(P) if l.startswith("/ip service set www ")]
    assert l == ["/ip service set www address=10.15.0.0/24"]


def test_tunnel_accepts_are_moved_above_a_stock_routers_own_drop_rules():
    # A stock config's `drop all not coming from LAN` sits above our terminal rule. Without the move,
    # tunnel traffic (in-interface=wireguard-netguard) is dropped before our accept is reached.
    fw = [l for l in sections.firewall(P) if not l.startswith("#")]
    for name in ("accept netguard tunnel", "accept wireguard"):
        l = next(l for l in fw if f'comment="NetGuard fw: {name}"' in l and " add " in l)
        assert f'move [find where comment="NetGuard fw: {name}"] destination=0' in l, l


def test_both_passwords_are_set_on_every_run_not_only_when_the_user_is_created():
    # Guarding `/user add` alone meant a re-run with a NEW api_password never reached the router while
    # admin's did: NetGuard would hold a credential the router lacked. So: add-if-missing, then an
    # unconditional `set`. Read from the RAW lines, where the guard is visible.
    raw = sections.api_user(P)
    for user, pw in (("netguard", P.api_password), ("admin", P.admin_password)):
        sets = [l for l in raw if l == f'/user set [find where name={user}] password="{pw}"']
        assert len(sets) == 1, (user, sets)   # unguarded: a bare top-level command
        assert not sets[0].startswith(":if")
    add = next(l for l in raw if l.startswith(":if") and "/user add name=netguard" in l)
    # An explicit empty password: omitting it makes /import fail and an interactive paste prompt.
    assert 'password=""' in add
    assert P.api_password not in add   # the secret appears once, in the set
    assert "\n".join(raw).count(P.api_password) == 1
