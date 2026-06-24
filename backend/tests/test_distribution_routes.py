from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient

import routes.distribution_routes as distribution_routes


class FakeDistributionService:
    def __init__(self, result):
        self._result = result

    def evaluate(self, decision_id: str, trace_id: str):
        return self._result


def make_client(monkeypatch, service):
    app = FastAPI()
    monkeypatch.setattr(distribution_routes, "get_distribution_governance_service", lambda: service)
    app.include_router(distribution_routes.router)
    return TestClient(app)


def test_evaluate_distribution_returns_200_for_new_decision(monkeypatch):
    result = SimpleNamespace(
        distribution_id="dist_1",
        decision_id="decision_1",
        distribution_category="SELECTED_PLAY",
        rule_applied="PASS_ALL_RULES",
        withheld_reason=None,
        evaluated_at_utc="2026-03-16T00:00:00+00:00",
        already_exists=False,
    )
    client = make_client(monkeypatch, FakeDistributionService(result))

    response = client.post("/internal/distribution/evaluate", json={"decision_id": "decision_1", "trace_id": "trace_1"})

    assert response.status_code == 200
    body = response.json()
    assert body["distribution_id"] == "dist_1"
    assert body["distribution_category"] == "SELECTED_PLAY"


def test_evaluate_distribution_returns_409_when_already_exists(monkeypatch):
    result = SimpleNamespace(
        distribution_id="dist_2",
        decision_id="decision_2",
        distribution_category="ANALYSIS_ONLY",
        rule_applied="NO_ACTION_CLASSIFICATION",
        withheld_reason=None,
        evaluated_at_utc="2026-03-16T00:00:00+00:00",
        already_exists=True,
    )
    client = make_client(monkeypatch, FakeDistributionService(result))

    response = client.post("/internal/distribution/evaluate", json={"decision_id": "decision_2", "trace_id": "trace_2"})

    assert response.status_code == 409
    detail = response.json()["detail"]
    assert detail["decision_id"] == "decision_2"
    assert detail["rule_applied"] == "NO_ACTION_CLASSIFICATION"
