from services.grading_service import GradingService
import services.grading_service as grading_module


class FakeCollection:
    def __init__(self, docs=None):
        self.docs = docs or []

    def find_one(self, query, sort=None):
        matches = [doc for doc in self.docs if all(doc.get(k) == v for k, v in query.items())]
        if not matches:
            return None
        if sort:
            key, direction = sort[0]
            matches.sort(key=lambda d: d.get(key), reverse=direction < 0)
        return matches[0]

    def insert_one(self, doc):
        self.docs.append(doc)
        return type("InsertResult", (), {"inserted_id": doc.get("graded_id", "ok")})

    def update_one(self, query, update):
        for doc in self.docs:
            if all(doc.get(k) == v for k, v in query.items()):
                doc.update(update.get("$set", {}))
                return type("UpdateResult", (), {"modified_count": 1})
        return type("UpdateResult", (), {"modified_count": 0})

    def find(self, query):
        def match(doc):
            for k, v in query.items():
                if isinstance(v, dict) and "$gte" in v:
                    if doc.get(k) < v["$gte"]:
                        return False
                elif doc.get(k) != v:
                    return False
            return True

        return [doc for doc in self.docs if match(doc)]


class FakeObservability:
    def __init__(self):
        self.settlement_calls = 0
        self.truth_calls = 0
        self.clv_calls = 0
        self.lifecycle_calls = 0

    def log_settlement_metrics(self, **_kwargs):
        self.settlement_calls += 1

    def log_truth_dataset_row(self, **_kwargs):
        self.truth_calls += 1

    def log_clv_capture(self, **_kwargs):
        self.clv_calls += 1

    def log_prediction_lifecycle(self, **_kwargs):
        self.lifecycle_calls += 1


def make_service() -> GradingService:
    svc = GradingService()
    setattr(svc, "grading_collection", FakeCollection())
    setattr(svc, "published_collection", FakeCollection())
    setattr(svc, "predictions_collection", FakeCollection())
    setattr(svc, "event_results_collection", FakeCollection())
    setattr(svc, "odds_snapshots_collection", FakeCollection())
    return svc


def test_grade_published_prediction_skips_non_official_predictions(monkeypatch):
    svc = make_service()
    published = FakeCollection(
        docs=[
        {
            "publish_id": "pub_non_official",
            "prediction_id": "pred_1",
            "event_id": "event_1",
            "is_official": False,
        }
    ]
    )
    setattr(svc, "published_collection", published)

    result = svc.grade_published_prediction("pub_non_official")

    assert result is None
    grading_records = getattr(svc, "grading_collection")
    assert len(grading_records.docs) == 0


def test_grade_published_prediction_writes_grading_and_observability(monkeypatch):
    svc = make_service()
    fake_obs = FakeObservability()
    monkeypatch.setattr(grading_module, "observability_service", fake_obs)

    published = FakeCollection(
        docs=[
        {
            "publish_id": "pub_1",
            "prediction_id": "pred_1",
            "event_id": "event_1",
            "is_official": True,
            "ticket_terms": {"line": -3.0, "price": -110},
            "published_at_utc": "2026-03-01T00:00:00+00:00",
            "trace_id": "trace_pub_1",
        }
    ]
    )
    predictions = FakeCollection(
        docs=[
        {
            "prediction_id": "pred_1",
            "market_key": "SPREAD:FULL_GAME",
            "selection": "HOME",
            "p_cover": 0.62,
            "market_snapshot_id_used": "snap_open_1",
            "decision_id": "decision_1",
        }
    ]
    )
    event_results = FakeCollection(
        docs=[
        {
            "event_id": "event_1",
            "status": "FINAL",
            "home_score": 110,
            "away_score": 103,
            "total_score": 213,
            "margin": 7,
        }
    ]
    )
    odds_snapshots = FakeCollection(
        docs=[
        {
            "snapshot_id": "snap_close_1",
            "event_id": "event_1",
            "market_key": "SPREAD:FULL_GAME",
            "selection": "HOME",
            "is_close_candidate": True,
            "price_american": -120,
        }
    ]
    )

    setattr(svc, "published_collection", published)
    setattr(svc, "predictions_collection", predictions)
    setattr(svc, "event_results_collection", event_results)
    setattr(svc, "odds_snapshots_collection", odds_snapshots)

    graded_id = svc.grade_published_prediction("pub_1")

    assert graded_id is not None
    grading_records = getattr(svc, "grading_collection")
    assert len(grading_records.docs) == 1
    doc = grading_records.docs[0]
    assert doc["publish_id"] == "pub_1"
    assert doc["result_code"] == "WIN"
    assert doc["bet_status"] == "SETTLED"
    assert doc["close_snapshot_id"] == "snap_close_1"

    assert fake_obs.settlement_calls == 1
    assert fake_obs.truth_calls == 1
    assert fake_obs.clv_calls == 1
    assert fake_obs.lifecycle_calls == 1
