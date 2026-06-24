from datetime import datetime, timezone, timedelta
import asyncio

from routes import decision_log_routes


class _FakeCursor:
    def __init__(self, docs):
        self._docs = list(docs)

    def sort(self, key, direction):
        reverse = direction == -1
        self._docs = sorted(self._docs, key=lambda d: d.get(key, ""), reverse=reverse)
        return self

    def limit(self, n):
        self._docs = self._docs[:n]
        return self

    def __iter__(self):
        return iter(self._docs)


class _FakeCollection:
    def __init__(self, docs):
        self._docs = list(docs)

    def find(self, query=None, projection=None):
        query = query or {}
        rows = self._docs

        if "user_id" in query:
            rows = [r for r in rows if r.get("user_id") == query["user_id"]]

        event_filter = query.get("event_id")
        if isinstance(event_filter, dict) and "$in" in event_filter:
            wanted = set(event_filter["$in"])
            rows = [r for r in rows if r.get("event_id") in wanted]

        if projection:
            projected = []
            include_keys = [k for k, v in projection.items() if v and k != "_id"]
            for row in rows:
                projected.append({k: row.get(k) for k in include_keys})
            rows = projected

        return _FakeCursor(rows)


class _FakeDB:
    def __init__(self, opened_rows, settlement_rows):
        self._collections = {
            "opened_event_log": _FakeCollection(opened_rows),
            "decision_settlement_metrics": _FakeCollection(settlement_rows),
        }

    def __getitem__(self, name):
        return self._collections[name]


def test_opened_picks_projection_uses_settlement_metrics(monkeypatch):
    now = datetime.now(timezone.utc)
    this_week_opened = now.isoformat()
    old_opened = (now - timedelta(days=10)).isoformat()

    fake_db = _FakeDB(
        opened_rows=[
            {
                "opened_event_id": "open_1",
                "user_id": "user_abc",
                "event_id": "evt_win",
                "league": "NBA",
                "opened_at": this_week_opened,
                "decision_record_id": "rec_1",
                "market_snapshot": {"spread_classification": "EDGE"},
            },
            {
                "opened_event_id": "open_2",
                "user_id": "user_abc",
                "event_id": "evt_loss",
                "league": "NFL",
                "opened_at": old_opened,
                "decision_record_id": "rec_2",
                "market_snapshot": {"spread_classification": "LEAN"},
            },
        ],
        settlement_rows=[
            {"event_id": "evt_win", "result_code": "WIN", "timestamp": now.isoformat()},
            {"event_id": "evt_loss", "result_code": "LOSS", "timestamp": now.isoformat()},
        ],
    )

    monkeypatch.setattr(decision_log_routes, "db", fake_db)

    result = asyncio.run(decision_log_routes.get_opened_picks(limit=20, user={"_id": "user_abc"}))

    assert result["count"] == 2
    assert result["weekly_record"]["wins"] == 1
    assert result["weekly_record"]["losses"] == 0
    assert result["opened_picks"][0]["settlement_outcome"] in {"WIN", "LOSS"}
