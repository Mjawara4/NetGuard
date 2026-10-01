# One-Shot MikroTik Provisioning — Design

**Date:** 2026-09-29
**Status:** awaiting review

## Purpose

Turn a factory-fresh MikroTik router into a working NetGuard hotspot site with a
single paste into the terminal: addressing, DHCP, NAT, hotspot with voucher
tiers, a captive portal, a CAPsMAN controller for the site's access points, the
WireGuard tunnel back to the NetGuard cloud, and the firewall and hardening
around all of it.

**Audience:** whoever is physically installing a router at a new site — and
from now on that is **not only NetGuard's own staff**. Customers onboarding
themselves get this script to configure their own router before using the
platform. They may have no RouterOS knowledge. Success is: paste, wait, read the
summary the script prints, and the site sells vouchers.

**Reference model: `L009UiGS-2HaxD`.** This is the board the fleet standardises
on (confirmed as the model of the "Hagie kumbija" site, which is configured and
working). The port plan below — `ether1` as WAN, `ether2`-`ether8` bridged,
SFP left out — is that board's layout. A different model with fewer ports will
need the bridge section adjusted; the script should report the board name it
found rather than assume.

### What self-service onboarding changes

Three consequences of handing this to people NetGuard does not employ:

1. **`site_slug` becomes untrusted input.** It arrives from a web form filled in
   by a customer, and it is interpolated into a script that runs with full admin
   rights on a router. Rejecting metacharacters rather than escaping them stops
   being defensive tidiness and becomes the actual boundary.
2. **Every site can safely use the same `10.15.0.0/16`.** This looks wrong at
   first glance and is worth stating plainly: NetGuard only ever reaches the
   *router*, at its unique `10.13.13.x` tunnel address. It never routes into a
   customer's LAN, so identical client subnets across hundreds of tenants never
   meet and cannot collide. Only the tunnel address must be unique, and the
   backend already allocates that.
3. **Each script carries that one router's secrets** — its WireGuard private key
   and a freshly generated API password. It is therefore a credential, not a
   document: it must not be logged, cached, or emailed around, and the endpoint
   returns it once.

**Greenfield only**, but two things I originally got wrong about what that
means, both confirmed on a real RouterOS 7.16.2 router during Task 8's review:

1. **A factory-fresh MikroTik is NOT a blank router.** It ships with a default
   configuration that already has `ether2`-`ether5` in a bridge called `bridge`.
   So `/interface bridge port add interface=ether2` fails with
   `failure: device already added as bridge port`, part-way through, leaving the
   identity changed and `bridge-hotspot` created but no firewall applied. The
   script must therefore **move** ports out of whatever bridge holds them rather
   than assume none does, and the pieces that create objects must tolerate
   being re-run after a partial failure. "No idempotency" was a decision made
   on a false premise.

2. **`:error` does not stop a pasted script.** It aborts an `/import`, but a
   paste is a sequence of independent commands: the refusal prints and
   execution continues to the end. Confirmed by feeding the script to a router
   that already had a hotspot — it printed the refusal and then printed
   "provisioning complete". Every preflight verification in this plan had used
   `/import`, because that is what the test harness uses, so the harness itself
   concealed this. The whole script is therefore wrapped in a single
   brace-enclosed block, which RouterOS treats as ONE command in both delivery
   modes, so `:error` aborts everything and `:local` also works across lines
   inside it.

Running it against a router carrying live customers remains out of scope, and
preflight refuses that case — but the refusal now has to actually stop.

## Grounding: the fleet as it actually is

Read from the running system on 2026-09-29, not assumed:

| Fact | Value |
|---|---|
| Board | `L009UiGS-2HaxD` |
| RouterOS | `7.25beta5` |
| RAM / CPU | 512 MB, 2 × ARM 800 MHz |
| License level | **5** (500 concurrent hotspot users) |
| Live sessions on one router | 54 |
| Client addressing in use | `10.15.20.x` – `10.15.22.x`, i.e. `10.15.0.0/16` |
| WireGuard subnet | `10.13.13.0/24`, server `10.13.13.1` |
| Existing hotspot profiles | `default` (`shared-users=4`), `7-Days` (carries an `on-login` script) |

The chosen LAN `10.15.0.0/16` matches what the fleet already uses and does not
collide with the WireGuard subnet.

