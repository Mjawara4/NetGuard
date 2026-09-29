from app.services.provisioning.params import build_params
from app.services.provisioning import sections

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


def tier(name):
    return line_with(sections.voucher_profiles(P), f"/ip hotspot user profile add name={name} ")


def test_hotspot_profile_line_carries_login_and_dns_and_no_certificate():
    l = line_with(sections.hotspot_server(P), "/ip hotspot profile add ")
    assert "name=netguard" in l.split()
    assert "hotspot-address=10.15.0.1" in l.split()
    assert "dns-name=login.netguard.local" in l.split()
    assert "login-by=http-chap,mac-cookie" in l.split()
    assert "http-cookie-lifetime=3d" in l.split()
    assert "ssl-certificate" not in text(sections.hotspot_server(P))
    assert "https" not in text(sections.hotspot_server(P))


def test_hotspot_server_line_is_on_the_bridge_and_pool_with_clean_timeouts():
    l = line_with(sections.hotspot_server(P), "/ip hotspot add ").split()
    for tok in ("interface=bridge-hotspot", "address-pool=hotspot-pool", "profile=netguard",
                "login-timeout=5m", "idle-timeout=5m", "keepalive-timeout=2m"):
        assert tok in l, tok


def test_each_tier_has_its_own_duration_and_sharing():
    expected = {"1-Hour": ("1h", "1"), "24-Hours": ("24h", "2"), "7-Days": ("7d", "4")}
    for name, (timeout, shared) in expected.items():
        toks = tier(name).split()
        assert f"session-timeout={timeout}" in toks
        assert f"shared-users={shared}" in toks
        for common in ("add-mac-cookie=yes", "mac-cookie-timeout=3d",
                       "idle-timeout=5m", "keepalive-timeout=2m"):
            assert common in toks, (name, common)


def test_default_tier_is_updated_in_place_with_sharing_4_and_no_session_timeout():
    # RouterOS ships a `default` profile; `add name=default` would be rejected.
    l = line_with(sections.voucher_profiles(P), "/ip hotspot user profile set ")
    toks = l.split()
    assert "[find" in toks and "name=default]" in toks
    assert "shared-users=4" in toks
    assert not any(t.startswith("session-timeout=") for t in toks)
    assert "add-mac-cookie=yes" in toks


def test_no_tier_is_rate_limited():
    # Explicitly specified: bandwidth is unshaped, tiers differ by duration.
    for l in sections.voucher_profiles(P):
        if not l.startswith("#"):
            assert "rate-limit" not in l, l


def test_walled_garden_allows_each_probe_host_on_its_own_line():
    ls = sections.walled_garden(P)
    for host in ("connectivitycheck.gstatic.com", "captive.apple.com",
                 "www.msftconnecttest.com", "login.netguard.local"):
        l = line_with(ls, f"/ip hotspot walled-garden add dst-host={host} ")
        assert 'comment="NetGuard"' in l


def test_walled_garden_ntp_ip_entry_exists():
    l = line_with(sections.walled_garden(P), "/ip hotspot walled-garden ip add ")
    assert "action=accept" in l.split()


def test_walled_garden_ends_with_the_visible_payment_todo():
    assert sections.walled_garden(P)[-1] == (
        "# TODO PAYMENT PROVIDER: add the provider's hosts here before going live."
    )


def test_walled_garden_objects_are_attributable():
    seen = 0
    for l in sections.walled_garden(P):
        if " add " in l and not l.startswith("#"):
            seen += 1
            assert 'comment="NetGuard"' in l, l
    assert seen == 5


def test_hotspot_objects_do_not_carry_comment():
    # RouterOS 7.16 (CHR) rejects `comment=` on /ip hotspot, /ip hotspot profile
    # and /ip hotspot user profile with "expected end of command". Router is the authority.
    for fn in (sections.hotspot_server, sections.voucher_profiles):
        for l in fn(P):
            if not l.startswith("#"):
                assert "comment=" not in l, l
