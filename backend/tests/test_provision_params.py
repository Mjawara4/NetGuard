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
    "counter\n",
    "counter\r",
    "Counter With Spaces",
    "",
    "-leading-hyphen",
    "x" * 40,
])
def test_rejects_slugs_that_could_inject_config(bad):
    with pytest.raises(ValueError, match="site_slug"):
        build_params(**{**OK, "site_slug": bad})


def test_accepts_valid_slugs():
    """Positive test: valid slugs are accepted"""
    # Two-character slug
    p = build_params(**{**OK, "site_slug": "ab"})
    assert p.site_slug == "ab"
    
    # 32-character slug
    p = build_params(**{**OK, "site_slug": "a" + "b" * 30 + "c"})
    assert p.site_slug == "a" + "b" * 30 + "c"
    
    # Slug with hyphens
    p = build_params(**{**OK, "site_slug": "my-site-123"})
    assert p.site_slug == "my-site-123"


# Review Focus #3 — a LAN that swallows the management tunnel.
@pytest.mark.parametrize("bad_lan", ["10.13.0.0/16", "10.13.13.0/24", "10.0.0.0/8"])
def test_rejects_lan_overlapping_the_wireguard_subnet(bad_lan):
    with pytest.raises(ValueError, match="overlap"):
        build_params(**{**OK, "lan_cidr": bad_lan})


def test_rejects_lan_too_small():
    """LAN must be /22 or larger (at least 1024 addresses)"""
    with pytest.raises(ValueError, match="at least 1024"):
        build_params(**{**OK, "lan_cidr": "10.16.0.0/24"})


def test_accepts_lan_at_minimum_size():
    """/22 is the minimum acceptable size (1024 addresses)"""
    p = build_params(**{**OK, "lan_cidr": "10.16.0.0/22"})
    assert p.lan_cidr == "10.16.0.0/22"


def test_rejects_pool_in_wireguard_subnet():
    """Pool boundaries that would overlap WireGuard subnet must be rejected.
    10.13.12.0/22 has 1024 addresses but pool_start would be 10.13.13.2,
    which is inside the WireGuard subnet 10.13.13.0/24."""
    with pytest.raises(ValueError, match="overlap"):
        build_params(**{**OK, "lan_cidr": "10.13.12.0/22"})


# Review Focus #5 — RouterOS rejects an unknown zone mid-script.
def test_rejects_unknown_timezone():
    with pytest.raises(ValueError, match="timezone"):
        build_params(**{**OK, "timezone": "Foo/Bar"})


def test_rejects_missing_wg_private_key():
    with pytest.raises(ValueError, match="wg_private_key"):
        build_params(**{**OK, "wg_private_key": ""})


def test_rejects_missing_wg_server_public_key():
    with pytest.raises(ValueError, match="wg_server_public_key"):
        build_params(**{**OK, "wg_server_public_key": ""})


def test_rejects_missing_wg_server_endpoint():
    with pytest.raises(ValueError, match="wg_server_endpoint"):
        build_params(**{**OK, "wg_server_endpoint": ""})


def test_rejects_missing_api_password():
    with pytest.raises(ValueError, match="api_password"):
        build_params(**{**OK, "api_password": ""})


# WireGuard client IP validation
def test_rejects_invalid_wg_client_ip():
    with pytest.raises(ValueError, match="wg_client_ip"):
        build_params(**{**OK, "wg_client_ip": "not-an-ip"})


def test_rejects_wg_client_ip_outside_subnet():
    with pytest.raises(ValueError, match="wg_client_ip"):
        build_params(**{**OK, "wg_client_ip": "10.13.12.1"})


def test_accepts_valid_wg_client_ip():
    p = build_params(**{**OK, "wg_client_ip": "10.13.13.254"})
    assert p.wg_client_ip == "10.13.13.254"


# WireGuard server endpoint validation
def test_rejects_invalid_wg_server_endpoint():
    with pytest.raises(ValueError, match="wg_server_endpoint"):
        build_params(**{**OK, "wg_server_endpoint": 'evil"; /user add'})


def test_accepts_valid_wg_server_endpoint_hostname():
    p = build_params(**{**OK, "wg_server_endpoint": "vpn.example.com"})
    assert p.wg_server_endpoint == "vpn.example.com"


# WireGuard key validation (base64, at least 40 chars)
def test_rejects_wg_private_key_not_base64():
    with pytest.raises(ValueError, match="wg_private_key"):
        build_params(**{**OK, "wg_private_key": 'a"b\n'})


def test_rejects_wg_private_key_too_short():
    with pytest.raises(ValueError, match="wg_private_key"):
        build_params(**{**OK, "wg_private_key": "abcd1234"})


def test_rejects_wg_server_public_key_not_base64():
    with pytest.raises(ValueError, match="wg_server_public_key"):
        build_params(**{**OK, "wg_server_public_key": 'evil";x'})


def test_rejects_wg_server_public_key_too_short():
    with pytest.raises(ValueError, match="wg_server_public_key"):
        build_params(**{**OK, "wg_server_public_key": "abcd1234"})


# API password validation (alphanumeric only)
def test_rejects_api_password_with_special_chars():
    with pytest.raises(ValueError, match="api_password"):
        build_params(**{**OK, "api_password": 'a"$b'})


def test_accepts_valid_api_password():
    p = build_params(**{**OK, "api_password": "SecurePassword123"})
    assert p.api_password == "SecurePassword123"


# WireGuard server port validation
def test_rejects_wg_server_port_out_of_range():
    with pytest.raises(ValueError, match="wg_server_port"):
        build_params(**{**OK, "wg_server_port": 99999})


def test_rejects_wg_server_port_negative():
    with pytest.raises(ValueError, match="wg_server_port"):
        build_params(**{**OK, "wg_server_port": -1})


def test_accepts_valid_wg_server_port():
    p = build_params(**{**OK, "wg_server_port": 12345})
    assert p.wg_server_port == 12345


# IPv6 rejection
def test_rejects_ipv6_lan():
    with pytest.raises(ValueError, match="IPv4"):
        build_params(**{**OK, "lan_cidr": "fd00::/64"})


def test_rejects_ipv6_wg_client_ip():
    with pytest.raises(ValueError, match="IPv4"):
        build_params(**{**OK, "wg_client_ip": "fd00::1"})
