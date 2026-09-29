import pytest
from app.services.provisioning.params import build_params

OK = dict(
    site_slug="serrekunda-counter",
    wg_private_key="cHJpdmF0ZS1rZXktbm90LXJlYWwtYnV0LWxvbmctZW5vdWdo",
    wg_client_ip="10.13.13.7",
    wg_server_public_key="c2VydmVyLXB1YmxpYy1rZXktbm90LXJlYWwtYnV0LWxvbmc=",
    wg_server_endpoint="74.208.167.166",
    wg_server_port=51820,
    api_password="Xk7mQp2rTz9wLb4nHc6v",
)


def test_defaults_match_the_fleet():
    p = build_params(**OK)
    assert p.lan_cidr == "10.15.0.0/16"
    assert p.gateway == "10.15.0.1"
    assert p.pool_start == "10.15.1.2"      # 10.15.0.0/24 left for infrastructure
    assert p.pool_end == "10.15.254.254"
    assert p.timezone == "Africa/Banjul"
    assert p.api_username == "netguard"
    assert p.wg_subnet_cidr == "10.13.13.0/24"


def test_gateway_is_outside_the_dhcp_pool():
    # A gateway inside the pool gets handed to a client and the site dies.
    import ipaddress
    p = build_params(**OK)
    gw = ipaddress.ip_address(p.gateway)
    assert not (ipaddress.ip_address(p.pool_start) <= gw <= ipaddress.ip_address(p.pool_end))


# Review Focus #2 — config injection through the site name.
@pytest.mark.parametrize("bad", [
    'counter"; /user add name=evil password=evil;',
    "counter;/system reboot",
    "counter$(reboot)",
    "counter\nmore",
    "Counter With Spaces",
    "",
    "-leading-hyphen",
    "x" * 40,
])
def test_rejects_slugs_that_could_inject_config(bad):
    with pytest.raises(ValueError, match="site_slug"):
        build_params(**{**OK, "site_slug": bad})


# Review Focus #3 — a LAN that swallows the management tunnel.
@pytest.mark.parametrize("bad_lan", ["10.13.0.0/16", "10.13.13.0/24", "10.0.0.0/8"])
def test_rejects_lan_overlapping_the_wireguard_subnet(bad_lan):
    with pytest.raises(ValueError, match="overlap"):
        build_params(**{**OK, "lan_cidr": bad_lan})


# Review Focus #5 — RouterOS rejects an unknown zone mid-script.
def test_rejects_unknown_timezone():
    with pytest.raises(ValueError, match="timezone"):
        build_params(**{**OK, "timezone": "Foo/Bar"})


def test_rejects_missing_wireguard_key():
    with pytest.raises(ValueError, match="wg_private_key"):
        build_params(**{**OK, "wg_private_key": ""})