## Capacity: what this hardware can and cannot do

Three ceilings, stated so they are visible rather than discovered in the field:

1. **License level caps concurrent hotspot users.** Level 4 = 200, Level 5 =
   500, Level 6 = unlimited. The L009 is Level 5. A cheaper hAP added later
   would be Level 4 and would begin refusing logins at exactly 200 with
   "session limit reached". The script reads `/system license` and prints the
   ceiling.
2. **The L009 has one 2.4 GHz dual-chain radio** (574 Mbit/s, no 5 GHz).
   Practical guidance is ~25 clients per radio, 80–100 under light load. The
   router is therefore configured as the *gateway and controller*. Its own radio
   still joins the hotspot bridge — turning it off would be wasteful at a small
   site — but it is sized as one more AP among many, not as the site's coverage.
   At a 100-AP site it carries a rounding error's worth of clients.
3. **100+ APs implies far more than 500 concurrent users.** At 25 clients per
   AP that is ~2,500, five times the Level 5 ceiling, through a 2-core ARM doing
   NAT. Beyond roughly 500 concurrent users a site needs either a Level 6
   license, or the hotspot gateway moved to a CHR in the cloud with the L009
   demoted to a CAPsMAN controller and L2 bridge. The script does not solve
   this; it reports the license ceiling so the wall is visible before it is
   hit. It does *not* report a current session count: on a greenfield router
   that is always zero, and concurrent-session headroom belongs on NetGuard's
   dashboard where it can be watched over time.

## Where this lives

**A NetGuard endpoint that generates the script per device**, extending the
existing `WireGuardService.generate_mikrotik_script` (`backend/app/services/
wireguard.py`) rather than shipping a static file.

This is forced: the script must embed that device's WireGuard **private key**,
its tunnel IP and the server's public key. Those are per-device secrets the
backend already mints in `WireGuardService`. A static template cannot carry
them, and asking an installer to paste keys by hand is how sites get
misconfigured.

The existing endpoint (`GET /inventory/devices/{id}/vpn-script`, surfaced in
Settings as "Get MikroTik VPN script") gains a sibling that returns the full
provisioning script. The WireGuard-only script stays, because re-keying an
existing router is a real, separate need.

### A security fix that rides along

The current generated script contains:

```
/ip service set api disabled=no port=8728 address=0.0.0.0/0
```

That exposes the RouterOS API to the entire internet, protected only by the
position of one firewall filter rule. Reorder or delete that rule and the API is
open. The new script pins the service itself:

```
/ip service set api disabled=no port=8728 address=10.13.13.0/24
```

Defence at the service, not only at the firewall. The WireGuard-only script is
corrected the same way.

## The generated script, section by section

Written as RouterOS CLI, pasteable as one block. Every object carries
`comment="NetGuard"` so provisioning is distinguishable from later hand edits.

### 1. Preflight — refuse rather than half-configure

Runs first, prints findings, and **stops** if the router is unsuitable:

- **RouterOS major version ≥ 7.** `/interface wireguard` does not exist on 6.x.
- **Already configured?** If `/ip hotspot` has any server, or a
  `wireguard-netguard` interface exists, abort with a message naming what was
  found. This is the greenfield guard.
- **Device-mode.** Since 7.17, routers ship with a device-mode; in `home` mode
  **hotspot is disabled**, and enabling a blocked feature requires *pressing a
  button on the router or a true cold reboot (unplugging it)*. No script can do
  that remotely. Preflight detects it and prints the physical step needed,
  because discovering this after the installer has left the site is expensive.
- **License level**, printed with its user ceiling.
- **Free RAM and storage**, printed.

### 2. Identity and clock

```
/system identity set name="<site-slug>"
/system clock set time-zone-name=Africa/Banjul
/system ntp client set enabled=yes servers=time.cloudflare.com,time.google.com
```

The clock is load-bearing, not housekeeping: every voucher tier is enforced by
`session-timeout` / `limit-uptime`, and a router whose clock is wrong sells
time it does not honour, or cuts customers off early. NTP before hotspot.

### 3. Bridge and ports

One bridge for the customer network. `ether1` is reserved as the WAN uplink;
`ether2`–`ether8` and the wireless interface join the bridge. The SFP port is
left out of the bridge and commented, since at this scale it is the likely
uplink to a distribution switch.

