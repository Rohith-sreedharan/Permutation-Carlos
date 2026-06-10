#!/usr/bin/env python3
"""
Find Prediction for Game

Check if a prediction record was created for a given game_id.
"""

import sys
from pathlib import Path
import json

# Add backend to path
ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(ROOT / 'backend'))

from db.mongo import db  # noqa: E402

GAME_ID = 'd43ce85e303f5250627d2ea74cd1e799'


def main():
    """
    Finds predictions associated with the game.
    """
    print(f"Searching for predictions for game_id: {GAME_ID}")

    predictions = list(db.predictions.find({'event_id': GAME_ID}))

    if not predictions:
        print("No predictions found for this game.")
        return 1

    print(f"Found {len(predictions)} prediction(s):")
    for pred in predictions:
        # Convert ObjectId to string for JSON serialization
        pred['_id'] = str(pred['_id'])
        print(json.dumps(pred, indent=2))

    return 0


if __name__ == '__main__':
    raise SystemExit(main())
