from app.services.wireguard import WireGuardService, WG_SUBNET

KEY = "aGVsbG8gd29ybGQgdGhpcyBpcyBub3QgYSByZWFsIGtleQ=="


def _script():
    return WireGuardService.generate_mikrotik_script(
        private_key=KEY,
        client_ip="10.13.13.9",
        server_public_key=KEY,
        server_endpoint="203.0.113.10",
        server_port=51820,
    )


def test_api_service_is_not_exposed_to_the_internet():
    # The API accepts a stored credential. Restricting it only by firewall rule
    # order means one reordered rule exposes it; pin the service itself.
    script = _script()
    assert "set api disabled=no port=8728 address=0.0.0.0/0" not in script
    assert f"address={WG_SUBNET}0/24" in script


def test_peer_cannot_claim_any_source_address():
    # The router only ever reaches the NetGuard server over this tunnel.
    script = _script()
    assert "allowed-address=0.0.0.0/0" not in script
    assert f"allowed-address={WG_SUBNET}0/24" in script