The bridge also joins the stock `LAN` interface list where one exists (see §9):
a factory-default router's firewall keys its "accept from the LAN" decision off
that list, and a bridge absent from it is treated as hostile.

### 4. Addressing and DHCP

```
/ip pool add name=hotspot-pool ranges=10.15.1.2-10.15.254.254
/ip address add address=10.15.0.1/16 interface=bridge-hotspot comment="NetGuard"
/ip dhcp-server add name=hotspot-dhcp interface=bridge-hotspot \
    address-pool=hotspot-pool lease-time=4h authoritative=yes
/ip dhcp-server network add address=10.15.0.0/16 gateway=10.15.0.1 \
    dns-server=10.15.0.1 comment="NetGuard"
```

- Gateway `10.15.0.1`, a /16 as specified. The pool deliberately starts at
  `10.15.1.2`, leaving `10.15.0.0/24` free for infrastructure — APs, switches,
  a printer at the counter — which a flat pool over the whole /16 would make
  impossible later.
- `lease-time=4h`: a /16 has ~65,000 addresses so there is no pressure to
  reclaim aggressively, and longer leases mean less DHCP chatter on a congested
  2.4 GHz medium. Long enough to survive a walk out of range, short enough that
  the lease table does not accumulate for weeks.
- `authoritative=yes` so the router answers wrong-subnet requests immediately
  rather than letting clients retry.

### 5. DNS and NAT

```
/ip dns set allow-remote-requests=yes servers=1.1.1.1,8.8.8.8 cache-size=4096KiB
/ip firewall nat add chain=srcnat out-interface=ether1 action=masquerade comment="NetGuard"
```

`allow-remote-requests` is required — hotspot clients resolve through the
router — and is why the firewall must block DNS from the WAN side (section 9).
A 4 MiB cache is sized for hundreds of clients rather than the default.

### 6. Hotspot server and profile

```
/ip hotspot profile add name=netguard hotspot-address=10.15.0.1 \
    dns-name=login.netguard.local \
    login-by=http-chap,mac-cookie \
    http-cookie-lifetime=3d
/ip hotspot add name=netguard interface=bridge-hotspot \
    address-pool=hotspot-pool profile=netguard idle-timeout=5m \
    keepalive-timeout=2m login-timeout=5m disabled=no
```

- **No `comment=` on either, and the hotspot is named `netguard`, not
  `netguard-hotspot`.** RouterOS 7.16 has no `comment` property on `/ip hotspot`
  or `/ip hotspot profile` and rejects it there (measured on a CHR), so both
  objects are deliberately untagged. The name matters beyond cosmetics:
  preflight refuses a router carrying `/ip hotspot` with any name but
  `netguard`, so the two must agree.

- **No certificate, by decision.** There is no public domain for this
  deployment, so a trusted certificate cannot be issued. It is not needed:
  captive-portal detection works through the phone's plain-HTTP connectivity
  probe plus DHCP option 114, neither of which involves TLS. The consequence,
  stated plainly: a customer whose first request is HTTPS will see a failure
  rather than the portal, until they open any HTTP page. This is the normal
  trade for hotspots without a domain.
- `dns-name=login.netguard.local` is resolved by the router's own DNS, giving
  the portal a name rather than a bare IP.
- `login-by=http-chap,mac-cookie`: the MAC cookie means a returning customer
  inside `http-cookie-lifetime` reconnects without re-entering a voucher —
  which matters when the same people buy daily.
- `login-timeout=5m` removes unauthorised hosts from the host table, so idle
  non-paying devices do not occupy entries.

### 7. Voucher tiers

Four profiles, matching how the business already sells. **No rate limits**, as
specified — bandwidth is unshaped and tiers differ only by duration:

| Profile | `session-timeout` | `shared-users` | Notes |
|---|---|---|---|
| `default` | none | 4 | Matches the live router's existing `shared-users=4` |
| `1-Hour` | `1h` | 1 | |
| `24-Hours` | `24h` | 2 | |
| `7-Days` | `7d` | 4 | |

All carry `add-mac-cookie=yes`, `mac-cookie-timeout=3d`, `idle-timeout=5m`,
`keepalive-timeout=2m`, and no `rate-limit` key at all.

