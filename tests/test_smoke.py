"""Milestone 0 smoke tests: package imports and the API health check."""

from fastapi.testclient import TestClient

import wiqaya
from wiqaya.api.app import app


def test_version() -> None:
    assert wiqaya.__version__ == "0.1.0"


def test_healthz() -> None:
    client = TestClient(app)
    resp = client.get("/api/v1/healthz")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["data"] == "simulated cohort"
