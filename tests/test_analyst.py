"""Planner analyst agent (D-045): aggregate-only tools, number check, human approval, audit. Uses a fake client."""

from __future__ import annotations

import json
import time
from types import SimpleNamespace as NS
from typing import Any

import pytest
from fastapi.testclient import TestClient

from wiqaya.common.paths import DUCKDB_PATH, RUNS_DIR

pytestmark = pytest.mark.skipif(
    not (DUCKDB_PATH.exists() and (RUNS_DIR / "simulation.json").exists()), reason="needs generated data"
)


def login(role: str) -> TestClient:
    from wiqaya.api.app import app

    c = TestClient(app)
    assert c.post("/api/v1/session/guest", json={"role": role}).status_code == 200
    return c


def _usage() -> NS:
    return NS(input_tokens=10, output_tokens=5, cache_read_input_tokens=0)


def _tool(i: int, name: str, args: dict[str, Any]) -> NS:
    return NS(type="tool_use", id=f"tu{i}", name=name, input=args)


class FakeClient:
    """Scripted model: reads need, runs a what-if, proposes, then answers with one real and one invented number."""

    def __init__(self, *a: Any, **k: Any) -> None:
        self.turn = 0
        self.beta = NS(messages=NS(create=self.create))

    def create(self, **kw: Any) -> NS:
        assert kw["model"] == "claude-opus-5-5" and kw["tools"] and "SIMULATED COHORT" in kw["system"]
        self.turn += 1
        if self.turn == 1:
            content = [_tool(1, "get_district_need", {"population": "all"}),
                       _tool(2, "estimate_extra_capacity", {"district_id": "musaffah", "extra_slots_12w": 48})]  # fmt: skip
            return NS(content=content, stop_reason="tool_use", usage=_usage())
        if self.turn == 2:
            est = json.loads(kw["messages"][-1]["content"][1]["content"])
            self.mid = est["estimated_extra_completed"]["mid"]
            self.unmet = est["unmet_people"]
            content = [_tool(3, "propose_action", {"title": "Add a van day in Musaffah", "action_type": "add_van_day",
                                                   "district_id": "musaffah", "rationale": "High unmet need",
                                                   "expected_effect": "More completed screenings"})]  # fmt: skip
            return NS(content=content, stop_reason="tool_use", usage=_usage())
        text = f"Musaffah has {self.unmet} people with unmet need; a van day could add about {self.mid}. Also 987.6."
        return NS(content=[NS(type="text", text=text)], stop_reason="end_turn", usage=_usage())


def _wait(c: TestClient, job_id: str) -> dict[str, Any]:
    for _ in range(100):
        j = c.get(f"/api/v1/planner/analyst/jobs/{job_id}").json()["data"]
        if j["status"] != "running":
            return j
        time.sleep(0.05)
    raise AssertionError("job did not finish")


def test_disabled_without_key(monkeypatch) -> None:
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    c = login("planner")
    assert c.get("/api/v1/planner/analyst/status").json()["data"]["enabled"] is False
    assert c.post("/api/v1/planner/analyst/ask", json={"question": "Where is need highest?"}).status_code == 503


@pytest.mark.parametrize("role", ["coordinator", "clinician", "family"])
def test_only_planner_and_admin(role: str) -> None:
    assert login(role).get("/api/v1/planner/analyst/status").status_code == 403


def test_tools_return_only_suppressed_aggregates() -> None:
    from wiqaya.agents import analyst
    from wiqaya.governance.suppress import is_suppression_safe

    job = analyst.Job(id="t", sid="test-sid", question="q")
    calls = [("get_district_need", {"population": p}) for p in analyst.POPULATIONS]
    calls += [("get_equity", {"segment": s}) for s in analyst.SEGMENTS]
    calls += [("get_policy_comparison", {}), ("get_model_calibration", {}),
              ("list_sites", {"district_id": "musaffah"}),
              ("estimate_extra_capacity", {"district_id": "musaffah", "extra_slots_12w": 24})]  # fmt: skip
    for name, args in calls:
        out = analyst.run_tool(name, args, "test-sid", job)
        assert "error" not in out, (name, out)
        text = json.dumps(out, default=str)
        assert "demo-0" not in text and '"p-0' not in text and "person_id" not in text, name
        for rows in (out.get("districts"), out.get("rows")):
            if rows:
                assert is_suppression_safe(rows), name
    assert "error" in analyst.run_tool("list_sites", {"district_id": "nowhere"}, "test-sid", job)


def test_number_check_flags_invented_numbers() -> None:
    from wiqaya.agents.analyst import check_numbers

    r = check_numbers("Uptake is 44.6 vs 19.8 per 100; reach 41.5%. Also 3 districts and 77.7.",
                      [{"wiqaya": 44.59, "baseline": 19.8, "reach": 0.415}], "q")  # fmt: skip
    assert r["unverified"] == ["77.7"] and r["verified"] == 3


def test_agent_loop_proposal_and_audit(monkeypatch) -> None:
    import anthropic

    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    monkeypatch.setattr(anthropic, "Anthropic", FakeClient)
    c = login("planner")
    r = c.post("/api/v1/planner/analyst/ask", json={"question": "Where would a van day help most?"})
    assert r.status_code == 202, r.text
    job = _wait(c, r.json()["data"]["id"])
    assert job["status"] == "done", job
    assert [s["tool"] for s in job["steps"]] == ["get_district_need", "estimate_extra_capacity", "propose_action"]
    assert job["number_check"]["unverified"] == ["987.6"]
    (p,) = job["proposals"]
    assert p["status"] == "pending_approval"

    other = login("planner")  # proposals are private to the session
    assert other.post(f"/api/v1/planner/analyst/proposals/{p['id']}/decision",
                      json={"decision": "approve"}).status_code == 404  # fmt: skip
    d = c.post(f"/api/v1/planner/analyst/proposals/{p['id']}/decision", json={"decision": "approve"}).json()["data"]
    assert d["status"] == "approved" and d["decided_by"] == "planner"

    from wiqaya.api.security import audit

    actions = {e["action"] for e in audit.recent(50)}
    assert {"analyst_question", "analyst_answer_done", "analyst_proposal_approved"} <= actions
