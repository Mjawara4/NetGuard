# Captive-Portal Payments (Modem Pay) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let a hotspot customer buy WiFi from the captive portal via Modem Pay and be logged in automatically, with each organisation using its own Modem Pay account.

**Architecture:** A public `/buy` page reads a router's existing profile prices, creates a Modem Pay hosted-checkout payment with that org's key, and a signature-verified webhook generates a voucher (reusing the existing generator) and creates it on the router. Money routes directly to the org; NetGuard holds none.

**Tech Stack:** FastAPI, async SQLAlchemy, Alembic, Fernet encryption, Modem Pay REST API (HMAC-SHA512 webhooks), React/Vite frontend, RouterOS API.

**Spec:** `docs/superpowers/specs/2026-10-04-portal-payments-design.md`

## Global Constraints

- Secret keys encrypted at rest with `app.utils.encryption` (Fernet); never returned in plaintext by any endpoint.
- Webhook trust is the **only** trust anchor for "paid": HMAC-SHA512 over the raw body, `hmac.compare_digest`, `x-modem-signature` header.
- The amount and plan granted are decided server-side from `profile_pricing`, never from webhook metadata.
- Idempotent on the Modem Pay `charge_id`: one charge grants exactly one voucher.
- Login method unchanged: username-only, reuse `voucher_jobs.generate_candidate` (random mode, `password == username`).
- Time via `limit-uptime`; `shared-users=1` and `add-mac-cookie=yes` already set; do not change `login-by` or profiles.
- Build and verify each stage against the Modem Pay **sandbox**; nothing real until the final acceptance test.
- Never `git add -A`; stage named paths only (node_modules/dist are tracked).

## Review Focus

- **Replayed webhook** for an already-fulfilled charge → grants nothing (idempotency on `charge_id`). Test in Task 5.
- **Wrong/absent signature** on a webhook → `400`, no voucher, no DB write. Test in Task 3 and Task 5.
- **Amount mismatch** (metadata claims a plan whose price ≠ amount paid) → rejected, no voucher. Test in Task 5.
- **Reading an org's keys back** via the settings API → returns "configured: true/false", never the plaintext key. Test in Task 2.
- **/buy for a router whose org has no keys or payments disabled** → clear "not available", no payment created. Test in Task 4.

---

### Task 1: Schema — org credential columns + payment_intents ledger

**Files:**
- Modify: `backend/app/models/core.py` (Organization: add columns; new PaymentIntent model)
- Create: `backend/alembic/versions/<rev>_portal_payments.py`
- Test: `backend/tests/test_payment_schema.py`

**Interfaces:**
- Produces: `Organization.modempay_secret_key: str|None`, `.modempay_webhook_secret: str|None`, `.payments_enabled: bool`; `PaymentIntent(id, device_id, charge_id[unique], plan, amount, currency, status, voucher_username, customer_mac, created_at, updated_at)`.

- [ ] **Step 1: Write the failing test** — model has the fields; `charge_id` is unique.

```python
# test_payment_schema.py
from app.models.core import Organization, PaymentIntent
def test_org_has_payment_columns():
    cols = Organization.__table__.columns
    assert "modempay_secret_key" in cols and "modempay_webhook_secret" in cols
    assert cols["payments_enabled"].default.arg is False
def test_payment_intent_charge_id_is_unique():
    assert PaymentIntent.__table__.columns["charge_id"].unique
```

- [ ] **Step 2: Run, verify fail** (`ImportError: PaymentIntent`).
- [ ] **Step 3: Add the columns and model** in `core.py` (nullable text for the two secrets, `Boolean default=False nullable=False` for `payments_enabled`; PaymentIntent per the spec table).
- [ ] **Step 4: Generate the migration**: `docker run ... alembic revision --autogenerate -m "portal payments"`; hand-verify it only ADDs columns/table (no drops/alters of existing data).
- [ ] **Step 5: Show the migration SQL to the human partner and get explicit approval before it can reach the live DB.** (Standing rule.)
- [ ] **Step 6: Run tests, commit** (`feat(payments): schema for per-org keys and the intent ledger`).

### Task 2: Per-org Modem Pay credentials — storage, API, settings UI

**Files:**
- Create: `backend/app/routers/payments_settings.py`
- Modify: `backend/app/main.py` (register router)
- Create: `frontend/src/pages/PaymentSettings.jsx` (or a section on an existing settings page)
- Test: `backend/tests/test_payment_settings.py`

**Interfaces:**
- Produces: `PUT /api/v1/payments/settings` (org admin only) `{modempay_secret_key?, modempay_webhook_secret?, payments_enabled?}`; `GET /api/v1/payments/settings` → `{configured: bool, payments_enabled: bool}` (never the key).