`shared-users` interacts with the license ceiling and is worth stating: with
`shared-users=4`, 500 concurrent *sessions* is as few as 125 vouchers.

**The `on-login` script is deliberately not ported.** The live `7-Days` profile
carries an `on-login` script performing voucher accounting by parsing the user's
`comment` field. NetGuard already does voucher lifecycle through the API, and
duplicating that logic in RouterOS script — in a generated file, on 100+ sites —
means two implementations of the same rules drifting apart. New sites get bare
profiles; NetGuard manages them.

### 8. Captive portal: walled garden

Unauthenticated access is permitted only to what a customer needs before paying:
the portal itself and the OS captive-portal probe endpoints (so detection
fires). Everything else requires a voucher. **The NTP entry this section
originally listed was deliberately removed:** the router is the hotspot's NTP
source and the walled garden governs client traffic, so an entry for an
upstream time host bought nothing and widened the pre-payment surface.

Payment-provider hosts are a placeholder list to be filled in once the provider is known — named explicitly
in the script as a thing to complete rather than left silently empty.

### 9. Firewall and hardening

Ordered, with `place-before` used so ordering is explicit rather than
positional-by-accident:

1. Accept established/related/untracked.
2. Drop invalid.
3. Accept input from `10.13.13.0/24` **scoped to `in-interface=wireguard-netguard`**
   — the NetGuard tunnel. Not source address alone: that would accept a
   `10.13.13.x` source spoofed from the WAN or the LAN, and skip the DNS drops
   below.
4. Accept udp/13231 on `ether1` — the WireGuard port itself. Without it the
   tunnel survives the WAN drop only while conntrack holds the flow (30s udp
   timeout against a 25s keepalive, a 5s margin), so a lapsed keepalive would
   leave ~25s in which a server-initiated packet is dropped.
5. Accept ICMP.
6. Drop DNS (udp/tcp 53) arriving on `ether1` — `allow-remote-requests=yes`
   would otherwise make the router an open resolver for reflection attacks.
7. Drop everything else in `input` from `ether1`.
8. In the **forward** chain: drop `connection-state=new` arriving on `ether1`.
   The input rules protect the router, not the LAN; without this an upstream
   that can route to the LAN subnet reaches customers' devices.

Rules 3, 4 and 8 are placed above the router's own first matching rule, not
above ours, because a factory-default config's `drop all not coming from LAN`
and its forward-chain accepts would otherwise take effect first. Nothing claims
an absolute index: `move ... destination=0` fails on a stock router with
fasttrack (`failure: cannot move builtin`).

**The client bridge joins the stock `LAN` interface list.** `drop all not
coming from LAN` matches `in-interface-list=!LAN`, and defconf's `LAN` list
holds exactly one member: the bridge named `bridge`. Since this script creates
`bridge-hotspot` and moves every customer port onto it, without that join the
rule drops every client packet — no DHCP lease, no DNS, no captive portal —
after the script reports success. The join is guarded on the list existing, so
a blank router is left alone. Chosen over an accept rule for
`in-interface=bridge-hotspot` above the stock drop: it is where RouterOS
expects that fact recorded, it fixes every LAN-keyed rule rather than one, and
it keeps both `drop invalid` rules in force for client traffic, which an accept
placed above the stock drop would skip (the first terminal input rule on
defconf is `drop invalid`, which is what the place-before selector targets).

Plus: `/ip service` — disable `telnet`, `ftp`, `www-ssl`, `api-ssl`; restrict
`ssh` to `10.13.13.0/24`; pin `api` to `10.13.13.0/24`. **`winbox` is pinned to
`10.13.13.0/24,10.15.0.0/24`** — the operator range as well as the tunnel. That
range lies outside the DHCP pool, so hotspot clients cannot be leased into it,
and it is the way back in when the tunnel is dead. It works only because
`bridge-hotspot` is in the `LAN` list; otherwise WinBox from `10.15.0.5` is
dropped along with everything else.

**`www` does NOT serve the hotspot login page.** This spec originally said it
did; the experiment disproved it. With `www` disabled the hotspot still
redirects clients to its own ports (64872-64875), verified on a CHR. `www` is
therefore kept only for the operator range (`/ip service set www
address=10.15.0.0/24`), not because the portal needs it.

