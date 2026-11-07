"""Planner analyst: a Claude tool-use agent over suppressed aggregate data (docs/DECISIONS.md D-045).

Governance:
- The tools reach only the planner's aggregate endpoints, so n<11 suppression applies to everything the model sees.
  There is no person-level tool.
- Every number in the answer is checked against the tool results. Numbers not found there are flagged in the UI.
- The agent can only *propose* actions. A planner approves or dismisses each proposal, and both are audited.
- Off by default: it needs ANTHROPIC_API_KEY, and AGENT_ENABLED=false turns it off.
"""

from __future__ import annotations

import json
import os
import re
import secrets
import threading
import time
from collections import defaultdict, deque
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

MODEL = os.environ.get("AGENT_MODEL", "claude-opus-5-5")
MAX_STEPS = int(os.environ.get("AGENT_MAX_STEPS", "8"))
QUESTIONS_PER_HOUR = int(os.environ.get("AGENT_QUESTIONS_PER_HOUR", "15"))
POPULATIONS = ["all", "labour_accommodation", "children_under_6", "adults_65_plus"]
SEGMENTS = ["nationality_group", "language", "age_band", "sex", "district", "housing_type", "insurance_tier",
            "district_x_nationality"]  # fmt: skip
ACTION_TYPES = ["add_van_day", "extend_clinic_hours", "targeted_outreach", "language_support", "translation_review",
                "investigate_further", "other"]  # fmt: skip


def status() -> dict[str, Any]:
    has_key = bool(os.environ.get("ANTHROPIC_API_KEY"))
    on = has_key and os.environ.get("AGENT_ENABLED", "true").lower() != "false"
    reason = None if on else ("Set ANTHROPIC_API_KEY to enable the AI analyst." if not has_key
                              else "Disabled by AGENT_ENABLED=false.")  # fmt: skip
    return {"enabled": on, "model": MODEL, "reason": reason, "max_steps": MAX_STEPS,
            "questions_per_hour": QUESTIONS_PER_HOUR}  # fmt: skip


SYSTEM = """You are the Wiqaya planner analyst. You help a health-authority planner in Abu Dhabi understand a \
preventive-screening outreach programme and decide where to act.

Data and limits:
- All data is a SIMULATED COHORT of 20,000 synthetic people. Say "simulated" when you report results.
- You see only aggregate, small-cell-suppressed data through your tools. Values shown as "suppressed" cover fewer \
than 11 people. Never estimate, back-calculate or guess a suppressed value, and do not combine cells to reveal one.
- You have no access to individual people and must not ask for it.
- Wiqaya reorders outreach. It does not diagnose. Do not give clinical advice or change clinical pathways.

How to work:
- Use the tools for every figure you report. Never invent numbers. If the tools cannot answer, say so.
- Compare the baseline (today's outreach) with Wiqaya where it helps.
- capacity what-ifs come from estimate_extra_capacity: a rough estimate from simulated rates, not a re-simulation. \
Report its range and say it is an estimate.
- When a concrete action follows from the evidence, call propose_action (at most 3 per question). A planner must \
approve each proposal; you never act yourself.
- Stop calling tools once you can answer.

Answer format (plain English, short, for a busy planner):
1. A one- or two-sentence direct answer.
2. "Evidence:" 2-5 bullets, each with the figure and where it came from.
3. "Caveats:" 1-3 bullets (simulation assumptions, suppression, estimate uncertainty).
No tables. No headings other than "Evidence:" and "Caveats:"."""


def _obj(props: dict[str, Any], required: list[str] | None = None) -> dict[str, Any]:
    return {"type": "object", "properties": props, "required": required if required is not None else list(props),
            "additionalProperties": False}  # fmt: skip


