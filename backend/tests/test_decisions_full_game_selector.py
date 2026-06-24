from datetime import datetime, timedelta, timezone
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from routes.decisions import _build_full_game_simulation_filter


class _FakeCollection:
    def __init__(self, docs):
        self.docs = docs

    def _matches(self, doc, query):
        if "$and" in query:
            return all(self._matches(doc, q) for q in query["$and"])
        if "$or" in query:
            return any(self._matches(doc, q) for q in query["$or"])

        for key, value in query.items():
            if isinstance(value, dict) and "$exists" in value:
                exists = key in doc
                if exists != bool(value["$exists"]):
                    return False
            else:
                if doc.get(key) != value:
                    return False
        return True

    def find_one(self, query, sort=None):
        matches = [d for d in self.docs if self._matches(d, query)]
        if not matches:
            return None
        if sort:
            field, direction = sort[0]
            reverse = direction < 0
            matches.sort(key=lambda d: d.get(field), reverse=reverse)
        return matches[0]


def test_full_game_selector_ignores_newer_1h_simulation():
    event_id = "evt_123"
    now = datetime.now(timezone.utc)

    older_full_game = {
        "event_id": event_id,
        "simulation_id": "sim_evt_123_full_old",
        "created_at": now - timedelta(minutes=10),
        "market_views": {
            "spread": {
                "edge_class": "NO_ACTION",
                "model_preference_selection_id": "NO_EDGE",
                "selections": [
                    {"selection_id": "s1", "market_line_for_selection": -1.5},
                    {"selection_id": "s2", "market_line_for_selection": 1.5},
                ],
            }
        },
    }

    newer_1h_missing_spread = {
        "event_id": event_id,
        "simulation_id": "sim_1H_evt_123_new",
        "period": "1H",
        "created_at": now,
        # Intentionally no market_views.spread bindings
    }

    coll = _FakeCollection([older_full_game, newer_1h_missing_spread])
    selected = coll.find_one(_build_full_game_simulation_filter(event_id), sort=[("created_at", -1)])

    assert selected is not None
    assert selected["simulation_id"] == "sim_evt_123_full_old"
    assert selected.get("period") is None
    assert bool(((selected.get("market_views") or {}).get("spread"))) is True
