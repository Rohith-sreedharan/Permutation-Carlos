# Chargeback Handling Protocol — BeatVegas

**Event:** `charge.dispute.created`  
**Handler:** `backend/routes/phase3_webhook_routes.py` — `_handle_charge_dispute_created()`  
**Sentinel event:** `CHARGEBACK_INITIATED` (alert threshold = 1; any single dispute triggers immediate alert)

---

## Protocol Steps (in order, all atomic within the handler)

### Step 1 — Immediate Entitlement Suspension
On `charge.dispute.created`, the user's entitlement record is suspended immediately.  
- `user_entitlements.active` → `False`
- `user_entitlements.revoke_reason` → `"CHARGEBACK_DISPUTE"`
- `user_entitlements.dispute_id` → Stripe dispute ID
- `user_entitlements.revoked_at` → UTC timestamp

This is a **suspension**, not a deletion. The user record and all data are retained pending dispute resolution.

### Step 2 — Session Invalidation
All active sessions for the user are invalidated:
- `user_sessions.revoked` → `True`
- `user_sessions.revoke_reason` → `"CHARGEBACK_DISPUTE"`

### Step 3 — Sentinel Alert
`CHARGEBACK_INITIATED` is written to `sentinel_event_log`.  
The integrity sentinel monitors this with threshold=1 (any single dispute fires an alert).  
Alert is immediate — no aggregation window.

### Step 4 — Billing State Change Log
The event is logged to `billing_state_change_log` via `billing_ledger.log_state_change()` with:
- `event_type: "CHARGEBACK_INITIATED"`
- `dispute_id`, `charge_id`, `amount_usd`

---

## Reinstatement (Manual Process)

Disputes won by BeatVegas (Stripe `charge.dispute.closed` with `status: "won"`):
1. Set `user_entitlements.active = True`, clear `revoke_reason`
2. Log `CHARGEBACK_RESOLVED_WON` to `billing_state_change_log`
3. Log to sentinel_event_log

Disputes lost or refunded:
1. Entitlement remains suspended
2. Log `CHARGEBACK_RESOLVED_LOST` to `billing_state_change_log`

> **Future work:** Add `charge.dispute.closed` handler to automate reinstatement.

---

## What Is NOT Done (by design)

- User data is **not deleted** on dispute — suspension only
- Entitlement is **not immediately deleted** — it is set to inactive with an audit trail
- No automated refund processing — Stripe handles this independently
- No email sent on dispute — legal review required before communicating disputes

---

## Relevant Code

| File | Symbol | Purpose |
|------|--------|---------|
| `backend/routes/phase3_webhook_routes.py` | `_handle_charge_dispute_created()` | Event handler |
| `backend/services/billing_ledger_service.py` | `billing_ledger.log_state_change()` | Audit log |
| `backend/services/integrity_sentinel.py` | `billing_write_fail_rate` monitor | Sentinel alert |
| `backend/services/entitlement_gate.py` | `require_active_subscription()` | Enforces suspended state |