- [ ] **Step 1: Write failing tests** — PUT stores encrypted (ciphertext != plaintext in the row); GET never returns the key; non-admin gets 403.

```python
async def test_secret_is_stored_encrypted_and_never_returned():
    org = Organization(name="o")
    resp = await put_settings({"modempay_secret_key": "sk_test_ABC"}, org, admin)
    assert org.modempay_secret_key != "sk_test_ABC"            # encrypted at rest
    got = await get_settings(org, admin)
    assert "sk_test_ABC" not in str(got) and got["configured"] is True
async def test_non_admin_cannot_set_keys():
    with pytest.raises(HTTPException) as e:
        await put_settings({"modempay_secret_key": "x"}, org, viewer)
    assert e.value.status_code == 403
```

- [ ] **Step 2–4:** fail → implement (encrypt with `encrypt_value` on write; GET computes `configured = bool(secret)`; gate to `SUPER_ADMIN`/`ORG_ADMIN`) → pass.
- [ ] **Step 5:** Settings screen: two write-only password fields (show "configured" if set, never the value), an enable toggle, Save. Frontend test: saving posts the fields; the key is never rendered back.
- [ ] **Step 6: Commit** (`feat(payments): per-org Modem Pay credential settings`).

### Task 3: Modem Pay client — create intent + verify webhook signature

**Files:**
- Create: `backend/app/services/modempay.py`
- Test: `backend/tests/test_modempay_client.py`

**Interfaces:**
- Produces: `create_payment_intent(secret_key, amount, currency, metadata, return_url, cancel_url) -> {payment_link, charge_id?}` (HTTP to Modem Pay); `verify_webhook(raw_body: bytes, signature: str, webhook_secret: str) -> bool`.

