# MikroTik One-Shot Provisioning Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A NetGuard endpoint that emits a single pasteable RouterOS script turning a factory-fresh MikroTik into a working hotspot site — addressing, DHCP, NAT, hotspot with voucher tiers, captive portal, CAPsMAN for 100+ APs, the WireGuard tunnel home, firewall hardening and a least-privilege API user.

**Architecture:** Pure functions, one per config section, each taking a frozen `ProvisionParams` and returning `list[str]` of RouterOS lines. An assembler concatenates them in a fixed order. Nothing touches a router: the output is text, which makes the whole thing unit-testable, and a CHR virtual router validates that RouterOS actually accepts it.

**Tech Stack:** Python 3.11, FastAPI, pytest (`asyncio_mode=auto`), RouterOS 7.x CLI, MikroTik CHR under QEMU/KVM.

**Spec:** `docs/superpowers/specs/2026-09-29-mikrotik-provisioning-design.md`

## Global Constraints

- **Greenfield only.** The script must refuse to run against an already-configured router rather than half-apply. No idempotency, no rollback.
- LAN is `10.15.0.0/16`, gateway `10.15.0.1`, DHCP pool `10.15.1.2`–`10.15.254.254`, leaving `10.15.0.0/24` free for infrastructure.
- WireGuard subnet is `10.13.13.0/24`, server `10.13.13.1`, interface name `wireguard-netguard`, `listen-port=13231`, `mtu=1420`, `persistent-keepalive=25s`. These match `backend/app/services/wireguard.py` and must not drift — NetGuard's monitoring depends on them.
- DHCP `lease-time=4h`, `authoritative=yes`.
- **No `rate-limit` on any hotspot profile.** Tiers differ by duration and `shared-users` only.
- Voucher tiers: `default` (no timeout, `shared-users=4`), `1-Hour` (`1h`/1), `24-Hours` (`24h`/2), `7-Days` (`7d`/4). All with `add-mac-cookie=yes`, `mac-cookie-timeout=3d`, `idle-timeout=5m`, `keepalive-timeout=2m`.
- Hotspot profile: `login-by=http-chap,mac-cookie`, `http-cookie-lifetime=3d`, `dns-name=login.netguard.local`. **No TLS certificate** — there is no domain, and captive-portal detection works over plain HTTP plus DHCP option 114.
- `/ip service set api address=10.13.13.0/24` — never `0.0.0.0/0`.
- Every object the script creates carries `comment="NetGuard"` — **except on the three menus RouterOS refuses it**. Confirmed on a real 7.16.2 router in Task 5: `/ip hotspot profile add`, `/ip hotspot add` and `/ip hotspot user profile add` all reject `comment=` with `expected end of command`. Those objects are identified by NAME instead (`netguard`, `netguard-hotspot`, and the four tier names). Walled-garden entries DO accept `comment=`.
- NTP and timezone are configured **before** the hotspot sections. Voucher durations are enforced by the router's clock.
- CAPsMAN uses the `/interface wifi` (wifi-qcom) stack, which supports local forwarding only. Do not port to legacy `/caps-man`.
- NetGuard authenticates to RouterOS with `device.ssh_username` / `device.ssh_password` (see `backend/app/routers/hotspot.py:270`). Misleadingly named, but that is where the generated API credential must be written. Do not rename those columns in this work.
- Backend test baseline: **82 passing**. None may regress.
- Run backend tests with:
  `docker run --rm -v "$PWD/backend:/app" -w /app netguard-backend:latest python -m pytest tests/ -q`
  Do **not** use `docker compose run` — the compose file hardcodes subnet `172.25.0.0/16`, which collides with the live production network.