TOOLS: list[dict[str, Any]] = [
    {"name": "get_district_need",
     "description": "Need and capacity per district for a population: people, open care gaps, gaps per 1,000, "
                    "unmet need per 1,000 (people with a gap and no assigned slot), 12-week slots, need-vs-capacity "
                    "ratio, and Wiqaya completed screenings per 100 contacts. Small cells are suppressed.",
     "input_schema": _obj({"population": {"type": "string", "enum": POPULATIONS}}), "strict": True},
    {"name": "get_equity",
     "description": "Simulated 12-week results by population segment for baseline and Wiqaya: reach %, completed "
                    "per 100 contacts, gaps closed %. Small cells are suppressed.",
     "input_schema": _obj({"segment": {"type": "string", "enum": SEGMENTS}}), "strict": True},
    {"name": "get_policy_comparison",
     "description": "Headline baseline vs Wiqaya results: primary endpoint, per-policy totals, capacity, and the "
                    "three sensitivity scenarios (less favourable assumptions).",
     "input_schema": _obj({}), "strict": True},
    {"name": "get_model_calibration",
     "description": "Risk model (R) and no-show model (N) quality on held-out synthetic data: AUROC, Brier, "
                    "calibration slope, and per-segment results (suppressed when small).",
     "input_schema": _obj({}), "strict": True},
    {"name": "list_sites",
     "description": "Clinics and mobile-van stops in a district, with opening hours and 12-week slot capacity "
                    "by slot type.",
     "input_schema": _obj({"district_id": {"type": "string"}}), "strict": True},
    {"name": "estimate_extra_capacity",
     "description": "Rough what-if: extra completed screenings over 12 weeks if a district gets extra slots "
                    "(a van day = 12 slots). Uses the district's unmet need and simulated completion rates, with a "
                    "low-high range from the sensitivity scenarios. Not a re-simulation.",
     "input_schema": _obj({"district_id": {"type": "string"},
                           "extra_slots_12w": {"type": "integer", "description": "Extra slots over 12 weeks, 1-1000"}}),
     "strict": True},
    {"name": "propose_action",
     "description": "Propose one concrete action for a planner to approve or dismiss. Nothing happens until a "
                    "human approves it.",
     "input_schema": _obj({
         "title": {"type": "string", "description": "Short imperative title, under 80 characters"},
         "action_type": {"type": "string", "enum": ACTION_TYPES},
         "district_id": {"type": "string", "description": "District id, or 'all'"},
         "rationale": {"type": "string", "description": "Why, citing figures from tool results"},
         "expected_effect": {"type": "string", "description": "Expected effect with its uncertainty"},
     }), "strict": True},
]  # fmt: skip

TOOL_LABEL = {
    "get_district_need": "Read district need and capacity",
    "get_equity": "Read equity results by segment",
    "get_policy_comparison": "Read baseline vs Wiqaya comparison",
    "get_model_calibration": "Read model calibration",
    "list_sites": "Listed clinics and van stops",
    "estimate_extra_capacity": "Ran a capacity what-if estimate",
    "propose_action": "Drafted a proposal for your approval",
}


# --------------------------------------------------------------------------------------------- tool execution
def _session(sid: str) -> Any:
    from wiqaya.api.security import Session

    return Session(sid=sid, role="planner")


def _district_rows(population: str, sid: str) -> list[dict[str, Any]]:
    from wiqaya.api.routers import planner_districts

    rows: list[dict[str, Any]] = planner_districts(population=population, s=_session(sid))["data"]  # type: ignore[arg-type]
    return [{k: v for k, v in r.items() if k not in ("lat", "lon")} for r in rows]


def _check_district(district_id: str) -> dict[str, Any] | None:
    from wiqaya.common import config as C

    if district_id in C.districts():
        return None
    return {"error": f"Unknown district_id '{district_id}'.", "valid_district_ids": sorted(C.districts())}


def run_tool(name: str, args: dict[str, Any], sid: str, job: Job) -> dict[str, Any]:
    from wiqaya.api.routers import clean, planner_calibration, planner_compare, planner_equity, site_name
    from wiqaya.api.store import get_store
    from wiqaya.capacity.slots import sites

    s = _session(sid)
    if name == "get_district_need":
        pop = args.get("population", "all")
        return {"population": pop, "districts": _district_rows(pop if pop in POPULATIONS else "all", sid)}
    if name == "get_equity":
        r = planner_equity(policy="both", segment=args.get("segment", "nationality_group"), s=s)
        return {"segment": r["segment"], "rows": r["data"]}
    if name == "get_policy_comparison":
        data: dict[str, Any] = planner_compare(s=s)["data"]
        return data
    if name == "get_model_calibration":
        d = planner_calibration(s=s)["data"]
        return {m: {k: v for k, v in d[m].items() if k != "reliability"} for m in d}
    if name == "list_sites":
        if err := _check_district(args.get("district_id", "")):
            return err
        st = get_store()
        did = args["district_id"]
        cap = st.buckets.groupby(["site_id", "slot_type"]).capacity.sum()
        out = []
        for site in sites().values():
            if site.district_id != did:
                continue
            slots = {t: int(c) for (sid_, t), c in cap.items() if sid_ == site.id}
            out.append({"site_id": site.id, "name": site_name(site.id), "kind": site.kind,
                        "van_weekday": site.weekday, "hours": f"{site.open_time}-{site.close_time}",
                        "slots_12w_by_type": slots, "slots_12w_total": sum(slots.values())})  # fmt: skip
        result: dict[str, Any] = clean({"district_id": did, "sites": out})
        return result
    if name == "estimate_extra_capacity":
        return _estimate(args.get("district_id", ""), int(args.get("extra_slots_12w", 0)), sid)
    if name == "propose_action":
        if args.get("district_id") not in ("all", None) and (err := _check_district(args["district_id"])):
            return err
        if len(job.proposals) >= 3:
            return {"error": "At most 3 proposals per question."}
        p = {"id": "prop-" + secrets.token_hex(4), **{k: str(args.get(k, ""))[:600] for k in
             ("title", "action_type", "district_id", "rationale", "expected_effect")},
             "status": "pending_approval", "decided_by": None, "decided_at": None}  # fmt: skip
        job.proposals.append(p)
        return {"proposal_id": p["id"], "status": "pending_approval",
                "note": "Shown to the planner for approval. Nothing has changed yet."}  # fmt: skip
    return {"error": f"Unknown tool {name}"}


