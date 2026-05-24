#!/usr/bin/env python3
"""
PF-2 — Transactional Email Live-Send Test

Sends all 5 required transactional emails to a real inbox via SendGrid.
Requires SENDGRID_API_KEY set in environment before running.

Usage (from project root):
    export SENDGRID_API_KEY=<your_key>
    cd backend && python3 scripts/send_test_emails.py beatvegasapp@gmail.com
"""
from __future__ import annotations

import sys
import os

# Allow running from project root or from backend/
_here = os.path.dirname(os.path.abspath(__file__))
_backend = os.path.dirname(_here)
if _backend not in sys.path:
    sys.path.insert(0, _backend)

TARGET = sys.argv[1] if len(sys.argv) > 1 else "beatvegasapp@gmail.com"
TEST_USER_ID = "pf2_test_live_send"

api_key = os.getenv("SENDGRID_API_KEY", "")
if not api_key:
    print("ERROR: SENDGRID_API_KEY is not set.")
    print("  Run: export SENDGRID_API_KEY=<your_key>  then re-run this script.")
    sys.exit(1)

from db.mongo import db
from services.transactional_email_service import (
    send_subscription_receipt,
    send_payment_failed,
    send_password_reset,
    send_renewal_reminder,
    send_cancellation_confirmation,
)

print(f"Sending 5 transactional emails to: {TARGET}")
print(f"Provider: SendGrid")
print()

# Insert ephemeral test user so _get_user_email() resolves correctly
db["users"].delete_one({"user_id": TEST_USER_ID})
db["users"].insert_one({"user_id": TEST_USER_ID, "email": TARGET})

results: list[tuple[str, bool]] = []

try:
    # 1 — Subscription receipt
    print("[1/5] Subscription receipt ...")
    ok = send_subscription_receipt(
        user_id=TEST_USER_ID,
        amount_usd=97.00,
        tier_name="Platform",
        stripe_invoice_id="in_pf2_test_001",
        next_renewal_date="June 24, 2026",
    )
    results.append(("Subscription receipt", ok))
    print(f"      {'OK' if ok else 'FAILED'}")

    # 2 — Payment failure
    print("[2/5] Payment failure ...")
    ok = send_payment_failed(
        user_id=TEST_USER_ID,
        amount_usd=97.00,
    )
    results.append(("Payment failure", ok))
    print(f"      {'OK' if ok else 'FAILED'}")

    # 3 — Password reset (takes email directly — no DB lookup)
    print("[3/5] Password reset ...")
    ok = send_password_reset(
        user_id=TEST_USER_ID,
        user_email=TARGET,
    )
    results.append(("Password reset", ok))
    print(f"      {'OK' if ok else 'FAILED'}")

    # 4 — Renewal reminder
    print("[4/5] Renewal reminder ...")
    ok = send_renewal_reminder(
        user_id=TEST_USER_ID,
        amount_usd=97.00,
        renewal_date="June 24, 2026",
    )
    results.append(("Renewal reminder", ok))
    print(f"      {'OK' if ok else 'FAILED'}")

    # 5 — Cancellation confirmation
    print("[5/5] Cancellation confirmation ...")
    ok = send_cancellation_confirmation(
        user_id=TEST_USER_ID,
        effective_date="June 24, 2026",
        old_tier="platform",
    )
    results.append(("Cancellation confirmation", ok))
    print(f"      {'OK' if ok else 'FAILED'}")

finally:
    # Always clean up the ephemeral test user
    db["users"].delete_one({"user_id": TEST_USER_ID})
    db["password_reset_tokens"].delete_many({"user_id": TEST_USER_ID})

print()
print("=" * 50)
all_ok = all(ok for _, ok in results)
for name, ok in results:
    print(f"  {'✅' if ok else '❌'} {name}")
print()
if all_ok:
    print("ALL 5 EMAILS SENT SUCCESSFULLY")
    sys.exit(0)
else:
    print("ONE OR MORE EMAILS FAILED — check SendGrid activity log")
    sys.exit(1)
