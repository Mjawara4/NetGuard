"""The connect-only script: joins a router that already runs a hotspot.

It must add NetGuard's way in and nothing else. Every test here is about
something it leaves alone, because the router it runs on is in service.
"""
import re

from app.services.provisioning import sections
from app.services.provisioning.connect import build_connect_script
from app.services.provisioning.params import build_params
from app.services.provisioning.script import build_provision_script

P = build_params(
    site_slug="kumbija", wg_private_key="cHJpdmF0ZS1rZXktbm90LXJlYWwtcGFkZGluZy0zYiE=", wg_client_ip="10.13.13.7",
    wg_server_public_key="c2VydmVyLS1rZXktbm90LXJlYWwtcGFkZGluZy0zYiE=", wg_server_endpoint="74.208.167.166",
    wg_server_port=51820, api_password="Xk7mQp2rTz9wLb4nHc6v", recovery_password="Qw8ZeRtY3uIoP5aSdF1g",
    device_id="11111111-1111-1111-1111-111111111111",
)
S = build_connect_script(P)


def commands(script=S):
    return [l for l in script.splitlines() if l and not l.startswith("#")]


def test_it_is_one_brace_block_like_the_full_script():
    lines = S.splitlines()
    assert lines[0] == "{" and lines[-1] == "}"


def test_it_requires_a_hotspot_and_points_a_blank_router_at_the_full_setup():
    assert ':if ([:len [/ip hotspot find]] = 0) do={ :error "NetGuard: this router has no hotspot' in S
    assert "full setup" in S


def test_the_full_script_points_a_router_with_a_hotspot_at_this_one():
    full = build_provision_script(P)
    assert "refusing to overwrite it" in full and "existing hotspot" in full


def test_it_never_touches_the_owners_network_hotspot_or_login_page():
    for menu in ("/interface bridge", "/ip pool", "/ip dhcp-server", "/ip dns", "/ip firewall nat",
                 "/ip hotspot add", "/ip hotspot profile", "/ip hotspot user", "/ip hotspot set",
                 "/file", "/system identity", "/system clock", "/system ntp", "/interface wifi",
                 "/ip neighbor", "/tool mac-server", "/interface list"):
        assert not any(menu in c for c in commands()), menu


def test_it_leaves_every_service_but_the_api_alone():
    services = [c for c in commands() if "/ip service set" in c]
    assert services and all("/ip service set api" in c for c in services)
    assert "port=" not in " ".join(services)


def test_api_access_is_added_to_the_owners_allow_list_not_swapped_for_it():
    # Something of theirs (Mikhmon, their own scripts) may already use the API.
    assert ":local ngApi [/ip service get api address]" in S
    assert "/ip service set api address=($ngApi , 10.13.13.0/24)" in S
    # An API that was off is switched on for the tunnel only, never for everyone.
    assert ":if ([/ip service get api disabled]) do={ /ip service set api disabled=no address=10.13.13.0/24 }" in S


def test_it_adds_no_drop_rule_and_removes_nothing():
    # (`action=drop` does appear: in the query that finds the owner's drop to sit above.)
    assert not re.search(r" add [^}]*action=(drop|reject|tarpit)", S)
    assert not re.search(r"\b(remove|disable|move)\b", " ".join(commands()))
    assert "chain=forward" not in S


def test_the_tunnel_accept_goes_above_the_owners_own_drop():
    line = next(c for c in commands() if "accept netguard tunnel" in c)
    assert "place-before=[:pick $t 0]" in line
    assert "in-interface=wireguard-netguard" in line and "src-address=10.13.13.0/24" in line


def test_it_does_not_fight_a_wireguard_interface_already_on_the_default_port():
    assert ":local ngPort 13231" in S
    assert ':while ([:len [/interface wireguard find where listen-port=$ngPort and name!="wireguard-netguard"]] > 0) do={ :set ngPort ($ngPort + 1) }' in S
    assert "listen-port=$ngPort" in S


def test_it_refuses_a_router_whose_own_network_is_the_tunnel_range():
    assert 'network in 10.13.13.0/24 and interface!="wireguard-netguard"' in S


def test_it_creates_the_api_user_but_no_full_access_account():
    assert '/user set [find where name=netguard] password="Xk7mQp2rTz9wLb4nHc6v"' in S
    assert "netguard-recovery" not in " ".join(commands())
    assert "group=full" not in S


def test_only_the_payment_hosts_join_the_walled_garden():
    garden = " ".join(c for c in commands() if "walled-garden" in c)
    assert "app.netguard.fun" in garden and "checkout.modempay.com" in garden
    # Captive-portal detection is the owner's hotspot's business, not ours.
    for host in ("captive.apple.com", "connectivitycheck.gstatic.com", "msftconnecttest", "login.netguard.local"):
        assert host not in garden


def test_everything_it_adds_is_guarded_so_it_can_be_run_again():
    for c in commands():
        if re.search(r"/[a-z -]+ add ", c):
            assert c.startswith(":if ([:len ["), c


def test_the_full_script_is_unchanged_by_the_shared_helpers():
    lines = sections.walled_garden(P)
    assert any("captive.apple.com" in l for l in lines)
    assert any("login.netguard.local" in l for l in lines)


def test_the_https_walled_garden_guard_can_recognise_its_own_entries():
    # Unquoted, the guard matched nothing on a real RouterOS and a re-run doubled the list.
    for line in sections.walled_garden(P):
        if "walled-garden ip" in line:
            assert 'protocol="tcp" and dst-port="' in line.split("] = 0)")[0], line
