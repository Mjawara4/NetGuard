from app.services.provisioning.params import build_params
from provision_helpers import sections

P = build_params(
    site_slug="serrekunda-counter",
    wg_private_key="cHJpdmF0ZS1rZXktbm90LXJlYWwtcGFkZGluZy0zYiE=",
    wg_client_ip="10.13.13.7",
    wg_server_public_key="c2VydmVyLS1rZXktbm90LXJlYWwtcGFkZGluZy0zYiE=",
    wg_server_endpoint="74.208.167.166", wg_server_port=51820,
    api_password="Xk7mQp2rTz9wLb4nHc6v", admin_password="Qw8ZeRtY3uIoP5aSdF1g",
)


def text(lines):
    return "\n".join(lines)


def test_preflight_refuses_routeros_6():
    lines = sections.preflight(P)
    guard = [l for l in lines if "get version" in l and ":error" in l]
    assert guard, "no single line both reads the version and errors on it"
    assert any("7" in l for l in guard), "version guard does not name the floor"


def test_preflight_greenfield_guards_actually_error():
    lines = sections.preflight(P)
    for probe in ("/ip hotspot find", "wireguard-netguard"):
        guard = [l for l in lines if probe in l and ":error" in l]
        assert guard, f"{probe} is checked but does not abort"


def test_preflight_is_the_greenfield_guard():
    t = text(sections.preflight(P))
    # Must abort if a hotspot or our tunnel already exists.
    assert "/ip hotspot find" in t
    assert "wireguard-netguard" in t


def test_preflight_reports_license_and_device_mode():
    t = text(sections.preflight(P))
    assert "/system license" in t
    assert "device-mode" in t
    # Both are wrapped so a command missing on some builds cannot abort the run.
    assert "on-error" in t


def test_preflight_reads_license_level_not_only_nlevel():
    # CHR-verified: RouterOS 7.16.2 rejects `nlevel` and exposes `level`.
    t = text(sections.preflight(P))
    assert "/system license get level" in t


def test_preflight_uses_no_local_variables():
    # CHR-verified: at the top level of an imported file, `:local x [cmd]` is
    # empty on the next line, so a version check built on it aborted every
    # router, including valid ones. Guards must be single-statement.
    for line in sections.preflight(P):
        if not line.startswith("#"):
            assert ":local" not in line, line


def test_clock_comes_before_anything_time_dependent():
    t = text(sections.identity_and_clock(P))
    assert "/system ntp client" in t
    assert "time-zone-name=Africa/Banjul" in t
    assert "time.cloudflare.com" in t and "time.google.com" in t
    assert "name=serrekunda-counter" in t


def test_clock_enables_the_ntp_client():
    t = text(sections.identity_and_clock(P))
    assert "/system ntp client set" in t
    assert "enabled=yes" in t


def test_bridge_guards_every_port_on_the_interface_existing():
    lines = sections.bridge(P)
    ports = [l for l in lines if "/interface bridge port add" in l]
    for n in range(2, 9):
        matching = [l for l in ports if f"interface=ether{n} " in l]
        assert len(matching) == 1, n
        assert f'[/interface find where name="ether{n}"]' in matching[0]
        assert matching[0].startswith(":if ")
    assert not any("interface=ether1 " in l for l in ports)
    assert any("interface=wifi1 " in l for l in ports)
    wlan = [l for l in ports if "interface=wlan1 " in l]
    assert len(wlan) == 1
    assert '[/interface find where name="wlan1"]' in wlan[0] and wlan[0].startswith(":if ")


def test_addressing_matches_the_agreed_plan():
    t = text(sections.addressing(P))
    assert "address=10.15.0.1/16" in t
    assert "ranges=10.15.1.2-10.15.254.254" in t
    assert "lease-time=4h" in t
    assert "authoritative=yes" in t


def test_dns_is_open_to_clients_but_nat_exists():
    t = text(sections.dns_and_nat(P))
    assert "allow-remote-requests=yes" in t
    assert "servers=1.1.1.1,8.8.8.8" in t
    assert "cache-size=4096KiB" in t
    assert "action=masquerade" in t
    assert "out-interface=ether1" in t


def test_every_created_object_is_attributable():
    # Sections emit the single-line form `/ip pool add name=...`, so matching
    # lines that START with "add" would match nothing and pass vacuously.
    # Match " add " and require at least one hit, so an empty match fails.
    seen = 0
    for fn in (sections.bridge, sections.addressing, sections.dns_and_nat):
        for line in fn(P):
            if " add " in line:
                seen += 1
                assert 'comment="NetGuard"' in line, line
    assert seen >= 3, f"expected several created objects, matched {seen}"


def test_summary_falls_back_to_nlevel_like_preflight_does():
    """A real hEX on RouterOS 7.24.5 exposes `nlevel`, not `level`.

    Preflight already tried both. The summary tried only `level`, so the one
    line that tells an installer their concurrent-user ceiling printed
    "unavailable" on hardware where `/system license print` showed nlevel: 4.
    """
    from app.services.provisioning import sections
    line = [l for l in sections.summary(P) if "License level" in l]
    assert line, "no license line in the summary"
    body = line[0]
    assert "get level" in body, "summary no longer reads level"
    assert "get nlevel" in body, (
        "summary has no nlevel fallback; an hEX reports the ceiling as "
        "unavailable even though RouterOS knows it"
    )


def test_summary_admin_line_matches_what_the_script_actually_did():
    """A reuse script must not claim it set a password it deliberately left alone.

    Caught on a CHR: the reuse variant printed "admin password: set to a random
    value (see the NetGuard dashboard)" while omitting the line that sets it --
    sending the installer to look for a password the dialog never showed.
    """
    from app.services.provisioning import sections
    from app.services.provisioning.params import build_params

    common = dict(site_slug="a-site", wg_client_ip="10.13.13.7",
                  wg_private_key="cHJpdmF0ZS1rZXktbm90LXJlYWwtcGFkZGluZy0zYiE=",
                  wg_server_public_key="c2VydmVyLS1rZXktbm90LXJlYWwtcGFkZGluZy0zYiE=",
                  wg_server_endpoint="74.208.167.166", wg_server_port=51820,
                  api_password="Abc123Abc123Abc123Abc123")

    rotated = sections.summary(build_params(**common, admin_password="Zz9Zz9Zz9Zz9Zz9Zz9Zz9Zz9"))
    reused = sections.summary(build_params(**common))

    rot_line = [l for l in rotated if "admin password" in l.lower()][0]
    reu_line = [l for l in reused if "admin password" in l.lower()][0]

    assert "random" in rot_line, "a rotating script should say it set a new one"
    assert "random" not in reu_line, (
        f"reuse script claims it set a random admin password but does not set "
        f"one: {reu_line[:110]}"
    )
    assert "unchanged" in reu_line.lower(), reu_line[:110]
