# Captive-Portal Payments (Modem Pay) — Design

**Status:** design, pending approval to build
**Date:** 2026-10-04

## Goal

Let a hotspot customer buy WiFi access from the captive portal with mobile
money or a card, through Modem Pay, and be logged in automatically — with the
only change the site owner makes to their router being a single "Buy WiFi"
button. Money goes straight to the owner's own Modem Pay account; NetGuard
never holds funds.

## The one-line summary of how it works

```
Buy WiFi (button on the captive portal)
  → NetGuard /buy page (reads this router's existing profile prices)
  → Modem Pay hosted checkout, using THIS ORG's Modem Pay key
  → customer pays (Wave / QMoney / card)
  → Modem Pay webhook → NetGuard verifies signature AND re-checks the amount
  → NetGuard generates a voucher the normal way and creates it on the router
  → customer logs in with the code (username-only), time runs on limit-uptime
```

## Decisions (locked)

- **Money flow:** each **organisation** supplies its own Modem Pay secret key
  and webhook secret. Payments route directly to that org's Modem Pay account.
  NetGuard holds no money and does no settlement. (If this should be per-user
  instead of per-org, it is a one-word change to where the columns live.)
- **Prices:** read from the router's existing `Device.voucher_template.profile_pricing`
  (`{ "<profile>": {"price": N, "currency": "GMD"} }`), set today on the hotspot
  management page. No new pricing config. Prices are therefore already per-router.
- **Plans:** the existing profiles — `3-Hours`, `24-Hours`, `7-Days`, `30-Days`.
- **Login method: UNCHANGED.** Username-only. Reuse the existing voucher
  generator (`backend/app/services/voucher_jobs.generate_candidate`, random
  mode, where `password == username`) so a customer types one code. Reuse the
  existing router user-creation path.
- **Time model:** `limit-uptime=<plan duration>` on the generated user — a usage
  budget that pauses when the device disconnects and resumes on reconnect, until
  spent. `shared-users=1` (already set) keeps it one device at a time.
  `add-mac-cookie=yes` (already set) makes reconnect seamless without re-typing.
  All four plans are usage-based to start; calendar-expiry for 7d/30d is a
  documented later addition (NetGuard holds the expiry, the monitor agent removes
  expired users).
- **No hard MAC binding.** The code is the identity; randomized phone MACs make a
  hard MAC lock fragile. mac-cookie is a convenience layer only.
- **Mini-browser handling:** the /buy page detects the captive popup (iOS CNA /
  Android captive login) and offers a one-tap "open in your browser to pay"
  escape, because the popup will not hand off to the Wave/QMoney app. After
  payment the customer is logged in by the code, so they never need to navigate
  back to the portal.

## Security requirements (every one is a task's test)

1. **Secret keys are encrypted at rest** — reuse `app.utils.encryption`
   (Fernet, the same as router passwords). They are never returned in any API
   response in plaintext (write-only fields; reads return a masked/boolean
   "configured" state).
2. **Webhook signature is verified** — HMAC-SHA512 over the raw request body
   using the org's webhook secret, compared with `hmac.compare_digest` (timing
   safe), against the `x-modem-signature` header. An unsigned or wrong-signature
   webhook is rejected `400` and does nothing.
3. **The amount is re-checked server-side** — the webhook maps the metadata's
   plan to the price in `profile_pricing` and confirms the paid amount matches.
   Metadata is never trusted to say how much was paid or what plan to grant.
4. **Idempotent on the Modem Pay charge id** — a replayed or duplicated webhook
   for a charge already fulfilled grants nothing more. One charge, one voucher.
5. **The /buy and webhook endpoints are public (unauthenticated)** — they take
   no NetGuard credentials. `router` + `mac` in the /buy URL are attacker-
   controllable and are treated as untrusted; the webhook signature is the only
   trust anchor for "paid".
6. **Payments are off until configured** — `payments_enabled` defaults false;
   /buy returns a clear "not available" state for a router whose org has no keys.

## Data model change (NEEDS DB-MIGRATION APPROVAL)

Alembic migration, additive only, adding to `organizations`:

| Column | Type | |
|---|---|---|
| `modempay_secret_key` | Text, nullable | encrypted |
| `modempay_webhook_secret` | Text, nullable | encrypted |
| `payments_enabled` | Boolean, default false, not null | |

All nullable/defaulted; existing rows untouched. `alembic upgrade head` already
runs on backend startup. Plus a `payment_intents` ledger table (new) to track
charge ids for idempotency and reconciliation:

| Column | Type | |
|---|---|---|
| `id` | UUID pk | |
| `device_id` | UUID fk → devices | |
| `charge_id` | Text, unique | Modem Pay charge id; the idempotency key |
| `plan` | Text | profile name |
| `amount` | BigInteger | minor units, as paid |
| `currency` | Text | |
| `status` | Text | created / paid / fulfilled / failed |
| `voucher_username` | Text, nullable | the code granted on fulfilment |
| `customer_mac` | Text, nullable | |
| `created_at` / `updated_at` | timestamps | |

## Reuse (what is NOT new code)

- Voucher code generation: `voucher_jobs.generate_candidate`.
- Creating the user on the router: the existing `/ip/hotspot/user` add path in
  `hotspot.py` (and the RouterOS API pool).
- Recording the sale: the existing `hotspot_sales` / sale-recording path.
- Encryption: `app.utils.encryption`.
- Prices: `Device.voucher_template.profile_pricing`.

## Router-side change

- **Walled-garden** entries for Modem Pay's checkout domain(s) and NetGuard's
  /buy host, so the pages load before login. (In the provisioning script.)
- **The Buy button** is one line of HTML that must live INSIDE the router's
  hotspot login page, because `$(mac)`/`$(ip)` are only substituted there:
  `<a href="https://app.netguard.fun/buy?router=<device-id>&mac=$(mac)&ip=$(ip)">Buy WiFi</a>`
  - **Default NetGuard portal:** the login page is ours, so the button is added
    automatically with the router id pre-filled (login.html uploaded via the
    router API after provisioning, or written by the setup flow).
  - **Custom portal (owner's own login page):** we do NOT auto-edit their
    arbitrary HTML. NetGuard shows a per-router copy-paste snippet (id pre-filled)
    in the dashboard for the owner to drop into their page. This is the standard
    model and the reliable one.
- No change to `login-by`, `shared-users`, mac-cookie, or profiles.

## Out of scope (first version)

- Split payments / sub-accounts (not needed: per-org keys).
- Calendar-expiry plans (documented as a later addition).
- Refunds, receipts by SMS/email, coupons.

## Acceptance test (only real hardware can prove it)

A real iPhone and a real Android, on a live router, each completing a **card**
payment and a **Wave/QMoney** payment, getting online, disconnecting, and
reconnecting with time intact. A CHR cannot test this; it is the final gate.

## Open item

- Confirm keys live on the **organisation** (assumed) vs the user.
