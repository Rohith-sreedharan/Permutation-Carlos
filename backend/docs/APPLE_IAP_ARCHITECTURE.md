# Apple IAP Architecture — BeatVegas

**Status:** Architecture documented. Apple Sign In for web is live. iOS IAP routing ready for app store submission.

---

## Apple Sign In — Web (Live)

**Route:** `POST /api/auth/apple`  
**File:** `backend/routes/auth_routes.py` (lines 298–345)  
**Phase:** Phase 2A.2

### Flow
1. iOS/web client receives `identity_token` from Apple's authentication services
2. Backend receives `{ identity_token, first_name?, last_name?, email? }`
3. Backend fetches Apple's public keys from `https://appleid.apple.com/auth/keys`
4. Decodes and verifies the JWT: `aud == APPLE_CLIENT_ID`, `iss == "https://appleid.apple.com"`, `exp` not elapsed
5. Extracts `sub` (Apple's stable user identifier), canonicalises email
6. Upserts user record in MongoDB `users` collection with `apple_sub` field
7. Issues BeatVegas JWT (same format as email/password login)

### Required Environment Variables
| Variable | Description |
|---|---|
| `APPLE_CLIENT_ID` | Bundle ID / Services ID registered with Apple (e.g. `app.beatvegas.web`) |

### Entitlement on First Sign-In
New Apple Sign In users are provisioned with an `intelligence_preview` entitlement record (tier: Intelligence Preview, active: true, expires_at: null).

---

## iOS App — In-App Purchase (IAP) Routing Architecture

> Not yet live. Architecture defined here for iOS App Store submission readiness.

### Subscription Products (Mirrors Stripe)

| Product ID | Tier | Price |
|---|---|---|
| `com.beatvegas.syndicate.monthly` | Syndicate | $39.00/month |
| `com.beatvegas.platform.monthly` | Platform | $97.00/month |

### IAP → Backend Flow

```
iOS App
  │
  ├─ User selects subscription
  │
  ├─ StoreKit 2: Product.purchase()
  │
  ├─ Apple returns Transaction (signed JWS)
  │
  └─ POST /api/iap/apple/verify
       { receipt_data: "<base64_receipt>" | jws_transaction: "<JWS>" }

Backend (future route: /api/iap/apple/verify)
  │
  ├─ Verify receipt with Apple App Store Server API
  │    URL: https://buy.itunes.apple.com/verifyReceipt (prod)
  │         https://sandbox.itunes.apple.com/verifyReceipt (sandbox)
  │
  ├─ Extract product_id and original_transaction_id
  │
  ├─ Map product_id → tier:
  │    com.beatvegas.syndicate.monthly → syndicate
  │    com.beatvegas.platform.monthly  → platform
  │
  ├─ Write to billing_ledger (PENDING → SETTLED) via billing_ledger_service.py
  │
  ├─ Upsert user_entitlements record (tier, active=True, expires_at)
  │
  ├─ Log SUBSCRIPTION_ACTIVATED to billing_state_change_log
  │
  └─ Return { status: "ok", tier: "<tier>", expires_at: "<iso>" }
```

### App Store Server Notifications (Future Webhook)

Apple pushes renewal/cancellation events to:  
`POST /api/webhooks/apple/iap` (future route)

Events to handle:
| Notification Type | Action |
|---|---|
| `DID_RENEW` | Extend `expires_at` by 30 days, log SUBSCRIPTION_RENEWED |
| `EXPIRED` | Set `active=False`, log SUBSCRIPTION_EXPIRED, invalidate sessions |
| `DID_CHANGE_RENEWAL_STATUS` (disable) | Log CANCELLATION_PENDING |
| `REFUND` | Suspend entitlement, log CHARGEBACK_INITIATED (same as Stripe dispute flow) |

### Idempotency
All IAP verifications use `original_transaction_id` as the idempotency key — identical to the `stripe_event_id` pattern in `phase3_webhook_routes.py`.

### Entitlement Source of Truth
Both Stripe (web) and Apple IAP (iOS) write to the same `user_entitlements` collection. The `payment_provider` field distinguishes the source:
- `"stripe"` — web subscriptions
- `"apple_iap"` — iOS in-app purchases

### Submission Requirements Checklist
- [ ] Register Subscription products in App Store Connect
- [ ] Set `APPLE_SHARED_SECRET` env var (for receipt validation)
- [ ] Set App Store Server Notifications URL to `/api/webhooks/apple/iap`
- [ ] Implement `POST /api/iap/apple/verify` route (mirrors phase3_webhook_routes.py pattern)
- [ ] Implement `POST /api/webhooks/apple/iap` route
- [ ] Test sandbox receipts end-to-end before submission
