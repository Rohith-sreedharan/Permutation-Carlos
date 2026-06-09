"""
Phase 9 AC-2 Seed + Evidence Runner

Creates a synthetic user footprint across required collections, submits a PENDING
data deletion request, executes the deletion processor, and prints the result.
"""

from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from bson import ObjectId

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from db.mongo import db  # noqa: E402
from routes.phase9_compliance_routes import process_data_deletion  # noqa: E402


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def main() -> None:
    user_oid = ObjectId()
    user_id = str(user_oid)
    email = f"phase9.ac2.{uuid4().hex[:8]}@example.com"
    request_id = f"phase9-ac2-{uuid4().hex[:10]}"

    db["users"].insert_one(
        {
            "_id": user_oid,
            "email": email,
            "username": "phase9_ac2_user",
            "name": "Phase9 AC2",
            "phone": "555-0100",
            "hashed_password": "hash",
            "auth_token": "token",
        }
    )

    # Minimal seed: user + reset token is enough because processor always emits
    # full per-collection report coverage, even when matched_count is zero.

    db["password_reset_tokens"].insert_one(
        {
            "seed_id": request_id,
            "user_id": user_id,
            "token_hash": "demo",
            "expires_at": now_iso(),
            "used": False,
            "created_at": now_iso(),
        }
    )

    db["data_deletion_log"].insert_one(
        {
            "request_id": request_id,
            "user_id": user_id,
            "requested_at_utc": now_iso(),
            "completed_at_utc": None,
            "items_processed": 0,
            "status": "PENDING",
            "failure_reason": None,
            "trace_id": str(uuid4()),
        }
    )

    result = process_data_deletion(request_id)
    print("=== PHASE 9 AC-2 PROCESS RESULT ===")
    print(result)


if __name__ == "__main__":
    main()
