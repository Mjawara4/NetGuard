# Captive-Portal Payments Acceptance

This is the release gate for Modem Pay captive-portal payments. Complete the
sandbox section before enabling live credentials.

Migration approval: **approved by the project owner on 2026-10-05** for
`backend/alembic/versions/0010_portal_payments.py`. This records approval for
the migration to accompany a future deployment; it does not record that the
migration has already been applied to production.

## Automated evidence

- Backend payment tests: signature rejection, replay idempotency, amount
  mismatch, encrypted credential storage, disabled/unconfigured routers, and
  server-owned pricing.
- Frontend tests: write-only credentials, plan rendering, payment request, and
  unavailable state.
- Router provisioning: focused unit/golden suite and RouterOS 7.16.2 CHR import.

## Sandbox end-to-end

Status: **pending sandbox credentials**.

1. Configure an organisation with `sk_test_...` and its sandbox webhook secret,
   then enable payments.
2. Configure prices for all intended profiles on one CHR or test router.
3. Open `/buy?router=<device UUID>&mac=<test MAC>` and confirm the displayed
   plans and prices exactly match the router's server-side `profile_pricing`.
4. Complete one hosted sandbox checkout.
5. Forward or simulate `charge.succeeded` with the Modem Pay CLI against
   `/api/v1/payments/webhook`.
6. Confirm exactly one RouterOS hotspot user exists with:
   - password equal to username;
   - the purchased profile;
   - the profile's matching `limit-uptime`;
   - a comment containing the Modem Pay charge ID.
7. Confirm one `hotspot_sales` row and one fulfilled `payment_intents` row were
   recorded with the same voucher username.
8. Replay the identical signed event. Confirm no second user or sale is created.
9. Send the event with an invalid signature and with a mismatched amount.
   Confirm both return `400` and create no router user or database write.

Record the date, operator, sandbox charge ID, router ID, and pass/fail notes here:

| Date | Operator | Charge | Router | Result | Notes |
|---|---|---|---|---|---|
| pending | pending | pending | pending | Not run | Sandbox credentials required |

## Real-device release gate

Status: **pending sandbox pass and physical devices**.

Run on a live router only after the sandbox section passes. Test each combination:

| Device | Payment method | Gets online | Disconnect/reconnect | Time preserved | Result |
|---|---|---:|---:|---:|---|
| iPhone | Card | pending | pending | pending | Not run |
| iPhone | Wave or QMoney | pending | pending | pending | Not run |
| Android | Card | pending | pending | pending | Not run |
| Android | Wave or QMoney | pending | pending | pending | Not run |

For every row, confirm the captive popup offers the full browser URL, hosted
checkout opens in the normal browser/payment app, the voucher logs in with one
code, and consumed `limit-uptime` resumes rather than resets after reconnect.