- Never write under `/opt/netguard` (bind-mounted into live containers). Never `git push`. Never `git add -A`.
- **Reference board is `L009UiGS-2HaxD`** (confirmed as the "Hagie kumbija" site's model): 8 ethernet ports plus SFP. `ether1` is WAN, `ether2`-`ether8` bridge, SFP left out.
- **`site_slug` is untrusted.** Customers now onboard themselves, so it arrives from a web form and is interpolated into a script running as router admin. Reject, never escape.
- **The returned script is a credential**, carrying that router's WireGuard private key and API password. Do not log it, do not cache it, return it once.

## Review Focus

Five failure modes the spec implies but which no task's happy path exercises. Each has a test assigned to the task that owns the code.

1. **A device with no WireGuard provisioned.** `wg_private_key` is `None`, and the script would embed the literal `None` as a key — a script that looks complete and silently cannot connect. The endpoint must refuse. *(Task 9)*
2. **`site_slug` containing RouterOS metacharacters.** A slug with `"`, `;`, `$` or a newline is config injection into a script that runs as admin. Must be rejected, not escaped. *(Task 3)*
3. **A LAN CIDR overlapping the WireGuard subnet.** Pass `10.13.0.0/16` and the router routes its own management tunnel into the customer bridge, cutting NetGuard off permanently. Must be refused. *(Task 3)*
4. **A generated API password containing quote or `$` characters.** RouterOS would mis-parse the `/user add` line, leaving either no user or a user with a different password than NetGuard stored. The alphabet must exclude them. *(Task 6)*
5. **An unknown timezone string.** RouterOS rejects `/system clock set time-zone-name=Foo/Bar` mid-script, after earlier sections have already applied. Must be validated against a known list up front. *(Task 3)*

## A deliberate deviation from the plan format

The writing-plans format requires a complete code block for every
implementation step. Tasks 4-7 instead give **exact assertions plus prose
direction** for the RouterOS content, and only full code for the Python.

This is deliberate. I cannot verify RouterOS syntax from here, and writing ~400
lines of invented CLI into a plan would dress up guesses as specification --
an implementer would then treat a wrong `ssl-certificate` or `local-forwarding`
flag as authoritative. Task 2 builds a real RouterOS parser to be the authority
instead, and every section task ends by running against it with the standing
instruction: *if RouterOS rejects a line, fix the code and update the test to
match reality.*

The Python signatures, the tests, and the constraint values ARE given exactly,
because those I can verify.

---

### Task 1: Close the API-exposure hole in the existing WireGuard script

Independent of everything else and worth shipping alone: the script NetGuard already hands out today opens the RouterOS API to the internet.

**Files:**
- Modify: `backend/app/services/wireguard.py:143-171`
- Test: `backend/tests/test_wireguard_script_security.py`

**Interfaces:**
- Consumes: nothing.
- Produces: nothing new. Behaviour change only.

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_wireguard_script_security.py`:

```python
from app.services.wireguard import WireGuardService, WG_SUBNET

KEY = "aGVsbG8gd29ybGQgdGhpcyBpcyBub3QgYSByZWFsIGtleQ="


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
```

- [ ] **Step 2: Run it to confirm it fails**

```bash
docker run --rm -v "$PWD/backend:/app" -w /app netguard-backend:latest \
  python -m pytest tests/test_wireguard_script_security.py -q
```
Expected: 2 failed — the current script contains both `0.0.0.0/0` strings.

- [ ] **Step 3: Fix the script**

In `backend/app/services/wireguard.py`, inside the f-string, change the peer line's `allowed-address=0.0.0.0/0` to `allowed-address={WG_SUBNET}0/24`, and change:

```
set api disabled=no port=8728 address=0.0.0.0/0
```
to
```
set api disabled=no port=8728 address={WG_SUBNET}0/24
```

Add a comment above the service line explaining why, so it is not "simplified" back:

```python
# The API accepts a stored credential, so it is pinned at the service as well
# as in the firewall. Relying on one filter rule's position means a single
# reorder exposes it to the internet.
```

- [ ] **Step 4: Run the tests** — expected: 2 passed, and the full suite still 82+.

```bash
docker run --rm -v "$PWD/backend:/app" -w /app netguard-backend:latest python -m pytest tests/ -q
```

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/wireguard.py backend/tests/test_wireguard_script_security.py
git commit -m "fix(backend): pin RouterOS API service to the WireGuard subnet"
```

---

### Task 2: CHR smoke-test harness

Deliberately second, before any RouterOS is generated. Every snippet in Tasks 4–8 is written from MikroTik's documentation and **is not verified**; a golden-file test only proves the generator matches an expectation written by the same person. A real RouterOS parser is the only thing that settles whether a command is valid on 7.25. Build the judge before the thing being judged.

**Files:**
- Create: `scripts/chr-smoke-test.sh`
- Create: `docs/chr-smoke-test.md`

**Interfaces:**
- Produces: `scripts/chr-smoke-test.sh <script-file>` — boots a CHR VM, applies the script, exits non-zero if RouterOS reported any error, and prints the router's own output.

- [ ] **Step 1: Confirm the host can run it**

```bash
ls /dev/kvm && grep -c -E '^flags.*(vmx|svm)' /proc/cpuinfo
```
Expected: `/dev/kvm` exists, count > 0. (Verified on this VPS 2026-09-29: present, 4 CPUs.) If absent, stop and report — do not silently skip this task; the plan depends on it.

- [ ] **Step 2: Install QEMU**

```bash
apt-get update && apt-get install -y qemu-system-x86 qemu-utils
```

- [ ] **Step 3: Write the harness**

Create `scripts/chr-smoke-test.sh`. It must:
1. Download the CHR image for a 7.x release once, into `/tmp/chr/`, and cache it:
   `https://download.mikrotik.com/routeros/7.16.2/chr-7.16.2.img.zip`
   (7.16.2 is a stable release; the fleet runs 7.25beta5, so a passing smoke test proves syntax valid on 7.16+, not that a 7.25beta-only feature works. State this limit in the doc.)
2. `unzip`, then `qemu-img resize` the raw image to 128M.
3. Boot with `-enable-kvm -m 256 -nographic` and a user-mode network with a hostfwd for SSH.
4. Wait for boot, log in as `admin` with no password, and apply the script under test by piping it over SSH.
5. Capture stdout and grep for RouterOS error markers (`syntax error`, `expected end of command`, `no such item`, `failure:`, `input does not match`). Exit 1 if any appear.
6. Always destroy the VM on exit (`trap`), so a failed run leaves nothing behind.

- [ ] **Step 4: Prove the harness can fail**

Feed it a deliberately invalid script and confirm it exits non-zero:

```bash
printf '/ip address add address=10.0.0.1/24 interface=nonexistent-iface\n' > /tmp/bad.rsc
./scripts/chr-smoke-test.sh /tmp/bad.rsc; echo "exit=$?"
```
Expected: `exit=1`, with the router's own error quoted. **A harness that cannot fail is worse than no harness** — this project has already shipped three gates that could not fail. Do not proceed until this step goes red.

- [ ] **Step 5: Prove it can pass**

```bash
printf '/system identity set name=smoke-ok\n' > /tmp/good.rsc
./scripts/chr-smoke-test.sh /tmp/good.rsc; echo "exit=$?"
```
Expected: `exit=0`.

- [ ] **Step 6: Document the limits**

Create `docs/chr-smoke-test.md` recording: how to run it; that a CHR has no wireless hardware so CAPsMAN config can be parsed but no AP will adopt; that a CHR reports a different license level than a real L009, so license-ceiling logic needs unit tests instead; and that the image is 7.16.2 while the fleet runs 7.25beta5.

- [ ] **Step 7: Commit**

```bash
git add scripts/chr-smoke-test.sh docs/chr-smoke-test.md
git commit -m "test: add CHR smoke-test harness for generated RouterOS scripts"
```

---

### Task 3: ProvisionParams and its validation

**Files:**
- Create: `backend/app/services/provisioning/__init__.py`
- Create: `backend/app/services/provisioning/params.py`
- Test: `backend/tests/test_provision_params.py`

**Interfaces:**
- Produces:
  ```python
  KNOWN_TIMEZONES: frozenset[str]   # includes "Africa/Banjul", "UTC", "Africa/Dakar"
  SLUG_RE  # re.compile(r"[a-z0-9][a-z0-9-]{0,30}[a-z0-9]") used with .fullmatch()

  @dataclass(frozen=True)
  class ProvisionParams:
      site_slug: str; timezone: str
      lan_cidr: str; gateway: str; pool_start: str; pool_end: str
      wan_interface: str; bridge_name: str
      wg_private_key: str; wg_client_ip: str
      wg_server_public_key: str; wg_server_endpoint: str; wg_server_port: int
      wg_subnet_cidr: str
      api_username: str; api_password: str
      hotspot_dns_name: str

  def build_params(*, site_slug: str, wg_private_key: str, wg_client_ip: str,
                   wg_server_public_key: str, wg_server_endpoint: str,
                   wg_server_port: int, api_password: str,
                   timezone: str = "Africa/Banjul",
                   lan_cidr: str = "10.15.0.0/16") -> ProvisionParams
  ```
  `build_params` raises `ValueError` on any invalid input. Later tasks consume `ProvisionParams` only.

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/test_provision_params.py`:

```python
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
    "counter\n",        # trailing newline alone: `^...$` accepts this
    "counter\r",
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
```

- [ ] **Step 2: Run to confirm failure**

```bash
docker run --rm -v "$PWD/backend:/app" -w /app netguard-backend:latest \
  python -m pytest tests/test_provision_params.py -q
```
Expected: collection error — `app.services.provisioning` does not exist.

- [ ] **Step 3: Implement**

Create `backend/app/services/provisioning/__init__.py` (empty) and `params.py`:

```python
"""Validated inputs for the one-shot provisioning script.

Everything that could make a generated script dangerous or silently wrong is
rejected here, before any RouterOS text exists. The section builders in
`sections.py` then take a ProvisionParams and never re-validate.
"""
import ipaddress
import re
from dataclasses import dataclass

# Rejected, not escaped: the generated script runs with full admin rights, and
# an escaping bug in a config language with several quoting contexts is a
# hole. A site name is ours to constrain.
# fullmatch, NOT `^...$` with .match(): Python's `$` also matches immediately
# before a trailing newline, so `^...$` ACCEPTS "counter\n". A newline is a
# RouterOS statement terminator, which is exactly the injection this rejection
# exists to prevent. Confirmed accepted by the Task 3 reviewer before this fix.
SLUG_RE = re.compile(r"[a-z0-9][a-z0-9-]{0,30}[a-z0-9]")

# Zones plausible for this deployment. Kept explicit rather than pulling in a
# tz database: RouterOS rejects an unknown zone mid-script, after earlier
# sections have already applied.
KNOWN_TIMEZONES = frozenset({
    "Africa/Banjul", "Africa/Dakar", "Africa/Bissau", "Africa/Conakry",
    "Africa/Freetown", "Africa/Abidjan", "Africa/Accra", "Africa/Lagos",
    "Europe/London", "UTC",
})

WG_SUBNET_CIDR = "10.13.13.0/24"


@dataclass(frozen=True)
class ProvisionParams:
    site_slug: str
    timezone: str
    lan_cidr: str
    gateway: str
    pool_start: str
    pool_end: str
    wan_interface: str
    bridge_name: str
    wg_private_key: str
    wg_client_ip: str
    wg_server_public_key: str
    wg_server_endpoint: str
    wg_server_port: int
    wg_subnet_cidr: str
    api_username: str
    api_password: str
    hotspot_dns_name: str


def build_params(*, site_slug: str, wg_private_key: str, wg_client_ip: str,
                 wg_server_public_key: str, wg_server_endpoint: str,
                 wg_server_port: int, api_password: str,
                 timezone: str = "Africa/Banjul",
                 lan_cidr: str = "10.15.0.0/16") -> ProvisionParams:
    if not SLUG_RE.fullmatch(site_slug or ""):
        raise ValueError(
            "site_slug must be 2-32 lowercase letters, digits or hyphens, "
            "starting and ending alphanumeric"
        )
    if timezone not in KNOWN_TIMEZONES:
        raise ValueError(f"timezone {timezone!r} is not in KNOWN_TIMEZONES")
    for name, value in (("wg_private_key", wg_private_key),
                        ("wg_server_public_key", wg_server_public_key),
                        ("api_password", api_password),
                        ("wg_server_endpoint", wg_server_endpoint)):
        if not value:
            raise ValueError(f"{name} is required")

    lan = ipaddress.ip_network(lan_cidr, strict=True)
    wg = ipaddress.ip_network(WG_SUBNET_CIDR, strict=True)
    if lan.overlaps(wg):
        raise ValueError(
            f"lan_cidr {lan_cidr} would overlap the WireGuard subnet "
            f"{WG_SUBNET_CIDR}; the router would route its own management "
            "tunnel into the customer bridge"
        )

    gateway = str(lan.network_address + 1)              # 10.15.0.1
    # Pool starts in the second /24 so the first stays free for APs,
    # switches and counter hardware.
    pool_start = str(lan.network_address + 258)          # 10.15.1.2
    pool_end = str(lan.broadcast_address - 257)          # 10.15.254.254

    return ProvisionParams(
        site_slug=site_slug, timezone=timezone,
        lan_cidr=lan_cidr, gateway=gateway,
        pool_start=pool_start, pool_end=pool_end,
        wan_interface="ether1", bridge_name="bridge-hotspot",
        wg_private_key=wg_private_key, wg_client_ip=wg_client_ip,
        wg_server_public_key=wg_server_public_key,
        wg_server_endpoint=wg_server_endpoint, wg_server_port=wg_server_port,
        wg_subnet_cidr=WG_SUBNET_CIDR,
        api_username="netguard", api_password=api_password,
        hotspot_dns_name="login.netguard.local",
    )
```

- [ ] **Step 4: Run tests** — expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/provisioning/ backend/tests/test_provision_params.py
git commit -m "feat(backend): validated ProvisionParams for router provisioning"
```

---

### Task 4: Core sections — preflight, clock, bridge, addressing, DNS, NAT

**Files:**
- Create: `backend/app/services/provisioning/sections.py`
- Test: `backend/tests/test_provision_sections_core.py`

**Interfaces:**
- Consumes: `ProvisionParams` from Task 3.
- Produces, each `(p: ProvisionParams) -> list[str]`:
  `preflight`, `identity_and_clock`, `bridge`, `addressing`, `dns_and_nat`

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/test_provision_sections_core.py`:

```python
from app.services.provisioning.params import build_params
from app.services.provisioning import sections

P = build_params(
    site_slug="serrekunda-counter",
    wg_private_key="cHJpdmF0ZS1rZXktbm90LXJlYWw=",
    wg_client_ip="10.13.13.7",
    wg_server_public_key="c2VydmVyLWtlecKgbm90LXJlYWw=",
    wg_server_endpoint="74.208.167.166", wg_server_port=51820,
    api_password="Xk7mQp2rTz9wLb4nHc6v",
)


def text(lines):
    return "\n".join(lines)


def test_preflight_refuses_routeros_6():
    # NOT "these two substrings appear somewhere in preflight" -- the hotspot and
    # wireguard guards already contain `:error`, and `get version` appears in the
    # banner, so that form passes with the whole version guard DELETED. Confirmed
    # survived mutation in the Task 4 review. Assert the guard as one unit.
    lines = sections.preflight(P)
    guard = [l for l in lines if "get version" in l and ":error" in l]
    assert guard, "no single line both reads the version and errors on it"
    assert any("7" in l for l in guard), "version guard does not name the floor"


def test_preflight_greenfield_guards_actually_error():
    # Same trap: asserting the substrings `/ip hotspot find` and
    # `wireguard-netguard` survives removing the `:error` that makes them a
    # guard rather than a print.
    lines = sections.preflight(P)
    for probe in ("/ip hotspot find", "wireguard-netguard"):
        guard = [l for l in lines if probe in l and ":error" in l]
        assert guard, f"{probe} is checked but does not abort"


def test_clock_enables_the_ntp_client():
    # Voucher durations are enforced by the router's clock, so an NTP client
    # that is configured but not ENABLED is a silent revenue bug. Asserting the
    # servers alone survived deleting `set enabled=yes`.
    t = text(sections.identity_and_clock(P))
    assert "/system ntp client set" in t
    assert "enabled=yes" in t


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


def test_clock_comes_before_anything_time_dependent():
    t = text(sections.identity_and_clock(P))
    assert "/system ntp client" in t
    assert "time-zone-name=Africa/Banjul" in t


def test_addressing_matches_the_agreed_plan():
    t = text(sections.addressing(P))
    assert "address=10.15.0.1/16" in t
    assert "ranges=10.15.1.2-10.15.254.254" in t
    assert "lease-time=4h" in t
    assert "authoritative=yes" in t


def test_dns_is_open_to_clients_but_nat_exists():
    t = text(sections.dns_and_nat(P))
    assert "allow-remote-requests=yes" in t
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
```

- [ ] **Step 2: Run to confirm failure** — expected: `ImportError` / `AttributeError` for `sections`.

- [ ] **Step 3: Implement the five sections**

Create `backend/app/services/provisioning/sections.py`. Each function returns
`list[str]`. Begin the file with:

```python
"""RouterOS config, one function per section.

Each takes a validated ProvisionParams and returns lines of RouterOS CLI.
Pure text: nothing here touches a router, which is what makes it testable.

The RouterOS syntax in this module is written from MikroTik's documentation
and is verified by `scripts/chr-smoke-test.sh`, not by these unit tests. A
unit test proves we emit what we intended; only a real RouterOS parser proves
what we intended is valid.
"""
```

`preflight(p)` emits, in order: a RouterOS major-version check that `:error`s
below 7; an abort if `[:len [/ip hotspot find]] > 0`; an abort if the
`wireguard-netguard` interface exists; and license level, device-mode, free RAM
and free disk **printed** (not fatal). Wrap the `license` and `device-mode`
reads in `:do {...} on-error={...}` so a build lacking either command still
runs. Print a plain-language note when device-mode is `home`, saying hotspot is
blocked and that enabling it needs a physical button press or a cold reboot.

`identity_and_clock(p)` sets `/system identity` from the slug, the timezone, and
enables the NTP client with `time.cloudflare.com,time.google.com`.

`bridge(p)` creates `bridge-hotspot` and adds `ether2`–`ether8` plus the
wireless interfaces as ports. Guard every port add on the interface existing
(`:if ([:len [/interface find where name="X"]] > 0)`), because customers
provision boards with fewer ports than the reference L009. Include a guarded
`wlan1` alongside `wifi1`/`wifi2`: the L009 uses the new `/interface wifi`
stack, but an older board self-provisioned by a customer exposes `wlan1`, and
without it that router gets NO radio in the bridge — a hotspot with no wireless,
which looks like a working install. `ether1` stays out — it is the WAN uplink. Leave
the SFP port out with a comment saying it is the likely distribution uplink.

`addressing(p)` creates the pool, the `/ip address` on the bridge, the DHCP
server and its network, using `p.gateway`, `p.pool_start`, `p.pool_end`.

`dns_and_nat(p)` sets `/ip dns` with `allow-remote-requests=yes`,
`servers=1.1.1.1,8.8.8.8`, `cache-size=4096KiB`, and adds the srcnat
masquerade on `p.wan_interface`.

- [ ] **Step 4: Run the tests** — expected: all pass.

- [ ] **Step 5: Validate the syntax against a real router**

```bash
python - <<'EOF' > /tmp/core.rsc
from app.services.provisioning.params import build_params
from app.services.provisioning import sections
p = build_params(site_slug="smoke", wg_private_key="k", wg_client_ip="10.13.13.7",
                 wg_server_public_key="k", wg_server_endpoint="203.0.113.1",
                 wg_server_port=51820, api_password="Xk7mQp2rTz9wLb4nHc6v")
for fn in (sections.identity_and_clock, sections.bridge, sections.addressing, sections.dns_and_nat):
    print("\n".join(fn(p)))
EOF
./scripts/chr-smoke-test.sh /tmp/core.rsc
```
Expected: exit 0. `preflight` is excluded here because it deliberately aborts on
a router that has no hotspot — test it separately by asserting it exits non-zero
on a CHR that has had `/ip hotspot add` run first.

**If RouterOS rejects a line, fix `sections.py` and update the unit test to
match reality.** The router is the authority, not the test.

- [ ] **Step 6: Commit**

```bash
git add backend/app/services/provisioning/sections.py backend/tests/test_provision_sections_core.py
git commit -m "feat(backend): core provisioning sections with CHR-verified syntax"
```

---

### Task 5: Hotspot sections — server, voucher tiers, walled garden

**Files:**
- Modify: `backend/app/services/provisioning/sections.py`
- Test: `backend/tests/test_provision_sections_hotspot.py`

**Interfaces:**
- Produces: `hotspot_server(p)`, `voucher_profiles(p)`, `walled_garden(p)` — each `-> list[str]`.

- [ ] **Step 1: Write the failing tests**

```python
from app.services.provisioning.params import build_params
from app.services.provisioning import sections

P = build_params(
    site_slug="serrekunda-counter", wg_private_key="k" * 44, wg_client_ip="10.13.13.7",
    wg_server_public_key="k" * 44, wg_server_endpoint="74.208.167.166",
    wg_server_port=51820, api_password="Xk7mQp2rTz9wLb4nHc6v",
)
def text(ls): return "\n".join(ls)


def test_hotspot_profile_needs_no_certificate():
    t = text(sections.hotspot_server(P))
    assert "login-by=http-chap,mac-cookie" in t
    assert "dns-name=login.netguard.local" in t
    # There is no domain for this deployment, so there can be no trusted cert.
    assert "ssl-certificate" not in t
    assert "https" not in t


def test_hotspot_timeouts_keep_the_host_table_clean():
    t = text(sections.hotspot_server(P))
    assert "login-timeout=5m" in t
    assert "idle-timeout=5m" in t
    assert "keepalive-timeout=2m" in t


def test_all_four_tiers_exist_with_agreed_sharing():
    t = text(sections.voucher_profiles(P))
    for name in ("default", "1-Hour", "24-Hours", "7-Days"):
        assert f"name={name}" in t
    assert "shared-users=4" in t
    assert "session-timeout=1h" in t
    assert "session-timeout=24h" in t
    assert "session-timeout=7d" in t


def test_nothing_in_the_hotspot_is_rate_limited():
    # Explicitly specified: bandwidth is unshaped, tiers differ by duration.
    # Scans hotspot_server TOO, not just the tiers. Scoped to voucher_profiles
    # alone, this gate survived `rate-limit` being added to
    # `/ip hotspot profile add` and to `/ip hotspot add` -- confirmed by
    # mutation in the Task 5 review. The constraint says "any hotspot profile".
    for fn in (sections.voucher_profiles, sections.hotspot_server):
        for line in fn(P):
            if line.strip().startswith("#"):
                continue          # the explanatory comment names the rule
            assert "rate-limit" not in line, f"{fn.__name__}: {line}"


def test_walled_garden_allows_captive_portal_detection():
    t = text(sections.walled_garden(P))
    # Without these the phone's probe fails and the portal never pops.
    assert "connectivitycheck.gstatic.com" in t
    assert "captive.apple.com" in t
    assert "msftconnecttest.com" in t


def test_walled_garden_names_the_unfinished_payment_list():
    # The provider is unknown; the gap must be visible in the output, not silent.
    t = text(sections.walled_garden(P))
    assert "PAYMENT PROVIDER" in t.upper()
```

- [ ] **Step 2: Run to confirm failure.**

- [ ] **Step 3: Implement the three sections**

`hotspot_server(p)` adds `/ip hotspot profile` named `netguard` with
`hotspot-address=p.gateway`, `dns-name=p.hotspot_dns_name`,
`login-by=http-chap,mac-cookie`, `http-cookie-lifetime=3d`; then
`/ip hotspot add` on the bridge with the pool, `idle-timeout=5m`,
`keepalive-timeout=2m`, `login-timeout=5m`.

`voucher_profiles(p)` adds the four `/ip hotspot user profile` entries from the
Global Constraints table. Emit **no** `rate-limit` key. Include a comment that
`shared-users=4` means 500 licensed sessions is as few as 125 vouchers.

`walled_garden(p)` adds `/ip hotspot walled-garden` entries for the three OS
probe hosts plus the portal name. **No NTP entry** — the walled garden governs
unauthenticated CLIENTS, and a client does not need NTP to reach the portal.
The ROUTER's clock is set by `identity_and_clock` and the router is not subject
to its own walled garden, so an NTP entry here buys nothing and would need an
arbitrary hardcoded IP.
End with a literal comment line:
`# TODO PAYMENT PROVIDER: add the provider's hosts here before going live.`
A comment in generated output is correct here — the gap belongs in front of the
installer, not buried in a spec.

- [ ] **Step 4: Run tests** — expected: pass.

- [ ] **Step 5: CHR-validate** the three sections appended after the core ones (hotspot needs the bridge and pool to exist first). Expected exit 0.

- [ ] **Step 6: Commit**

```bash
git add backend/app/services/provisioning/sections.py backend/tests/test_provision_sections_hotspot.py
git commit -m "feat(backend): hotspot server, voucher tiers and walled garden sections"
```

---

### Task 6: Firewall, hardening, and the least-privilege API user

**Files:**
- Modify: `backend/app/services/provisioning/sections.py`
- Create: `backend/app/services/provisioning/secrets.py`
- Test: `backend/tests/test_provision_sections_security.py`

**Interfaces:**
- Produces: `firewall(p)`, `api_user(p)` in `sections.py`; and in `secrets.py`:
  ```python
  API_PASSWORD_ALPHABET: str
  def generate_api_password(length: int = 24) -> str
  ```

- [ ] **Step 1: Write the failing tests**

```python
import re
from app.services.provisioning.params import build_params
from app.services.provisioning import sections
from app.services.provisioning.secrets import generate_api_password, API_PASSWORD_ALPHABET

P = build_params(
    site_slug="serrekunda-counter", wg_private_key="k" * 44, wg_client_ip="10.13.13.7",
    wg_server_public_key="k" * 44, wg_server_endpoint="74.208.167.166",
    wg_server_port=51820, api_password="Xk7mQp2rTz9wLb4nHc6v",
)
def text(ls): return "\n".join(ls)


# Review Focus #4 — a password RouterOS would mis-parse.
def test_generated_password_cannot_break_routeros_quoting():
    for ch in '"\'$\;{} \n\r\t`':
        assert ch not in API_PASSWORD_ALPHABET
    for _ in range(200):
        pw = generate_api_password()
        assert len(pw) == 24
        assert re.fullmatch(r"[A-Za-z0-9]{24}", pw), pw


def test_passwords_are_not_predictable():
    assert len({generate_api_password() for _ in range(50)}) == 50


def test_api_service_is_pinned_to_the_tunnel_not_the_world():
    t = text(sections.firewall(P))
    assert "set api disabled=no port=8728 address=10.13.13.0/24" in t
    assert "0.0.0.0/0" not in t


def test_router_is_not_an_open_dns_resolver():
    # allow-remote-requests=yes is required for clients, so the WAN must be shut.
    t = text(sections.firewall(P))
    assert "dst-port=53" in t
    assert "in-interface=ether1" in t
    assert "action=drop" in t


def test_hotspot_login_page_is_not_broken_by_hardening():
    t = text(sections.firewall(P))
    # www serves the captive portal; disabling it would silently kill logins.
    assert "set www disabled=yes" not in t
    for svc in ("telnet", "ftp", "api-ssl", "www-ssl"):
        assert f"set {svc} disabled=yes" in t


def test_api_user_is_least_privilege_and_source_restricted():
    t = text(sections.api_user(P))
    assert "name=netguard" in t
    assert "address=10.13.13.0/24" in t
    assert "!sensitive" in t   # must not be able to read other stored creds
    assert "!policy" in t
    assert "name=admin" not in t
```

- [ ] **Step 2: Run to confirm failure.**

- [ ] **Step 3: Implement**

`backend/app/services/provisioning/secrets.py`:

```python
"""Credential generation for provisioned routers."""
import secrets
import string

# Alphanumeric only, deliberately. RouterOS config has several quoting
# contexts and a password containing a quote, `$`, `;`, backslash or a brace
# either fails to parse or creates a user whose password differs from the one
# NetGuard stored -- a router that provisions "successfully" and can never be
# reached. 24 alphanumerics is ~143 bits; the lost symbol classes cost
# nothing that matters.
API_PASSWORD_ALPHABET = string.ascii_letters + string.digits


def generate_api_password(length: int = 24) -> str:
    return "".join(secrets.choice(API_PASSWORD_ALPHABET) for _ in range(length))
```

`firewall(p)` emits, using `place-before` so order is explicit: accept
established/related/untracked; drop invalid; accept input from
`p.wg_subnet_cidr`; accept ICMP; drop udp+tcp 53 arriving on `p.wan_interface`;
drop remaining input from `p.wan_interface`. Then `/ip service`: disable
`telnet`, `ftp`, `www-ssl`, `api-ssl`; pin `ssh`, `winbox`, `api` to
`p.wg_subnet_cidr`; leave `www` enabled with a comment saying the hotspot login
page depends on it. Then neighbor discovery off, both mac-servers off,
`/ip cloud set ddns-enabled=no`.

`api_user(p)` adds the `netguard` group with the policy list from the spec and
the user with `address=p.wg_subnet_cidr` and `password=p.api_password`.

- [ ] **Step 4: Run tests** — expected: pass.

- [ ] **Step 5: CHR-validate.** Apply core + hotspot + these two sections. Expected exit 0.

  **Take care here:** the firewall section can lock the harness out of its own
  VM. Run the firewall section last in the smoke script and confirm the harness
  reports the router's output before the connection drops; if it hangs, have the
  harness apply the firewall via a scheduled one-shot script instead of inline.

- [ ] **Step 6: Commit**

```bash
git add backend/app/services/provisioning/sections.py backend/app/services/provisioning/secrets.py backend/tests/test_provision_sections_security.py
git commit -m "feat(backend): firewall hardening and least-privilege API user"
```

---

### Task 7: WireGuard and CAPsMAN sections

**Files:**
- Modify: `backend/app/services/provisioning/sections.py`
- Test: `backend/tests/test_provision_sections_tunnel.py`

**Interfaces:**
- Produces: `wireguard(p)`, `capsman(p)` — each `-> list[str]`.

- [ ] **Step 1: Write the failing tests**

```python
from app.services.provisioning.params import build_params
from app.services.provisioning import sections

P = build_params(
    site_slug="serrekunda-counter",
    wg_private_key="cHJpdmF0ZS1rZXktbm90LXJlYWw=", wg_client_ip="10.13.13.7",
    wg_server_public_key="c2VydmVyLWtleS1ub3QtcmVhbA==",
    wg_server_endpoint="74.208.167.166", wg_server_port=51820,
    api_password="Xk7mQp2rTz9wLb4nHc6v",
)
def text(ls): return "\n".join(ls)


def test_wireguard_matches_the_conventions_monitoring_depends_on():
    t = text(sections.wireguard(P))
    assert "name=wireguard-netguard" in t
    assert "listen-port=13231" in t
    assert "mtu=1420" in t
    assert "persistent-keepalive=25s" in t
    assert "endpoint-address=74.208.167.166" in t
    assert "endpoint-port=51820" in t


def test_wireguard_peer_is_scoped_to_the_tunnel():
    t = text(sections.wireguard(P))
    assert "allowed-address=10.13.13.0/24" in t
    assert "0.0.0.0/0" not in t


def test_router_gets_its_tunnel_address_and_a_route_to_the_server():
    t = text(sections.wireguard(P))
    assert "address=10.13.13.7" in t
    assert "dst-address=10.13.13.1/32" in t


def test_capsman_uses_the_modern_stack_only():
    t = text(sections.capsman(P))
    assert "/interface wifi" in t
    # The legacy stack allows manager-forwarding, which would tunnel every
    # client through a 2-core router. Must not be used.
    assert "/caps-man" not in t


def test_capsman_puts_clients_on_the_hotspot_bridge():
    t = text(sections.capsman(P))
    assert "bridge-hotspot" in t


def test_capsman_provisions_any_ap_without_per_ap_work():
    # At 100+ APs, per-AP configuration is not viable.
    t = text(sections.capsman(P))
    assert "provisioning" in t
```

- [ ] **Step 2: Run to confirm failure.**

- [ ] **Step 3: Implement**

`wireguard(p)` mirrors `WireGuardService.generate_mikrotik_script` exactly —
same interface name, port, MTU, keepalive and `/32` route — but with
`allowed-address=p.wg_subnet_cidr`. Add a comment pointing at
`backend/app/services/wireguard.py` and saying these values must stay in step
with it, because NetGuard reaches the device at its tunnel address.

`capsman(p)` enables the controller on the `/interface wifi` stack, creates a
configuration with the site SSID and a datapath bridging to `p.bridge_name`,
and a provisioning rule matching any radio so an AP adopts with no per-AP
work. Comment that this stack is local-forwarding-only and that porting to
`/caps-man` would put client traffic through the controller.

- [ ] **Step 4: Run tests** — expected: pass.

- [ ] **Step 5: CHR-validate.** A CHR has no radio, so `capsman` may parse but
  cannot be exercised; assert only that RouterOS accepts the commands. Record in
  the report which CAPsMAN lines could not be functionally verified.

- [ ] **Step 6: Commit**

```bash
git add backend/app/services/provisioning/sections.py backend/tests/test_provision_sections_tunnel.py
git commit -m "feat(backend): WireGuard and CAPsMAN provisioning sections"
```

---

### Task 8: Assemble the script

**Files:**
- Create: `backend/app/services/provisioning/script.py`
- Create: `backend/tests/fixtures/provision_expected.rsc`
- Test: `backend/tests/test_provision_script.py`

**Interfaces:**
- Produces:
  ```python
  SECTION_ORDER: tuple  # the section callables, in application order
  def build_provision_script(p: ProvisionParams) -> str
  ```

- [ ] **Step 1: Write the failing tests**

```python
import re
from pathlib import Path
from app.services.provisioning.params import build_params
from app.services.provisioning.script import build_provision_script, SECTION_ORDER
from app.services.provisioning import sections

FIXED = dict(
    site_slug="serrekunda-counter",
    wg_private_key="cHJpdmF0ZS1rZXktbm90LXJlYWw=", wg_client_ip="10.13.13.7",
    wg_server_public_key="c2VydmVyLWtleS1ub3QtcmVhbA==",
    wg_server_endpoint="74.208.167.166", wg_server_port=51820,
    api_password="Xk7mQp2rTz9wLb4nHc6v",
)
EXPECTED = Path(__file__).parent / "fixtures" / "provision_expected.rsc"


def test_matches_the_golden_file():
    got = build_provision_script(build_params(**FIXED))
    assert got == EXPECTED.read_text(), (
        "Generated script changed. If deliberate, review the diff line by line "
        "and re-record with: python -m tests.record_provision_golden"
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


def test_no_secret_appears_more_than_once():
    p = build_params(**FIXED)
    script = build_provision_script(p)
    assert script.count(p.wg_private_key) == 1
    assert script.count(p.api_password) == 1


def test_gateway_is_never_inside_the_pool():
    p = build_params(**FIXED)
    script = build_provision_script(p)
    assert f"ranges={p.pool_start}-{p.pool_end}" in script
    assert f"address={p.gateway}/16" in script


def test_api_is_never_world_open_anywhere_in_the_script():
    script = build_provision_script(build_params(**FIXED))
    assert "0.0.0.0/0" not in script


# RouterOS rejects `comment=` on these three menus (confirmed on 7.16.2 in
# Task 5: `expected end of command`, error column on the comment). They are
# identified by name instead. Listed explicitly rather than skipped by a
# substring, so adding a fourth exception is a deliberate edit.
MENUS_WITHOUT_COMMENT = (
    "/ip hotspot profile add",
    "/ip hotspot user profile add",
    "/ip hotspot add",
)


def test_every_add_is_attributable_to_netguard():
    script = build_provision_script(build_params(**FIXED))
    seen = 0
    for line in script.splitlines():
        if " add " not in line:
            continue
        if any(m in line for m in MENUS_WITHOUT_COMMENT):
            continue
        seen += 1
        assert 'comment="NetGuard"' in line, line
    assert seen >= 10, f"expected many created objects, matched {seen}"


def test_the_comment_exempt_objects_are_identifiable_by_name():
    # They cannot carry a comment, so the only handle on them is their name.
    # Without this, the exemption above would let them become anonymous.
    script = build_provision_script(build_params(**FIXED))
    for line in script.splitlines():
        if any(m in line for m in MENUS_WITHOUT_COMMENT):
            assert "name=" in line, line


def test_summary_tells_the_installer_what_they_need():
    script = build_provision_script(build_params(**FIXED))
    tail = script[-2000:]
    for token in ("license", "10.15.0.1", "netguard", "wireguard"):
        assert token in tail.lower()
```

- [ ] **Step 2: Run to confirm failure.**

- [ ] **Step 3: Implement `script.py`**

```python
"""Assemble the section builders into one pasteable script."""
from .params import ProvisionParams
from . import sections

# Order is behavioural, not cosmetic:
#   preflight first so an unsuitable router is refused before anything applies;
#   clock before hotspot because voucher durations are enforced by it;
#   addressing before hotspot because the hotspot binds the bridge and pool;
#   firewall second-to-last because it can cut the installer's own session;
#   summary last so it is what remains on screen.
SECTION_ORDER = (
    sections.preflight,
    sections.identity_and_clock,
    sections.bridge,
    sections.addressing,
    sections.dns_and_nat,
    sections.hotspot_server,
    sections.voucher_profiles,
    sections.walled_garden,
    sections.api_user,
    sections.wireguard,
    sections.capsman,
    sections.firewall,
    sections.summary,
)


def build_provision_script(p: ProvisionParams) -> str:
    out: list[str] = []
    for fn in SECTION_ORDER:
        out.extend(fn(p))
        out.append("")
    return "\n".join(out)
```

Also add `sections.summary(p)`, printing board, RouterOS version, license level
and ceiling, LAN and gateway, DHCP range, profile names, the API **username**,
and the tunnel address.

**The summary must NOT print the API password.** Controller ruling: the
"each secret appears exactly once" invariant above is the one worth keeping. The
NetGuard UI already shows the password (Task 10), and a script pasted into a
terminal can be scrolled back or logged by whoever is standing at the counter.
Print the username and a line telling the installer the password is in the
NetGuard dashboard.

- [ ] **Step 4: Record the golden file**

Create `backend/tests/record_provision_golden.py` that writes the fixture, then run it. Review the generated `.rsc` **by reading it end to end** before committing — this file is the contract, and a golden file recorded without being read just freezes whatever bug exists.

- [ ] **Step 5: Run tests** — expected: pass.

- [ ] **Step 6: CHR-validate the whole script.** Expected exit 0 apart from `preflight`'s deliberate refusal behaviour, which gets its own run against a pre-configured CHR.

- [ ] **Step 7: Commit**

```bash
git add backend/app/services/provisioning/script.py backend/tests/test_provision_script.py backend/tests/fixtures/provision_expected.rsc backend/tests/record_provision_golden.py
git commit -m "feat(backend): assemble the one-shot provisioning script"
```

---

### Task 9: The endpoint

**Files:**
- Modify: `backend/app/routers/devices.py` (add after the existing `provision-wireguard` endpoint at line 163)
- Modify: `backend/app/schemas/inventory.py`
- Test: `backend/tests/test_provision_endpoint.py`

**Interfaces:**
- Consumes: `build_params`, `build_provision_script`, `generate_api_password`.
- Produces:
  ```
  GET /api/v1/inventory/devices/{device_id}/provision-script?site_slug=&timezone=
  -> ProvisionScriptResponse(device_id, site_slug, script, api_username,
                             api_password, warnings: list[str])
  ```
  Side effect: sets `device.ssh_username="netguard"` and `device.ssh_password=<generated>`, because that is the credential pair `backend/app/routers/hotspot.py:270` uses for the RouterOS API.

- [ ] **Step 1: Write the failing tests**

```python
import pytest
from app.services.provisioning.params import build_params
from app.services.provisioning.script import build_provision_script


# Review Focus #1 — the most dangerous input: a device with no tunnel yet.
def test_refuses_a_device_with_no_wireguard_key():
    with pytest.raises(ValueError, match="wg_private_key"):
        build_params(
            site_slug="a-site", wg_private_key="", wg_client_ip="10.13.13.7",
            wg_server_public_key="k", wg_server_endpoint="203.0.113.1",
            wg_server_port=51820, api_password="Xk7mQp2rTz9wLb4nHc6v",
        )


def test_script_never_contains_a_placeholder_or_none():
    p = build_params(
        site_slug="a-site", wg_private_key="r" * 44, wg_client_ip="10.13.13.7",
        wg_server_public_key="s" * 44, wg_server_endpoint="203.0.113.1",
        wg_server_port=51820, api_password="Xk7mQp2rTz9wLb4nHc6v",
    )
    s = build_provision_script(p)
    for bad in ("None", "PLACEHOLDER", "NOT_FOUND", "auto-read-from-volume"):
        assert bad not in s
```

Plus an HTTP-level test following the pattern in `backend/tests/test_voucher_job_endpoints.py`: a device lacking `wg_private_key` returns **409** with a message telling the caller to run `provision-wireguard` first; a provisioned device returns 200, a script containing its real tunnel IP, and a 24-character alphanumeric password; and the device record afterwards has `ssh_username == "netguard"`.

- [ ] **Step 2: Run to confirm failure.**

- [ ] **Step 3: Implement**

Add `ProvisionScriptResponse` to `backend/app/schemas/inventory.py`. Add the
endpoint to `devices.py`, following the existing `provision-wireguard` handler
for auth (`Depends(get_authorized_actor)`), device lookup and
`decrypt_device_secrets`. It must:

1. 404 if the device does not exist.
2. **409 if `device.wg_private_key` is missing**, with the remedy named. Do not
   emit a script with a placeholder key — that is the existing generator's
   failure mode and the thing Review Focus #1 exists to prevent.
3. Resolve the server public key the same way the existing handler does, and
   raise rather than substitute a placeholder.
4. `generate_api_password()`, `build_params(...)`, `build_provision_script(...)`.
5. Persist `ssh_username`/`ssh_password` so monitoring works the moment the
   script is pasted, and commit.
6. Return the response, with `warnings` carrying anything non-fatal.

Wrap `build_params`' `ValueError` into a 400 so a bad `site_slug` is a client
error, not a 500.

- [ ] **Step 4: Run the full suite** — expected: 82 baseline plus the new tests, none failing.

- [ ] **Step 5: Commit**

```bash
git add backend/app/routers/devices.py backend/app/schemas/inventory.py backend/tests/test_provision_endpoint.py
git commit -m "feat(backend): endpoint returning a one-shot router provisioning script"
```

---

### Task 10: The self-service surface

Customers now onboard themselves, so the endpoint is unusable without a button.

**Files:**
- Modify: `frontend/src/pages/Devices.jsx` (NOT Settings.jsx — see the note below)
- Test: `frontend/src/test/provision-script.test.jsx`

**Interfaces:**
- Consumes: `GET /api/v1/inventory/devices/{id}/provision-script` from Task 9.

**Controller correction to this plan:** an earlier draft named `Settings.jsx`.
That is wrong. `Settings.jsx` only lists the endpoint in an API reference
*table*; the working script flow already lives in `Devices.jsx`:

- `Devices.jsx:147` `handleProvision()` — POSTs `provision-wireguard`, puts
  `res.data.mikrotik_script` in state, opens a modal
- `Devices.jsx:453` renders the script
- `Devices.jsx:456` an explicit copy button using
  `navigator.clipboard.writeText` plus an `alert()` confirmation

Extend that pattern rather than building a second one. The new control sits
beside the existing WireGuard action on the selected device, and reuses the same
modal shape so an operator sees one consistent flow.

- [ ] **Step 1: Write the failing test**

Render `Devices.jsx` with a mocked device list and assert: a "Get setup script"
control exists for the selected router; clicking it calls
`/inventory/devices/{id}/provision-script` exactly once; the returned script is
rendered; the generated API password is shown with a warning that it appears
only once; and a 409 response renders the remedy text ("provision WireGuard
first") rather than a raw error string.

- [ ] **Step 2: Run it to confirm it fails.**

- [ ] **Step 3: Implement**, reusing the existing modal and the ink/signal
tokens. The script block must NOT be auto-selected or auto-copied — it is a
credential, and silently putting a router's private key on someone's clipboard
is a surprise. Keep the existing explicit copy button pattern.

Note the existing flow reports errors with `alert()`. Match the surrounding
code rather than introducing a second error convention in one file; improving
`alert()` usage across the page is out of scope here.

- [ ] **Step 4: Run the frontend suite** — baseline 148 passing, none may regress:
  `cd frontend && npx vitest run`

- [ ] **Step 5: Measure contrast**, per the Global Constraints of the visual-identity plan, since this adds UI to a migrated page:
  `cd /tmp/pwshot && node measure.mjs http://127.0.0.1:5199 /settings prov --min-nodes=60`
  Expected: 0 failures in both themes.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/pages/Settings.jsx frontend/src/test/provision-script.test.jsx
git commit -m "feat(frontend): self-service router setup script in Settings"
```

---

## Done when

- `GET /api/v1/inventory/devices/{id}/provision-script` returns a script that a CHR accepts end to end.
- Backend tests: 82 baseline plus the new suites, all passing.
- `scripts/chr-smoke-test.sh` demonstrably fails on invalid input and passes on the real script.
- No `0.0.0.0/0` anywhere in either generated script.
- The golden file has been read line by line by a human, not just recorded.

## Not in this plan

- Board layouts other than `L009UiGS-2HaxD`. The script reports the board it found; adapting the bridge section for a smaller router is follow-on work.
- Re-configuring the two live routers.
- Moving the hotspot gateway to a cloud CHR, which is the answer beyond ~500 concurrent users per site.
- Porting the `on-login` voucher accounting script.
- Payment-provider walled-garden hosts.
- Renaming `ssh_username`/`ssh_password` to reflect that they hold API credentials.