Also: `/ip neighbor discovery-settings set discover-interface-list=none`,
`/tool mac-server set allowed-interface-list=none`,
`/tool mac-server mac-winbox set allowed-interface-list=none`,
`/ip cloud set ddns-enabled=no`.

### 10. NetGuard API user

A dedicated user with a generated password, restricted to the tunnel:

```
/user group add name=netguard policy=api,read,write,test,winbox,!local,!telnet,!ssh,!ftp,!reboot,!policy,!password,!sniff,!sensitive,!romon
/user add name=netguard group=netguard address=10.13.13.0/24 password="<generated>" comment="NetGuard API"
```

Not `admin`: the API credential is stored in NetGuard's database, so it should
be least-privilege and source-restricted. `!sensitive` matters — it prevents
that account reading other stored credentials.

The generated password is returned by the endpoint alongside the script so
NetGuard can store it on the device record, and is **printed once** by the
script for the installer's records.

### 11. WireGuard

Exactly the existing convention, so NetGuard's monitoring keeps working
unchanged: interface `wireguard-netguard`, `listen-port=13231`, `mtu=1420`,
peer `10.13.13.1`, endpoint from `WG_SERVER_ENDPOINT`, `persistent-keepalive=25s`,
and a `/32` route to the server.

One change: the peer's `allowed-address` narrows from `0.0.0.0/0` to
`10.13.13.0/24`. The router only ever needs to reach the NetGuard server over
this tunnel; `0.0.0.0/0` permits the peer to source traffic claiming any
address.

### 12. CAPsMAN for the site's access points

The controller, in **local forwarding** mode:

```
/interface wifi capsman set enabled=yes \
    package-path="" upgrade-policy=suggest-same-version \
    ca-certificate=auto certificate=auto
```

- **Local forwarding, and on this stack it is the only option.** In the legacy
  `/caps-man` stack a controller could be put in manager-forwarding mode, where
  every client's traffic tunnels through it — a 2-core ARM router would collapse
  under 100 APs. The new `/interface wifi` (wifi-qcom) stack supports *only*
  local forwarding: APs bridge traffic themselves and the controller carries
  control messages alone. So the thing that makes 100+ APs viable is inherent
  here rather than something the script enables, and the script must not be
  "improved" later by porting it back to `/caps-man`. CAPsMAN has no documented
  limit on CAP count; the controller's CPU and RAM are the limit.
- Provisioning rules match any CAP and apply one configuration, so an installer
  plugs an AP in and it joins with no per-AP work — the only tractable approach
  at 100+ units.
- Datapath puts CAP clients on `bridge-hotspot`, so they land in the hotspot and
  DHCP exactly like wired clients.
- `/interface wifi` (wifi-qcom) is used rather than the legacy
  `/caps-man`, since RouterOS 7.25 on this hardware uses the new stack and
  WiFiWave2 devices support local forwarding only.

Note for the installer: APs must be set to CAP mode to be adopted. That is a
per-AP action on first boot and cannot be done from the controller.

### 13. Closing summary

The script's last act is to print a block the installer can photograph: board,
RouterOS version, license level and its user ceiling, LAN subnet and gateway,
DHCP range, hotspot profile names, the API username, the WireGuard tunnel IP,
and any preflight warning that was non-fatal.

It does **not** print the generated API password. The NetGuard UI shows it once,
and a script pasted into a terminal can be scrolled back or logged by anyone
standing at the counter — so the password stays in one place rather than two.

## Interfaces

```
POST /api/v1/inventory/devices/{device_id}/provision-script
    ?site_slug=<str>&timezone=<str>
->  { "device_id": "<uuid>", "site_slug": "<str>", "script": "<RouterOS CLI>",
      "api_username": "netguard", "api_password": "<generated>",
      "admin_password": "<generated>", "warnings": ["..."] }
```

**POST, not GET** (a GET returns 405, and a test asserts it). Every call
ROTATES the router's credentials: it mints a fresh `netguard` API password and a
fresh `admin` password and returns a script that sets both, so the call is not
safe to repeat idly and any script handed out earlier stops being valid.
Restricted to `SUPER_ADMIN` and `ORG_ADMIN` users (403 otherwise) and to devices
in the caller's own organisation (404 otherwise), because the response carries
secrets and the embedded tunnel key. Returns 409 if the device has no WireGuard
tunnel yet, naming `POST .../provision-wireguard` as the remedy; that sibling
endpoint is gated on the same roles, since it returns the same tunnel private
key.