- [ ] **Step 1: Write failing test for signature verification** (no network needed — it's just HMAC).

```python
import hmac, hashlib
from app.services.modempay import verify_webhook
def _sign(body, secret): return hmac.new(secret.encode(), body, hashlib.sha512).hexdigest()
def test_valid_signature_accepted():
    body = b'{"event":"charge.succeeded"}'
    assert verify_webhook(body, _sign(body, "whsec"), "whsec") is True
def test_tampered_body_rejected():
    body = b'{"event":"charge.succeeded"}'
    assert verify_webhook(b'{"event":"evil"}', _sign(body, "whsec"), "whsec") is False
def test_wrong_secret_rejected():
    body = b'{"x":1}'
    assert verify_webhook(body, _sign(body, "whsec"), "other") is False
```

- [ ] **Step 2–4:** fail → implement `verify_webhook` with `hmac.compare_digest` over HMAC-SHA512; implement `create_payment_intent` with `httpx` (mock HTTP in tests) → pass.
- [ ] **Step 5: Commit** (`feat(payments): modem pay client and webhook verification`).

### Task 4: Public /buy page + create-payment endpoint

**Files:**
- Create: `backend/app/routers/buy.py` (public router, no auth)
- Create: `frontend/src/pages/Buy.jsx` + route (public)
- Modify: `backend/app/main.py`
- Test: `backend/tests/test_buy_endpoint.py`

**Interfaces:**
- Produces: `GET /api/v1/buy/plans?router=<device_id>` → `{enabled, plans:[{profile, price, currency}]}` from `voucher_template.profile_pricing`; `POST /api/v1/buy/pay` `{router, mac, plan}` → `{checkout_url}` (creates a PaymentIntent row `status=created` and a Modem Pay intent with metadata `{device_id, mac, plan}`).

- [ ] **Step 1: Write failing tests** — plans come from `profile_pricing`; a router whose org has no keys or `payments_enabled=false` returns `enabled:false` and `/pay` refuses.

```python
async def test_plans_come_from_profile_pricing():
    dev.voucher_template = {"profile_pricing": {"3-Hours": {"price": 10, "currency": "GMD"}}}
    out = await get_plans(router=dev.id)
    assert {"profile": "3-Hours", "price": 10, "currency": "GMD"} in out["plans"]
async def test_pay_refused_when_payments_disabled():
    org.payments_enabled = False
    with pytest.raises(HTTPException) as e:
        await pay({"router": dev.id, "mac": "AA:BB", "plan": "3-Hours"})
    assert e.value.status_code in (403, 409)
```

- [ ] **Step 2–4:** fail → implement (resolve device→org, read prices, create intent via Task 3, persist PaymentIntent) → pass.
- [ ] **Step 5: Buy.jsx** — lists plans with prices; "Buy" posts and redirects to `checkout_url`; detects captive popup (`navigator` heuristics / known CNA markers) and shows "Open in your browser to pay" with the full URL. Frontend test: renders plans, Buy triggers POST then redirect.
- [ ] **Step 6: Commit** (`feat(payments): public buy page and payment creation`).

### Task 5: Webhook — verify, re-check amount, idempotent, fulfil

**Files:**
- Create: `backend/app/routers/payment_webhook.py` (public)
- Modify: `backend/app/main.py`
- Test: `backend/tests/test_payment_webhook.py`

**Interfaces:**
- Consumes: `verify_webhook` (Task 3), `generate_candidate` (`app.services.voucher_jobs`), the router user-add path (`hotspot.py`), `profile_pricing`, PaymentIntent (Task 1).
- Produces: `POST /api/v1/payments/webhook` → on a verified `charge.succeeded`: re-check amount vs price, if intent not already `fulfilled` generate a voucher and create the hotspot user on the router (`limit-uptime=<plan>`, profile=plan), record the sale, set intent `fulfilled` + `voucher_username`.

- [ ] **Step 1: Write failing tests** — the Review-Focus trio.

```python
async def test_unsigned_webhook_rejected_and_nothing_written():
    r = await webhook(raw=b'{"event":"charge.succeeded"}', signature="bad")
    assert r.status_code == 400 and router_add.call_count == 0
async def test_replayed_charge_grants_once():
    body = signed_charge(charge_id="ch_1", plan="3-Hours", amount=10)
    await webhook(**body); await webhook(**body)      # twice
    assert router_add.call_count == 1                   # one voucher only
async def test_amount_mismatch_rejected():
    body = signed_charge(charge_id="ch_2", plan="3-Hours", amount=1)  # price is 10
    await webhook(**body)
    assert router_add.call_count == 0
```

- [ ] **Step 2–4:** fail → implement (resolve org by the device in the intent/metadata, verify signature with that org's secret, look up PaymentIntent by `charge_id`, re-check `amount == profile_pricing[plan].price`, guard on `status != fulfilled`, generate + create + record, update status) → pass.
- [ ] **Step 5: Commit** (`feat(payments): signed, idempotent, amount-checked fulfilment webhook`).

### Task 6: Router-side — Buy button + walled garden in the provisioning script

**Files:**
- Modify: `backend/app/services/provisioning/sections.py` (walled_garden + the hotspot login page)
- Modify: `backend/tests/fixtures/provision_expected.rsc` (re-record)
- Test: `backend/tests/test_provision_sections_hotspot.py`

**Interfaces:**
- Produces: walled-garden `dst-host` entries for the Modem Pay checkout domain and the NetGuard /buy host; a login-page customisation carrying the Buy link with `$(mac)`/`$(ip)`.

- [ ] **Step 1: Write failing tests** — walled garden includes the Modem Pay + NetGuard hosts; the generated login page contains the buy URL with the MikroTik variables; the `# TODO PAYMENT PROVIDER` line is gone.
- [ ] **Step 2–4:** fail → implement (replace the TODO with real hosts; add the login-page file write with the button) → re-record golden → pass.
- [ ] **Step 5: CHR-verify** the full script still imports clean (`scripts/chr-smoke-test.sh`).
- [ ] **Step 6: Commit** (`feat(payments): buy button and payment walled-garden in the setup script`).

### Task 7: Sandbox end-to-end + real-device acceptance (manual, documented)

**Files:**
- Create: `docs/payments-acceptance.md`

- [ ] **Step 1:** Against the **sandbox**, drive /buy → checkout → simulate the `charge.succeeded` webhook (Modem Pay webhook CLI) → confirm a voucher is created on a CHR/real router and the sale recorded.
- [ ] **Step 2:** Document and then run the **real-device gate**: iPhone + Android, a card and a Wave/QMoney payment, on a live router — online, disconnect, reconnect with time intact. Record results.
- [ ] **Step 3: Commit** the acceptance doc.

---

## Self-Review

- **Spec coverage:** money flow (Task 2), prices (Task 4), login-unchanged/voucher reuse (Task 5), time model (Task 5/6), mini-browser escape (Task 4), router button (Task 6), security reqs 1–6 (Tasks 2/3/5), migration approval (Task 1). Covered.
- **Placeholders:** none — each task names files, interfaces, and test code.
- **Type consistency:** `generate_candidate`, `verify_webhook`, `create_payment_intent`, `PaymentIntent.charge_id` used consistently across tasks.
- **Review Focus:** replay (T5), bad signature (T3/T5), amount mismatch (T5), key read-back (T2), unconfigured router (T4) — each pinned to a task.
