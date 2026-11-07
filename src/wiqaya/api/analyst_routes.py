"""Planner analyst routes (D-045). Aggregate-only agent; proposals need a human decision; every step is audited."""

from __future__ import annotations

from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from wiqaya.agents import analyst
from wiqaya.api.routers import envelope
from wiqaya.api.security import Session, audit, require
from wiqaya.api.store import get_store

router = APIRouter(prefix="/api/v1/planner/analyst", tags=["planner"])
ROLES = ("planner", "admin")


class Ask(BaseModel):
    question: str = Field(min_length=3, max_length=600)


class Decision(BaseModel):
    decision: Literal["approve", "dismiss"]
    note: str = Field(default="", max_length=500)


def _audit_done(role: str) -> Any:
    def cb(job: analyst.Job) -> None:
        tools = sorted({f"aggregate:{s['tool']}" for s in job.steps})
        audit.write(role, job.sid, f"analyst_answer_{job.status}", "PlannerAnalyst", job.id, tools)

    return cb


@router.get("/status")
def analyst_status(s: Session = Depends(require(*ROLES))) -> dict[str, Any]:  # noqa: B008
    return envelope(get_store(), analyst.status())


@router.post("/ask", status_code=202)
def analyst_ask(body: Ask, s: Session = Depends(require(*ROLES))) -> dict[str, Any]:  # noqa: B008
    st = analyst.status()
    if not st["enabled"]:
        raise HTTPException(503, st["reason"])
    if analyst.agents.busy(s.sid):
        raise HTTPException(409, "The analyst is still working on your previous question.")
    if not analyst.agents.allow(s.sid):
        raise HTTPException(429, f"Limit of {analyst.QUESTIONS_PER_HOUR} questions per hour reached.")
    job = analyst.start(s.sid, body.question.strip(), on_done=_audit_done(s.role))
    audit.write(s.role, s.sid, "analyst_question", "PlannerAnalyst", job.id, [])
    return envelope(get_store(), job.public())


@router.get("/jobs/{job_id}")
def analyst_job(job_id: str, s: Session = Depends(require(*ROLES))) -> dict[str, Any]:  # noqa: B008
    job = analyst.agents.jobs.get(job_id)
    if not job or job.sid != s.sid:
        raise HTTPException(404, "No such analyst job in this session.")
    return envelope(get_store(), job.public())


@router.post("/proposals/{proposal_id}/decision")
def analyst_decide(proposal_id: str, body: Decision, s: Session = Depends(require(*ROLES))) -> dict[str, Any]:  # noqa: B008
    p = analyst.agents.proposal(s.sid, proposal_id)
    if not p:
        raise HTTPException(404, "No such proposal in this session.")
    from datetime import UTC, datetime

    p.update(status="approved" if body.decision == "approve" else "dismissed", decided_by=s.role,
             decided_at=datetime.now(UTC).isoformat(timespec="seconds"), note=body.note)  # fmt: skip
    audit.write(s.role, s.sid, f"analyst_proposal_{p['status']}", "Proposal", proposal_id, [])
    return envelope(get_store(), p)


@router.post("/reset")
def analyst_reset(s: Session = Depends(require(*ROLES))) -> dict[str, Any]:  # noqa: B008
    analyst.agents.reset(s.sid)
    return envelope(get_store(), {"reset": True})
