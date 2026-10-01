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


def raw_rule(name):
    return next(l for l in sections.firewall(P)
                if f'comment="NetGuard fw: {name}"' in l and " add " in l and not l.startswith("#"))


# Terminal actions, not just `drop`: a stock LAN guard written as `reject` (or `tarpit`) would otherwise be
# invisible and our tunnel accept would land BELOW it, with the script reporting success and the router
# unreachable. Pinned as a set so narrowing it back to drop-only goes red.
SELECT_STOCK_INPUT_DROP = ('find where chain=input and (action=drop or action=reject or action=tarpit) '
                           'and !dynamic and !(comment~"^NetGuard fw")]')


def test_forward_drop_rule_sits_above_the_routers_own_first_forward_rule():
    l = raw_rule("drop wan forward")
    assert "action=drop" in l and "connection-state=new" in l and "in-interface=ether1" in l
    # Above the first forward rule that is neither dynamic (the fasttrack dummy, the hotspot's) nor ours.
    assert 'find where chain=forward and !dynamic and !(comment~"^NetGuard fw")]' in l
    assert "place-before=[:pick $t 0]" in l
    # A blank router has no such rule: the else branch just appends.
    assert "else={ /ip firewall filter add chain=forward action=drop connection-state=new" in l


def test_no_firewall_rule_is_positioned_by_index():
    # `move ... destination=0` fails on a stock router that has the fasttrack rule: a builtin
    # "special dummy rule to show fasttrack counters" holds index 0 (`failure: cannot move builtin`),
    # which aborts the whole block. Nothing may claim an absolute position.
    raw = "\n".join(sections.firewall(P))
    assert "destination=" not in raw
    assert " move " not in raw


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


def test_tunnel_accepts_go_above_a_stock_routers_own_input_drop_not_by_index():
    # A stock config's `drop all not coming from LAN` sits above our terminal rule and would drop tunnel
    # traffic (wireguard-netguard is not in its LAN list) before our accept is reached. Target the first
    # input drop rule that is neither dynamic nor ours with place-before; with none (a blank router) fall
    # back to before our own terminal rule.
    for name in ("accept netguard tunnel", "accept wireguard"):
        l = raw_rule(name)
        assert SELECT_STOCK_INPUT_DROP in l, l
        assert "place-before=[:pick $t 0]" in l, l
        assert ':if ([:len $t] > 0)' in l, l
        assert 'else={ /ip firewall filter add' in l and \
            'place-before=[find where comment="NetGuard fw: drop wan input"]' in l.split("else=")[1], l


def test_input_selector_covers_every_terminal_action():
    from app.services.provisioning.sections import TERMINAL_ACTIONS
    assert set(TERMINAL_ACTIONS) == {"drop", "reject", "tarpit"}
    for name in ("accept netguard tunnel", "accept wireguard"):
        l = raw_rule(name)
        for action in ("drop", "reject", "tarpit"):
            assert f"action={action}" in l.split("place-before")[0], (name, action)


# ---------------------------------------------------------------------------
# The client bridge must be reachable for input on a FACTORY-FRESH router
# ---------------------------------------------------------------------------
# A defconf router's input chain ends with `drop all not coming from LAN`, which matches
# `in-interface-list=!LAN`, and defconf's `LAN` list has exactly one member: the bridge named
# `bridge`. This script creates `bridge-hotspot` and moves all seven customer ports onto it.
# With nothing putting that bridge in `LAN`, the drop rule discards every packet arriving on it:
# no DHCP lease, no DNS to the gateway, no captive portal -- after the script has printed
# "===== NetGuard provisioning complete =====" -- and the documented operator WinBox path from
# 10.15.0.0/24 is dead for the same reason. Three verification rounds missed it because the
# defconf reconstruction they used copied the filter RULES but not the `/interface list` wiring
# those rules key off. Measured on a CHR: BRIDGEHOTSPOT-IN-LAN=0, PORTS-ON-DEFCONF-BRIDGE=0.


def test_the_client_bridge_is_reachable_for_input_on_a_stock_router():
    """Written as a disjunction on purpose.

    There are two defensible fixes -- join the stock `LAN` interface list, or emit an accept
    for `in-interface=bridge-hotspot` above the stock drop-all -- and this branch chose the
    first. The test pins the PROPERTY, so swapping to the other fix later keeps it green while
    removing both goes red.
    """
    raw = "\n".join(raw_lines())
    joins_lan_list = (
        '/interface list member add list=LAN interface=bridge-hotspot' in raw
        and '/interface list find where name="LAN"' in raw
    )
    accepts_above_stock_drop = any(
        "in-interface=bridge-hotspot" in l and "action=accept" in l
        and SELECT_STOCK_INPUT_DROP in l and "place-before=[:pick $t 0]" in l
        for l in sections.firewall(P)
    )
    assert joins_lan_list or accepts_above_stock_drop, (
        "nothing makes bridge-hotspot reachable for input past a stock "
        "`drop all not coming from LAN`; every hotspot client would be dropped"
    )


def lan_join_line():
    return next(l for l in sections.bridge(P) if "/interface list member add" in l)


def test_the_lan_list_join_names_our_bridge_and_the_stock_list():
    l = lan_join_line()
    assert "list=LAN" in l and f"interface={P.bridge_name}" in l
    # Tagged like every other object we create, so an operator can tell what put it there.
    assert 'comment="NetGuard"' in l


def test_the_lan_list_join_is_skipped_when_the_router_has_no_lan_list():
    # A blank router has no interface lists, and nothing on it references `LAN`, so adding a
    # member would fail (`no such item`) or invent an object nothing reads. Outer guard is
    # `> 0` on the list existing -- the mirror of every other guard in this file.
    l = lan_join_line()
    assert l.startswith(':if ([:len [/interface list find where name="LAN"]] > 0) do={ ')
    # And we never create the list ourselves.
    assert "/interface list add" not in "\n".join(raw_lines())


def test_the_lan_list_join_is_idempotent():
    # Inner guard, so a second run does not add a duplicate member.
    l = lan_join_line()
    assert ('/interface list member find where list="LAN" '
            f'interface="{P.bridge_name}"]] = 0') in l


def test_the_client_bridge_is_never_put_in_the_wan_list():
    # `WAN` carries the defconf masquerade (`out-interface-list=WAN`) and the stock
    # `drop all from WAN not DSTNATed` forward rule. Putting the client bridge there would
    # NAT clients to themselves and drop their forwarded traffic.
    raw = "\n".join(raw_lines())
    assert "list=WAN" not in raw


def test_the_summary_reports_whether_the_client_bridge_is_in_the_lan_list():
    # The failure this guards against printed "provisioning complete" and served nothing.
    # The summary now states the one fact that distinguishes the two outcomes.
    s = "\n".join(sections.summary(P))
    assert '/interface list member find where list="LAN" interface="bridge-hotspot"' in s
    assert "WARNING" in s and "NOT in the LAN interface list" in s
