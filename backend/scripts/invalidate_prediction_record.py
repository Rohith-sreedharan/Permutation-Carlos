#!/usr/bin/env python3
"""
FIX-07-B: Invalidate Prediction Record

Manually modified a simulation to generate an EDGE case for API contract proof.
This created a prediction record that was not published due to a low grade.
This script marks that prediction record as invalid.
"""

import sys
from pathlib import Path
from datetime import datetime, timezone

# Add backend to path
ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(ROOT / 'backend'))

from db.mongo import db  # noqa: E402

PREDICTION_ID = "pred_d43ce85e303f5250627d2ea74cd1e799_spread_20260308154713"
VOID_REASON = "Invalid record from manual simulation modification for testing"


def main():
    """
    Finds the prediction and marks it as invalid.
    """
    print(f"Searching for prediction_id: {PREDICTION_ID}")

    prediction = db.predictions.find_one({'prediction_id': PREDICTION_ID})

    if not prediction:
        print("ERROR: Prediction not found. Cannot invalidate.")
        return 1

    print("Found prediction. Updating status to INVALID.")

    result = db.predictions.update_one(
        {'_id': prediction['_id']},
        {
            '$set': {
                'grading_status': 'INVALID',
                'void_reason': VOID_REASON,
                'voided_at': datetime.now(timezone.utc)
            }
        }
    )

    if result.modified_count > 0:
        print("Successfully marked prediction as INVALID.")
        
        # Verify the update
        updated_record = db.predictions.find_one({'_id': prediction['_id']})
        print("\n--- VERIFICATION ---")
        print(f"grading_status: {updated_record.get('grading_status')}")
        print(f"void_reason: {updated_record.get('void_reason')}")
        print(f"voided_at: {updated_record.get('voided_at')}")
        print("--- VERIFICATION COMPLETE ---")

    else:
        print("ERROR: Failed to update prediction record.")
        return 1

    return 0


if __name__ == '__main__':
    raise SystemExit(main())
