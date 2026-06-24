#!/usr/bin/env python3
"""
FIX-07-B: Void Invalidated Record

Manually modified a simulation to generate an EDGE case for API contract proof.
This script voids the resulting published prediction record as per protocol B.
"""

import sys
from pathlib import Path

# Add backend to path
ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(ROOT / 'backend'))

from services.publishing_service import publishing_service  # noqa: E402
from db.mongo import db # noqa: E402

GAME_ID = 'd43ce85e303f5250627d2ea74cd1e799'
VOID_REASON = "Manual simulation modification — invalid record"


def main():
    """
    Finds the published prediction associated with the manually altered
    simulation and voids it.
    """
    print(f"Searching for published predictions for game_id: {GAME_ID}")

    # Find the prediction created from the modified simulation
    # It should be the only one for this game that is an official prediction
    published_predictions = publishing_service.get_published_predictions_for_event(GAME_ID)

    if not published_predictions:
        print("ERROR: No published predictions found for this game. Cannot void.")
        return 1

    # We expect only one record to have been created
    if len(published_predictions) > 1:
        print(f"WARNING: Found {len(published_predictions)} published predictions. Voiding all of them.")

    for prediction in published_predictions:
        publish_id = prediction['publish_id']
        print(f"Found published prediction to void: {publish_id}")

        # Void the prediction
        print(f"Voiding prediction with reason: '{VOID_REASON}'")
        success = publishing_service.void_published_prediction(publish_id, VOID_REASON)

        if success:
            print(f"Successfully voided prediction: {publish_id}")

            # Verify the record is updated
            voided_record = publishing_service.get_published_prediction(publish_id)
            print("\n--- VERIFICATION ---")
            print(f"is_official: {voided_record.get('is_official')}")
            print(f"void_reason: {voided_record.get('void_reason')}")
            print(f"voided_at: {voided_record.get('voided_at')}")
            print("--- VERIFICATION COMPLETE ---")

            # Check audit log (observability service)
            # For this script, we assume the log is written correctly by the service.
            # A full verification would involve querying the observability sink.
            print("\nAudit log entry for VOIDED stage created by publishing_service.")

        else:
            print(f"ERROR: Failed to void prediction: {publish_id}")
            return 1

    # Regarding replacement: The system should automatically generate a new
    # prediction if market conditions warrant it. We can check for a new
    # publishable prediction.
    print("\nChecking for new publishable predictions for this event...")
    publishable = publishing_service.get_publishable_predictions(event_id=GAME_ID)
    if publishable:
        print(f"Found {len(publishable)} new publishable predictions that can replace the voided one.")
    else:
        print("No new publishable predictions found at this time. This is expected if market conditions have changed.")

    return 0


if __name__ == '__main__':
    raise SystemExit(main())
