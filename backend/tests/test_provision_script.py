import re
from pathlib import Path
from app.services.provisioning.params import build_params
from app.services.provisioning.script import build_provision_script, SECTION_ORDER
from app.services.provisioning import sections

FIXED = dict(
    site_slug="serrekunda-counter",
    wg_private_key="cHJpdmF0ZS1rZXktbm90LXJlYWwtcGFkZGluZy0zYiE=", wg_client_ip="10.13.13.7",
    wg_server_public_key="c2VydmVyLS1rZXktbm90LXJlYWwtcGFkZGluZy0zYiE=",
    wg_server_endpoint="74.208.167.166", wg_server_port=51820,
    api_password="Xk7mQp2rTz9wLb4nHc6v", recovery_password="Qw8ZeRtY3uIoP5aSdF1g",
)
EXPECTED = Path(__file__).parent / "fixtures" / "provision_expected.rsc"


def test_matches_the_golden_file():
    got = build_provision_script(build_params(**FIXED))
    assert got == EXPECTED.read_text(), (
        "Generated script changed. If deliberate, review the diff line by line "
        "and re-record with: python tests/record_provision_golden.py"
    )


def test_preflight_runs_first_and_clock_before_hotspot():
    order = [fn.__name__ for fn in SECTION_ORDER]
    assert order[0] == "preflight"
    assert order.index("identity_and_clock") < order.index("hotspot_server")
    assert order.index("addressing") < order.index("hotspot_server")
    # Firewall second-to-last: it can cut the installer's own session.
    # Asserted exactly -- an `or` here would let either arrangement pass.
    assert order[-2] == "firewall"
    assert order[-1] == "summary"


def test_wireguard_is_created_before_the_firewall_that_references_it():
    # The firewall's tunnel-accept rule uses in-interface=wireguard-netguard;
    # RouterOS rejects a rule naming an interface that does not exist yet.
    order = [fn.__name__ for fn in SECTION_ORDER]
    assert order.index("wireguard") < order.index("firewall")
    script = build_provision_script(build_params(**FIXED))
    created = script.index("/interface wireguard add name=wireguard-netguard")
    referenced = script.index("in-interface=wireguard-netguard")
    assert created < referenced


def test_every_section_is_present_exactly_once():
    names = [fn.__name__ for fn in SECTION_ORDER]
    assert len(names) == len(set(names)) == 13
    for name in names:
        assert getattr(sections, name) in SECTION_ORDER


def test_no_secret_appears_more_than_once():
    p = build_params(**FIXED)
    script = build_provision_script(p)
    assert script.count(p.wg_private_key) == 1
    assert script.count(p.api_password) == 1


def test_summary_names_the_api_user_but_never_the_password():
    p = build_params(**FIXED)
    text = "\n".join(sections.summary(p))
    assert p.api_password not in text
    assert p.wg_private_key not in text
    assert p.api_username in text
    assert "dashboard" in text.lower()


def test_keepalive_stays_below_the_conntrack_udp_timeout():
    # Measured conntrack UDP timeout is 30s. The keepalive margin is what keeps
    # every tunnel alive through the firewall's WAN drop; see sections.wireguard.
    conntrack_udp_timeout = 30
    script = build_provision_script(build_params(**FIXED))
    # Only the real peer command: comments discuss the value too.
    found = re.findall(r"^(?!#).*wireguard peers add .*persistent-keepalive=(\d+)s",
                       script, flags=re.M)
    assert len(found) == 1
    assert int(found[0]) < conntrack_udp_timeout
    # Recorded where a tuner will look: the rule that depends on the margin.
    assert "udp-timeout is 30s" in script


def test_gateway_is_never_inside_the_pool():
    p = build_params(**FIXED)
    script = build_provision_script(p)
    assert f"ranges={p.pool_start}-{p.pool_end}" in script
    assert f"address={p.gateway}/16" in script


def test_api_is_never_world_open_anywhere_in_the_script():
    script = build_provision_script(build_params(**FIXED))
    assert "0.0.0.0/0" not in script


# RouterOS rejects `comment=` on these menus (confirmed on 7.16.2 in Task 5:
# `expected end of command`, error column on the comment). Listed explicitly
# rather than skipped by a substring, so adding another exception is a
# deliberate edit. `/interface wifi capsman set` is a `set`, not an `add`.
MENUS_WITHOUT_COMMENT = (
    "/ip hotspot profile add",
    "/ip hotspot user profile add",
    "/ip hotspot add",
)