def _estimate(district_id: str, extra: int, sid: str) -> dict[str, Any]:
    from wiqaya.api.store import get_store

    if err := _check_district(district_id):
        return err
    if not 1 <= extra <= 1000:
        return {"error": "extra_slots_12w must be between 1 and 1000."}
    st = get_store()
    row = next(r for r in _district_rows("all", sid) if r["district_id"] == district_id)
    if row.get("suppressed") or row.get("unmet_need_per_1000") is None:
        return {"district_id": district_id, "error": "District figures are suppressed (n<11); no estimate."}
    unmet = round(row["unmet_need_per_1000"] * row["n"] / 1000)
    sim = st.simulation
    overall = float(sim["primary_endpoint"]["wiqaya"])
    rate = row.get("wiqaya_completed_per_100_contacts")
    rate_source = "district simulated rate"
    if not isinstance(rate, (int, float)):
        rate, rate_source = overall, "programme-wide simulated rate (district rate unavailable)"
    sens = [float(v["wiqaya_per_100"]) for v in sim.get("sensitivity", {}).values()]
    low_f = min(sens) / overall if sens else 0.8
    usable = min(extra, unmet)
    mid = usable * float(rate) / 100
    return {"district_id": district_id, "name": row["name"], "extra_slots_12w": extra,
            "unmet_people": unmet, "usable_extra_slots": usable,
            "completed_per_100_contacts_used": round(float(rate), 1), "rate_source": rate_source,
            "estimated_extra_completed": {"low": round(mid * low_f), "mid": round(mid), "high": round(mid * 1.1)},
            "method": "min(extra slots, unmet people) x completed per 100 contacts; low end scaled by the least "
                      "favourable sensitivity scenario; high end +10%. Rough estimate, not a re-simulation.",
            "label": "Simulated cohort"}  # fmt: skip


# --------------------------------------------------------------------------------------------- number check
_NUM = re.compile(r"(?<![\w-])\d[\d,]*(?:\.\d+)?")


def _numbers(obj: Any, out: list[float]) -> None:
    if isinstance(obj, bool):
        return
    if isinstance(obj, (int, float)):
        out.append(float(obj))
    elif isinstance(obj, dict):
        for v in obj.values():
            _numbers(v, out)
    elif isinstance(obj, list):
        for v in obj:
            _numbers(v, out)
    elif isinstance(obj, str):
        out.extend(float(m.replace(",", "")) for m in _NUM.findall(obj))


def check_numbers(answer: str, sources: list[Any], question: str) -> dict[str, Any]:
    """Every number in the answer should appear in a tool result (allowing rounding and proportion->percent)."""
    pool: list[float] = []
    for s in sources:
        _numbers(s, pool)
    _numbers(question, pool)
    found: list[str] = []
    unverified: list[str] = []
    for raw in _NUM.findall(answer):
        v = float(raw.replace(",", ""))
        if (v.is_integer() and v <= 12) or v in (100, 1000) or 2024 <= v <= 2030:  # counts, "per 100", years
            continue
        ok = any(abs(v - t) <= 0.051 or abs(v - round(t)) < 1e-9 or abs(v - 100 * t) <= 0.051 for t in pool)
        (found if ok else unverified).append(raw)
    return {"checked": len(found) + len(unverified), "verified": len(found),
            "unverified": sorted(set(unverified), key=unverified.index)}  # fmt: skip


# --------------------------------------------------------------------------------------------- jobs
@dataclass
class Job:
    id: str
    sid: str
    question: str
    status: str = "running"  # running | done | error
    steps: list[dict[str, Any]] = field(default_factory=list)
    answer: str = ""
    proposals: list[dict[str, Any]] = field(default_factory=list)
    number_check: dict[str, Any] | None = None
    error: str | None = None
    started: str = field(default_factory=lambda: datetime.now(UTC).isoformat(timespec="seconds"))
    seconds: float | None = None
    usage: dict[str, int] = field(default_factory=dict)
    model: str = MODEL

    def public(self) -> dict[str, Any]:
        return {k: v for k, v in self.__dict__.items() if k != "sid"}