**`admin_password` is a second secret, and this spec never mentioned it.** The
script rotates the router's own `admin` account away from the factory blank
password and hands the customer that new value. It is the break-glass
credential: `admin` is reachable from the LAN, so leaving it blank would be an
open door on a router whose management services are otherwise pinned to the
tunnel. **NetGuard never stores it** — unlike the API password, which is
persisted on the device record — and the script never prints it. The response
body is the only place it exists, which makes the NetGuard UI the only place a
customer can read it. If it is lost, the way back in is WinBox from the operator
range, or a factory reset.

`site_slug` names the router identity and the CAPsMAN SSID. `timezone` defaults
to `Africa/Banjul`. The endpoint stores the generated API password on the device
record, so the caller does not have to.

## Error handling

The script's failure model is *refuse early, loudly*. There is no rollback: on a
greenfield router, a half-applied config is recovered by a factory reset, which
is faster and more predictable than a scripted undo. Preflight therefore does
all the refusing, before anything is written.

Backend-side: the endpoint raises rather than emitting a script with a
placeholder in it. The existing generator's habit of substituting
`SERVER_PUBLIC_KEY_PLACEHOLDER` and continuing is the failure mode to avoid —
a script that looks complete and silently cannot connect.

## Testing

RouterOS config cannot be unit-tested, and there is no spare router. Three
layers instead:

1. **Golden-file tests of the generator.** Given a fixed device record, the
   emitted script matches a committed expected output byte for byte. This is
   what catches an accidental change to a firewall rule's order or a dropped
   `comment=`.
2. **Assertions on invariants** rather than only on the whole file: the API
   service is never `0.0.0.0/0`; no secret appears twice; `10.15.0.1` is outside
   the DHCP pool; the WireGuard subnet and the LAN subnet do not overlap; NTP
   is configured before the hotspot section.

   **The invariant "every created object carries `comment="NetGuard"`" is no
   longer true, and the test enforcing it had to be narrowed.** RouterOS 7.16
   has no `comment` property on `/ip hotspot`, `/ip hotspot profile` or
   `/ip hotspot user profile` and rejects it there, so the hotspot, its profile
   and all four user profiles (`default`, `1-Hour`, `24-Hours`, `7-Days`) are
   deliberately untagged. Five of those are objects the script CREATES (the
   test counts exactly five exemptions); `default` ships with RouterOS and is
   only `set`. What is enforced instead: every object that CAN carry the tag
   does, and each exemption is named and must carry a `name=` so it stays
   identifiable. The tag is load-bearing where it survives:
   preflight refuses a `wireguard-netguard` whose comment is not one NetGuard
   writes, which is why `wireguard.py` and `sections.py` must agree on it.
3. **A CHR smoke test — confirmed feasible.** `/dev/kvm` is present on this VPS
   and 4 CPUs report `vmx`/`svm`, so MikroTik's Cloud Hosted Router (free below
   1 Mbit/s) can run in a local VM and the script can be applied end to end
   before it ever touches a real router. `qemu` is not installed yet and would
   need adding.

   What this layer catches that golden files cannot: a command RouterOS rejects.
   A generated script can be byte-perfect against an expectation that was itself
   wrong — the expectation is written by the same person as the generator. Only
   a real RouterOS parser settles whether `/interface wifi capsman set ...` is
   valid on 7.25. It also exercises preflight's refusals, since a CHR is a
   greenfield router by definition.

   Limits to be honest about: a CHR has no wireless hardware, so the CAPsMAN
   controller can be configured and its rules verified but no AP will ever
   adopt; and a CHR is Level 0/P-Unlimited rather than Level 5, so the license
   ceiling logic needs its own unit test rather than relying on the VM.

## Not in this spec

- Re-configuring or migrating the two live routers. Greenfield only.
- Moving the hotspot gateway to a cloud CHR, which is the answer beyond ~500
  concurrent users per site.
- A trusted TLS certificate for the portal, which needs a domain.
- Porting the `on-login` voucher accounting script.
- Payment-provider walled-garden hosts, pending the provider.
- Per-AP placement, channel planning or site survey for 100+ APs.
