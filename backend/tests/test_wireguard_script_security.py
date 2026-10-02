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


def test_monitoring_accept_is_scoped_to_the_tunnel_interface():
    """An unscoped src-address accept trusts anything that can spoof the subnet.

    Observed on a real hEX: the rule landed at input position 0 as a blanket
    accept for src 10.13.13.0/24 with no in-interface, sitting above the stock
    `accept established` and both `drop invalid` rules. Anything that can put
    that source address into the input chain was accepted.
    """
    script = _script()
    accept = [l for l in script.splitlines() if "Allow NetGuard Monitoring" in l and "add " in l]
    assert accept, "no monitoring accept rule found"
    for line in accept:
        assert "in-interface=wireguard-netguard" in line, (
            f"unscoped accept: {line.strip()[:120]}"
        )


def test_monitoring_accept_does_not_use_absolute_placement():
    """Absolute placement fails with `no such item` on an empty filter table.

    Checked against executable lines only -- the script explains the hazard in a
    comment, and that prose quotes the very string being banned.
    """
    config = [l for l in _script().splitlines() if not l.strip().startswith("#")]
    for line in config:
        assert "place-before=0" not in line, line.strip()[:120]


def test_monitoring_accept_handles_an_empty_filter_table():
    """A router with no filter rules must still get the accept, not an error."""
    script = _script()
    assert ":len" in script, "no guard on the placement lookup"


def test_monitoring_accept_is_not_added_twice():
    """The UI button can be pressed repeatedly; the rule must not accumulate."""
    script = _script()
    assert 'find where comment="Allow NetGuard Monitoring"' in script, (
        "re-running the script would append a duplicate accept rule"
    )


def test_placement_targets_blocking_rules_only():
    """Placement must key off terminal actions, not a fixed index."""
    script = _script()
    for action in ("action=drop", "action=reject", "action=tarpit"):
        assert action in script, f"placement does not consider {action}"
