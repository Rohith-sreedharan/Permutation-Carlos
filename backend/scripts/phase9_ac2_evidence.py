"""
Phase 9 AC-2 Evidence Script

Verifies that data_deletion_log completion entries contain per-collection processing
for all mandated data types in the Phase 9 directive.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Dict, List, Set

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from db.mongo import db


REQUIRED_COLLECTIONS: Set[str] = {
    "users",
    "password_reset_tokens",
    "outbound_communication_log",
    "decision_records",
    "decision_settlement_metrics",
    "truth_dataset",
    "ai_picks",
    "billing_ledger",
    "billing_state_change_log",
    "commissions",
    "parlay_overage_charge_log",
    "sentinel_event_log",
    "self_exclusion_log",
}


def latest_completed_entry() -> Dict:
    entry = db["data_deletion_log"].find_one(
        {"status": "COMPLETED"},
        sort=[("completed_at_utc", -1)],
    )
    if not entry:
        raise RuntimeError("No COMPLETED data_deletion_log entry found")
    return entry


def main() -> None:
    entry = latest_completed_entry()
    report: List[Dict] = entry.get("collection_report", [])
    seen = {row.get("collection") for row in report if row.get("collection")}

    missing = sorted(REQUIRED_COLLECTIONS - seen)
    print("=== PHASE 9 AC-2 EVIDENCE ===")
    print(f"request_id: {entry.get('request_id')}")
    print(f"trace_id: {entry.get('trace_id')}")
    print(f"requested_at_utc: {entry.get('requested_at_utc')}")
    print(f"completed_at_utc: {entry.get('completed_at_utc')}")
    print(f"items_processed: {entry.get('items_processed')}")
    print(f"collection_report_entries: {len(report)}")
    print(f"required_collections_seen: {len(REQUIRED_COLLECTIONS - set(missing))}/{len(REQUIRED_COLLECTIONS)}")

    print("\n-- Collection Processing --")
    for row in report:
        print(row)

    if missing:
        print("\nSTATUS: FAIL")
        print(f"Missing required collections: {missing}")
        raise SystemExit(1)

    print("\nSTATUS: PASS")


if __name__ == "__main__":
    main()
