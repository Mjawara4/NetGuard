from dataclasses import replace

from app.services.provisioning.params import build_params
from provision_helpers import sections

P = build_params(
    site_slug="serrekunda-counter", wg_private_key="cHJpdmF0ZS1rZXktbm90LXJlYWwtcGFkZGluZy0zYiE=", wg_client_ip="10.13.13.7",
    wg_server_public_key="c2VydmVyLS1rZXktbm90LXJlYWwtcGFkZGluZy0zYiE=", wg_server_endpoint="74.208.167.166",
    wg_server_port=51820, api_password="Xk7mQp2rTz9wLb4nHc6v", recovery_password="Qw8ZeRtY3uIoP5aSdF1g",
    device_id="11111111-1111-1111-1111-111111111111",
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


def test_each_tier_has_its_own_duration_and_one_shared_user():
    # One voucher, one device at a time: every tier is shared-users=1, by request.
    expected = {"3-Hours": "3h", "24-Hours": "24h", "7-Days": "7d", "30-Days": "30d"}
    for name, timeout in expected.items():
        toks = tier(name).split()
        assert f"session-timeout={timeout}" in toks
        assert "shared-users=1" in toks
        for common in ("add-mac-cookie=yes", "mac-cookie-timeout=3d",
                       "idle-timeout=5m", "keepalive-timeout=2m"):
            assert common in toks, (name, common)


def test_default_tier_is_updated_in_place_with_one_shared_user_and_no_session_timeout():
    # RouterOS ships a `default` profile; `add name=default` would be rejected.
    l = line_with(sections.voucher_profiles(P), "/ip hotspot user profile set ")
    toks = l.split()
    assert "[find" in toks and "name=default]" in toks
    assert "shared-users=1" in toks
    assert not any(t.startswith("session-timeout=") for t in toks)
    for common in ("add-mac-cookie=yes", "mac-cookie-timeout=3d",
                   "idle-timeout=5m", "keepalive-timeout=2m"):
        assert common in toks, common


def test_nothing_in_the_hotspot_is_rate_limited():
    for fn in (sections.voucher_profiles, sections.hotspot_server):
        for line in fn(P):
            if line.strip().startswith("#"):
                continue          # the explanatory comment names the rule
            assert "rate-limit" not in line, f"{fn.__name__}: {line}"


def test_walled_garden_allows_each_probe_host_on_its_own_line():
    ls = sections.walled_garden(P)
    for host in ("connectivitycheck.gstatic.com", "captive.apple.com",
                 "www.msftconnecttest.com", "login.netguard.local"):
        l = line_with(ls, f"/ip hotspot walled-garden add dst-host={host} ")
        assert 'comment="NetGuard"' in l


def test_walled_garden_allows_payment_and_buy_hosts_without_todo():
    rendered = text(sections.walled_garden(P))
    for host in ("app.netguard.fun", "api.modempay.com", "checkout.modempay.com",
                 "test.checkout.modempay.com",
                 "cdnjs.cloudflare.com", "fonts.googleapis.com", "fonts.gstatic.com",
                 "na-gateway.mastercard.com", "ye1.i.lencr.org", "ye1.c.lencr.org"):
        assert f"dst-host={host}" in rendered
    assert "TODO PAYMENT PROVIDER" not in rendered
    for host in ("ye1.i.lencr.org", "ye1.c.lencr.org"):
        assert f"dst-host={host} protocol=tcp dst-port=80 action=accept" in rendered


NG = replace(P, portal_mode="netguard")


def test_default_portal_contains_device_buy_url_and_mikrotik_client_variables():
    rendered = text(sections.portal_page(NG))
    assert "https://app.netguard.fun/buy?router=11111111-1111-1111-1111-111111111111" in rendered
    assert "\\$(mac)" in rendered
    assert "\\$(ip)" in rendered
    assert "Buy WiFi" in rendered
    assert "hexMD5" in rendered
    assert 'document.forms[\\"login\\"]' in rendered
    assert 'document.forms[\\"sendin\\"]' in rendered
    assert 'q.get(\\"voucher\\")' in rendered
    assert "document.login" not in rendered
    assert "document.sendin" not in rendered


def test_default_portal_can_list_configured_prices():
    priced = replace(NG, portal_plans=(("3-Hours", "10", "GMD"), ("24-Hours", "25", "GMD")))
    rendered = text(sections.portal_page(priced))
    assert "3-Hours" in rendered and "D10" in rendered
    assert "24-Hours" in rendered and "D25" in rendered
    assert "plan=3-Hours" in rendered
    assert "plan=24-Hours" in rendered


def test_the_script_leaves_the_login_page_alone_unless_netguards_portal_was_chosen():
    # P carries no portal choice: the login page is the owner's, not ours.
    assert P.portal_mode == "custom"
    rendered = text(sections.portal_page(P))
    assert "/file" not in rendered
    assert "login.html" not in rendered.replace("leaving the router's login page", "")


def test_netguard_portal_is_written_into_the_folder_the_hotspot_really_serves():
    rendered = text(sections.portal_page(NG))
    assert ':local ngPortalDir [/ip hotspot profile get [find where name="netguard"] html-directory]' in rendered
    assert ':local ngLogin ($ngPortalDir . "/login.html")' in rendered
    assert "name=$ngLogin" in rendered
    assert '"hotspot/login.html"' not in rendered


def test_netguard_portal_waits_for_routeros_to_finish_creating_the_default_pages():
    # RouterOS writes a new hotspot's default pages a moment AFTER the server
    # is added. Checked too early, login.html "does not exist", and the add
    # then fails with "file already exists" (seen on CHR 7.16.2).
    ls = sections.portal_page(NG)
    wait = next(i for i, l in enumerate(ls) if l.startswith(":while ") and ":delay" in l)
    write = next(i for i, l in enumerate(ls) if "/file add name=$ngLogin" in l)
    assert wait < write


def test_netguard_portal_page_is_marked_as_netguards():
    from app.services.portal_install import NETGUARD_PAGE_MARKER
    from app.services.provisioning.sections import render_portal_html
    assert NETGUARD_PAGE_MARKER in render_portal_html(P.device_id)


def test_the_script_never_sets_the_hotspot_html_folder():
    # It is created once with RouterOS's default and never changed again, so a
    # folder the owner later points the hotspot at survives every re-run.
    assert "html-directory" not in text(sections.hotspot_server(P))


def test_custom_portal_button_has_client_variables_and_no_plan():
    from app.services.provisioning import sections as raw
    rendered = raw.custom_portal_button(P.device_id)
    assert "<!-- NETGUARD-BUY-START -->" in rendered
    assert f"router={P.device_id}" in rendered
    assert "mac=$(mac)" in rendered
    assert "ip=$(ip)" in rendered
    assert "login=$(link-login-only)" in rendered
    assert "plan=" not in rendered
    assert 'id="netguard-chap"' in rendered
    assert 'hexMD5("$(chap-id)"+v+"$(chap-challenge)")' in rendered
    assert "connected=1" in rendered


def test_walled_garden_objects_are_attributable():
    seen = 0
    for l in sections.walled_garden(P):
        if " add " in l and not l.startswith("#"):
            seen += 1
            assert 'comment="NetGuard"' in l, l
    assert seen == 26


def test_hotspot_objects_do_not_carry_comment():
    # RouterOS 7.16 (CHR) rejects `comment=` on /ip hotspot, /ip hotspot profile
    # and /ip hotspot user profile with "expected end of command". Router is the authority.
    #
    # /ip hotspot ip-binding is a DIFFERENT menu and does accept comment -- verified
    # on a CHR, which stored it without complaint. It is exempt rather than excluded,
    # so the binding stays attributable like every other object we create.
    # Exempt menus that DO accept comment, each verified on a CHR which stored it:
    #   /ip hotspot ip-binding  and  /ip hotspot user
    # The rejection applies to /ip hotspot, /ip hotspot profile and
    # /ip hotspot user profile. Note /ip hotspot user and /ip hotspot user
    # profile are different menus with opposite behaviour, so the prefix test
    # below must check the longer one first.
    accepts_comment = ("/ip hotspot ip-binding", "/ip hotspot user add",
                       "/ip hotspot user find", ":if ([:len [/ip hotspot user find")
    for fn in (sections.hotspot_server, sections.voucher_profiles):
        for l in fn(P):
            if l.startswith("#") or any(m in l for m in accepts_comment):
                continue
            assert "comment=" not in l, l


def test_admin_range_bypasses_the_captive_portal():
    """An operator on the admin range must not be captured by the portal.

    Found on a real install: the installer's laptop on ether2 is a hotspot
    client like any phone, so it got the login page -- while WinBox is allowed
    only from the admin range, which is outside the DHCP pool. Without a bypass
    binding the operator has to fight the portal to administer the router.
    """
    ls = sections.hotspot_server(P)
    binding = [l for l in ls if "ip-binding" in l and "add " in l]
    assert binding, "no hotspot ip-binding; the admin range is captured by the portal"
    line = binding[0]
    assert "type=bypassed" in line, line[:120]
    assert P.operator_cidr in line, (
        f"binding must cover the operator range {P.operator_cidr}, the same range "
        f"WinBox is opened to, or the two can drift apart: {line[:120]}"
    )


def test_bypass_binding_cannot_drift_from_the_winbox_allowance():
    """Both must name the same range; a mismatch silently locks the operator out."""
    from app.services.provisioning import sections as S
    binding = [l for l in S.hotspot_server(P) if "ip-binding" in l and "add " in l][0]
    winbox = [l for l in S.firewall(P) if l.startswith("/ip service set winbox")][0]
    assert P.operator_cidr in binding and P.operator_cidr in winbox


def test_bypass_binding_is_idempotent():
    """Asserted on the RAW output -- the shared helper strips the guard it checks."""
    from app.services.provisioning import sections as raw
    line = [l for l in raw.hotspot_server(P) if "ip-binding" in l][0]
    assert line.startswith(":if ([:len [/ip hotspot ip-binding find"), (
        f"re-running would stack duplicate bindings: {line[:100]}"
    )


# --- a known hotspot login for staff and testing --------------------------
#
# Asked for so a router can be tested without minting a voucher. Parameterised
# rather than hardcoded: `admin`/`root` is the first pair anyone guesses, and on
# a customer site it is free internet for whoever tries it. One place to change.


def test_a_hotspot_login_is_created_on_the_default_profile():
    ls = sections.voucher_profiles(P)
    line = [l for l in ls if "/ip hotspot user add" in l]
    assert line, "no hotspot login; the site cannot be tested without a voucher"
    body = line[0]
    assert "name=admin" in body
    assert "password=root" in body
    assert "profile=default" in body


def test_the_hotspot_login_is_idempotent():
    from app.services.provisioning import sections as raw
    line = [l for l in raw.voucher_profiles(P) if "/ip hotspot user add" in l][0]
    assert line.startswith(':if ([:len [/ip hotspot user find where name="admin"]] = 0)'), (
        f"re-running would stack duplicate hotspot logins: {line[:100]}"
    )


def test_the_hotspot_login_is_a_parameter_not_a_constant():
    from app.services.provisioning.params import build_params
    p = build_params(
        site_slug="a-site", wg_client_ip="10.13.13.7",
        wg_private_key="cHJpdmF0ZS1rZXktbm90LXJlYWwtcGFkZGluZy0zYiE=",
        wg_server_public_key="c2VydmVyLS1rZXktbm90LXJlYWwtcGFkZGluZy0zYiE=",
        wg_server_endpoint="74.208.167.166", wg_server_port=51820,
        api_password="Abc23Abc23Abc23Abc23Abc2", recovery_password="Xyz89Xyz89Xyz89Xyz89Xyz8",
        hotspot_login_user="staff", hotspot_login_password="s3cretPass")
    body = text(sections.voucher_profiles(p))
    assert "name=staff" in body and "password=s3cretPass" in body
    assert "name=admin" not in body


def test_the_hotspot_login_cannot_carry_injection():
    """It reaches the router inside a quoted RouterOS argument."""
    from app.services.provisioning.params import build_params
    import pytest as _pytest
    for bad in ('ad"min', "ad;min", "ad min", "admin\n/user add name=x"):
        with _pytest.raises(ValueError):
            build_params(
                site_slug="a-site", wg_client_ip="10.13.13.7",
                wg_private_key="cHJpdmF0ZS1rZXktbm90LXJlYWwtcGFkZGluZy0zYiE=",
                wg_server_public_key="c2VydmVyLS1rZXktbm90LXJlYWwtcGFkZGluZy0zYiE=",
                wg_server_endpoint="74.208.167.166", wg_server_port=51820,
                api_password="Abc23Abc23Abc23Abc23Abc2", recovery_password="Xyz89Xyz89Xyz89Xyz89Xyz8",
                hotspot_login_user=bad)


def test_no_profile_allows_more_than_one_shared_user():
    """One voucher = one device. No shared-users value above 1 anywhere."""
    import re
    for l in sections.voucher_profiles(P):
        for m in re.finditer(r"shared-users=(\d+)", l):
            assert int(m.group(1)) == 1, f"shared-users>{1} in: {l[:90]}"
