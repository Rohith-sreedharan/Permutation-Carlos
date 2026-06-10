from fastapi import FastAPI
from fastapi.testclient import TestClient

import routes.integrity_routes as integrity_routes


class FakeIntegritySentinel:
    def __init__(self):
        self.calls = []

    def run_check_cycle(self, enforce_actions: bool = True):
        self.calls.append(enforce_actions)
        return {"ok": True, "enforce_actions": enforce_actions}

    def get_latest_status(self):
        return {"last": "status"}


def make_client(monkeypatch, sentinel):
    app = FastAPI()
    monkeypatch.setattr(integrity_routes, "get_integrity_sentinel", lambda: sentinel)
    app.include_router(integrity_routes.router)
    return TestClient(app)


def test_run_integrity_check_uses_payload_enforce_actions(monkeypatch):
    sentinel = FakeIntegritySentinel()
    client = make_client(monkeypatch, sentinel)

    response = client.post("/internal/integrity/check", json={"enforce_actions": False})

    assert response.status_code == 200
    assert response.json()["enforce_actions"] is False
    assert sentinel.calls == [False]


def test_get_latest_integrity_status_returns_wrapper_object(monkeypatch):
    sentinel = FakeIntegritySentinel()
    client = make_client(monkeypatch, sentinel)

    response = client.get("/internal/integrity/latest")

    assert response.status_code == 200
    assert response.json() == {"status": {"last": "status"}}