class AgentStore:
    def __init__(self) -> None:
        self.jobs: dict[str, Job] = {}
        self.history: dict[str, list[Any]] = {}
        self.asked: dict[str, deque[float]] = defaultdict(deque)
        self.lock = threading.Lock()

    def allow(self, sid: str) -> bool:
        now = time.monotonic()
        with self.lock:
            q = self.asked[sid]
            while q and now - q[0] > 3600:
                q.popleft()
            if len(q) >= QUESTIONS_PER_HOUR:
                return False
            q.append(now)
            return True

    def busy(self, sid: str) -> bool:
        return any(j.sid == sid and j.status == "running" for j in self.jobs.values())

    def proposal(self, sid: str, pid: str) -> dict[str, Any] | None:
        for j in self.jobs.values():
            if j.sid == sid:
                for p in j.proposals:
                    if p["id"] == pid:
                        return p
        return None

    def reset(self, sid: str) -> None:
        with self.lock:
            self.history.pop(sid, None)


agents = AgentStore()


def start(sid: str, question: str, on_done: Any = None) -> Job:
    job = Job(id="job-" + secrets.token_hex(6), sid=sid, question=question)
    agents.jobs[job.id] = job
    threading.Thread(target=_run, args=(job, on_done), daemon=True).start()
    return job


def _run(job: Job, on_done: Any) -> None:
    import anthropic

    t0 = time.monotonic()
    sources: list[Any] = []
    client = anthropic.Anthropic(max_retries=2, timeout=180.0)
    messages: list[Any] = list(agents.history.get(job.sid, []))[-20:]
    messages.append({"role": "user", "content": job.question})
    try:
        for _ in range(MAX_STEPS):
            resp = client.beta.messages.create(  # type: ignore[call-overload]
                model=MODEL,
                max_tokens=16000,
                system=SYSTEM,
                tools=TOOLS,
                messages=messages,
                output_config={"effort": "medium"},
                cache_control={"type": "ephemeral"},
                betas=["server-side-fallback-2026-07-01"],
                fallbacks="default",
            )
            for k in ("input_tokens", "output_tokens", "cache_read_input_tokens"):
                job.usage[k] = job.usage.get(k, 0) + int(getattr(resp.usage, k, 0) or 0)
            if resp.stop_reason == "refusal":
                raise RuntimeError("The model declined this request. Try rephrasing the question.")
            messages.append({"role": "assistant", "content": resp.content})
            calls = [b for b in resp.content if b.type == "tool_use"]
            if resp.stop_reason == "pause_turn":
                continue
            if not calls:
                job.answer = "\n".join(b.text for b in resp.content if b.type == "text").strip()
                break
            results = []
            for b in calls:
                args = b.input if isinstance(b.input, dict) else {}
                try:
                    out = run_tool(b.name, args, job.sid, job)
                except Exception as e:  # tool bug: report to the model, not the user
                    out = {"error": f"{type(e).__name__}: {e}"}
                sources.append(out)
                job.steps.append({"tool": b.name, "label": TOOL_LABEL.get(b.name, b.name), "input": args,
                                  "error": out.get("error") if isinstance(out, dict) else None})  # fmt: skip
                results.append({"type": "tool_result", "tool_use_id": b.id, "content": json.dumps(out, default=str),
                                "is_error": bool(isinstance(out, dict) and out.get("error"))})  # fmt: skip
            messages.append({"role": "user", "content": results})
        else:
            job.answer = job.answer or "I stopped after the step limit before finishing. Try a narrower question."
        job.number_check = check_numbers(job.answer, sources, job.question)
        job.status = "done"
        agents.history[job.sid] = messages
    except anthropic.AuthenticationError:
        job.status, job.error = "error", "The Claude API key was rejected. Check ANTHROPIC_API_KEY."
    except anthropic.RateLimitError:
        job.status, job.error = "error", "The Claude API is rate-limiting requests. Try again in a minute."
    except anthropic.APIStatusError as e:
        job.status, job.error = "error", f"Claude API error ({e.status_code}). Try again shortly."
    except anthropic.APIConnectionError:
        job.status, job.error = "error", "Could not reach the Claude API. Check the network connection."
    except RuntimeError as e:
        job.status, job.error = "error", str(e)
    finally:
        job.seconds = round(time.monotonic() - t0, 1)
        if on_done:
            on_done(job)