def test_every_add_is_attributable_to_netguard():
    script = build_provision_script(build_params(**FIXED))
    seen = 0
    for line in script.splitlines():
        # Prose in comments may contain the word "add".
        if line.lstrip().startswith("#") or " add " not in line:
            continue
        if any(m in line for m in MENUS_WITHOUT_COMMENT):
            continue
        seen += 1
        # Prefix match: firewall rules say "NetGuard fw: ...", the API user
        # and group say "NetGuard API"; all remain identifiable as ours.
        assert 'comment="NetGuard' in line, line
    assert seen >= 10, f"expected many created objects, matched {seen}"


def test_the_comment_exempt_objects_are_identifiable_by_name():
    # They cannot carry a comment, so the only handle on them is their name.
    # Without this, the exemption above would let them become anonymous.
    script = build_provision_script(build_params(**FIXED))
    exempt = 0
    for line in script.splitlines():
        if line.lstrip().startswith("#"):
            continue
        if any(m in line for m in MENUS_WITHOUT_COMMENT):
            exempt += 1
            assert "name=" in line, line
    assert exempt == 5  # hotspot profile, hotspot, three tiers


def test_summary_tells_the_installer_what_they_need():
    # Read the summary SECTION, not a fixed-size tail of the script: a tail window
    # silently stops covering the earlier summary lines as soon as the section grows.
    script = build_provision_script(build_params(**FIXED))
    from app.services.provisioning import sections
    summary = "\n".join(sections.summary(build_params(**FIXED)))
    assert summary in script
    for token in ("license", "10.15.0.1", "netguard", "wireguard",
                  # The client bridge's firewall reachability. A stock router's
                  # `drop all not coming from LAN` discards every client packet when this
                  # is wrong, and the rest of the summary still prints "complete".
                  "lan interface list"):
        assert token in summary.lower(), token


def _depth_walk(script):
    """Yield (line_no, depth_before, depth_after) counting braces outside comments and quotes."""
    depth = 0
    for n, line in enumerate(script.splitlines(), 1):
        if line.lstrip().startswith("#"):
            yield n, depth, depth
            continue
        before, in_q, esc = depth, False, False
        for ch in line:
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == '"':
                in_q = not in_q
            elif not in_q and ch == "{":
                depth += 1
            elif not in_q and ch == "}":
                depth -= 1
        yield n, before, depth


def test_whole_script_is_one_brace_enclosed_block():
    # `:error` aborts everything only inside a single command. Pasted line by line it prints and the
    # script carries on (confirmed on a CHR: it ran through to "provisioning complete" on a router
    # that already had a hotspot). One block makes a paste a single command.
    script = build_provision_script(build_params(**FIXED))
    lines = [l for l in script.splitlines() if l.strip()]
    assert lines[0] == "{" and lines[-1] == "}"
    walked = list(_depth_walk(script))
    last_nonblank = max(n for n, _, _ in walked if script.splitlines()[n - 1].strip())
    for n, before, after in walked:
        if n == last_nonblank:
            assert (before, after) == (1, 0)
        elif n > 1:
            # Never returns to top level before the end: an early `}` would end the block
            # and every later line would run as its own command.
            assert after >= 1, f"block closed early at line {n}"
    assert walked[-1][2] == 0


def test_no_statement_sits_outside_the_block():
    script = build_provision_script(build_params(**FIXED))
    lines = script.splitlines()
    first = next(i for i, l in enumerate(lines) if l.strip())
    last = max(i for i, l in enumerate(lines) if l.strip())
    assert lines[first] == "{" and lines[last] == "}"
    assert not any(l.strip() for l in lines[:first])
    assert not any(l.strip() for l in lines[last + 1:])


def test_preflight_is_inside_the_block_so_its_error_aborts_everything():
    script = build_provision_script(build_params(**FIXED))
    lines = script.splitlines()
    for n, before, _ in _depth_walk(script):
        if ":error" in lines[n - 1] and not lines[n - 1].lstrip().startswith("#"):
            assert before >= 1, lines[n - 1]


def test_summary_reports_what_the_installer_cannot_see_otherwise():
    p = build_params(**FIXED)
    text = "\n".join(sections.summary(p))
    assert "Tunnel status" in text and "last-handshake" in text
    assert "WAN port" in text and p.wan_interface in text
    assert "LAN ports" in text and "bridge port find" in text
    # The tunnel-only warning, including winbox's extra range.
    assert "reachable only through the tunnel" in text and p.operator_cidr in text
    # A dropped session mid-run is expected, and where to reconnect.
    assert "session was cut" in text and "10.15.x" in text


def test_summary_does_not_overstate_the_firewall():
    text = "\n".join(sections.summary(build_params(**FIXED)))
    # It drops NEW connections to the router and to the LAN, but not the WireGuard port or ping.
    assert "router and LAN" in text
    assert "except the WireGuard port and ping" in text
