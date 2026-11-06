"""API: RBAC, audit, genomic stripping, suppression, persona flows (PROMPT.md §8.1, Milestone 6).

Needs the generated data (`make data train simulate`); skipped otherwise.
"""

from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient

from wiqaya.common.paths import DUCKDB_PATH, RUNS_DIR

pytestmark = pytest.mark.skipif(
    not (DUCKDB_PATH.exists() and (RUNS_DIR / "simulation.json").exists()), reason="needs generated data"
)


@pytest.fixture(scope="module")
def app():
    from wiqaya.api.app import app as fastapi_app

    return fastapi_app


def login(app, role: str, hh: str = "hh-demo-001") -> TestClient:
    c = TestClient(app)
    r = c.post("/api/v1/session/guest", json={"role": role, "household_id": hh})
    assert r.status_code == 200, r.text
    return c


def test_no_session_is_401(app) -> None:
    assert TestClient(app).get("/api/v1/worklist").status_code == 401


def test_bad_role_rejected(app) -> None:
    assert TestClient(app).post("/api/v1/session/guest", json={"role": "root"}).status_code == 422


@pytest.mark.parametrize(
    ("role", "path", "status"),
    [
        ("coordinator", "/api/v1/worklist", 200),
        ("planner", "/api/v1/worklist", 403),
        ("family", "/api/v1/worklist", 403),
        ("planner", "/api/v1/people/demo-001", 403),
        ("family", "/api/v1/people/demo-001", 403),
        ("coordinator", "/api/v1/planner/districts", 403),
        ("planner", "/api/v1/planner/districts", 200),
        ("coordinator", "/api/v1/admin/audit", 403),
        ("admin", "/api/v1/admin/audit", 200),
        ("family", "/api/v1/family/hh-demo-001/messages", 200),
        ("family", "/api/v1/family/hh-demo-010/messages", 403),
        ("coordinator", "/api/v1/family/hh-demo-001/messages", 403),
    ],
)
def test_role_matrix(app, role: str, path: str, status: int) -> None:
    assert login(app, role).get(path).status_code == status


def test_family_role_cannot_read_genomic(app) -> None:
    # Family has no person endpoint at all; coordinator gets genomic fields stripped.
    c = login(app, "coordinator")
    body = c.get("/api/v1/people/demo-001").json()["data"]
    assert body["genomic"].startswith("restricted")
    text = json.dumps(body)
    assert "LDLR" not in text and "ClinVar" not in text


def test_clinician_sees_genomic(app) -> None:
    body = login(app, "clinician").get("/api/v1/people/demo-001").json()["data"]
    assert body["genomic"][0]["gene"] == "LDLR"
    assert body["cascade_index"]["tasks_created"] >= 3


def test_cascade_requires_clinician_signoff(app) -> None:
    c = login(app, "coordinator")
    fid = c.get("/api/v1/people/demo-004").json()["data"]["flag"]["flag_id"]
    assert c.post(f"/api/v1/flags/{fid}/decision", json={"decision": "accepted"}).status_code == 403
    c.post("/api/v1/session/guest", json={"role": "clinician"})  # role switch keeps the session overlay
    assert c.post(f"/api/v1/flags/{fid}/decision", json={"decision": "accepted"}).status_code == 200
    pv = c.post("/api/v1/outreach/preview", json={"flag_id": fid}).json()["data"]
    assert pv["status"].startswith("approved")


def test_reject_needs_reason(app) -> None:
    c = login(app, "coordinator")
    fid = c.get("/api/v1/people/demo-002").json()["data"]["flag"]["flag_id"]
    assert c.post(f"/api/v1/flags/{fid}/decision", json={"decision": "rejected"}).status_code == 422
    assert (
        c.post(f"/api/v1/flags/{fid}/decision", json={"decision": "rejected", "note": "moved away"}).status_code == 200
    )


def test_person_reads_are_audited(app) -> None:
    c = login(app, "coordinator")
    c.get("/api/v1/people/demo-002")
    a = login(app, "admin").get("/api/v1/admin/audit?limit=50").json()["data"]
    ev = next(e for e in a if e["entity_id"] == "demo-002")
    assert ev["actor_role"] == "coordinator" and ev["fields_read"]


@pytest.mark.parametrize(
    "path",
    [
        "/api/v1/planner/districts",
        "/api/v1/planner/equity?segment=district",
        "/api/v1/planner/equity?segment=language&policy=wiqaya",
        "/api/v1/planner/equity?segment=nationality_group",
    ],
)
def test_aggregates_are_suppressed(app, path: str) -> None:
    from wiqaya.governance.suppress import is_suppression_safe

    rows = login(app, "planner").get(path).json()["data"]
    assert rows and is_suppression_safe(rows)
    assert all("suppressed" in r for r in rows)


def test_every_aggregate_route_checked(app) -> None:
    from wiqaya.api.routers import AGGREGATE_PATHS, router

    planner_routes = {r.path for r in router.routes if getattr(r, "path", "").startswith("/api/v1/planner/")}
    assert planner_routes == set(AGGREGATE_PATHS)


def test_planner_gets_only_aggregates(app) -> None:
    body = login(app, "planner").get("/api/v1/planner/compare").json()
    assert body["label"] == "Simulated cohort"
    text = json.dumps(body)
    assert "demo-0" not in text and "p-0" not in text


def test_consent_edge_case_graph(app) -> None:
    g = login(app, "coordinator").get("/api/v1/family-graph/demo-001").json()["data"]
    ids = {n["id"] for n in g["nodes"]}
    assert {"demo-003", "demo-004", "demo-005"} <= ids
    assert "demo-020" not in ids
    g20 = login(app, "coordinator").get("/api/v1/family-graph/demo-020").json()["data"]
    assert g20["in_graph"] is False and g20["excluded_links"]


def test_family_sees_arabic_bundle_message(app) -> None:
    msgs = login(app, "family").get("/api/v1/family/hh-demo-001/messages").json()["data"]
    assert msgs
    m = next(x for x in msgs if x["recipient_id"] == "demo-002")
    assert m["language"] == "ar" and m["rtl"] and m["channel"] == "whatsapp"
    assert m["pathway"] == "household_bundle"


def test_worker_sms_malayalam_van(app) -> None:
    c = login(app, "coordinator")
    fid = c.get("/api/v1/people/demo-010").json()["data"]["flag"]["flag_id"]
    pv = c.post("/api/v1/outreach/preview", json={"flag_id": fid}).json()["data"]
    assert pv["channel"] == "sms" and pv["language"] == "ml" and pv["pathway"] == "mobile_van"


def test_guest_rate_limited() -> None:
    from fastapi import HTTPException

    from wiqaya.api.security import RateLimiter

    rl = RateLimiter(limit=2, window=60)
    rl.check("x")
    rl.check("x")
    with pytest.raises(HTTPException):
        rl.check("x")


def test_security_headers(app) -> None:
    r = TestClient(app).get("/api/v1/healthz")
    assert r.headers["X-Frame-Options"] == "DENY" and r.headers["X-Data-Label"] == "Simulated cohort"
