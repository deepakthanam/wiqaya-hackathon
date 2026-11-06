"""`make simulate` / `make sensitivity`: baseline vs Wiqaya over 12 weeks, plus sensitivity scenarios."""

from __future__ import annotations

import copy
import json
import time
from datetime import date
from typing import Any

import pandas as pd

from wiqaya.common import config as C
from wiqaya.common.paths import RUNS_DIR
from wiqaya.evaluate.metrics import policy_metrics, segment_metrics
from wiqaya.fhir.ndjson import dumps
from wiqaya.fhir.resources import cc, iso, meta
from wiqaya.simulate.engine import Simulator, latent_table
from wiqaya.store import repo

DETECTION_CODE = {"undiagnosed_t2d": "t2d", "prediabetes": "prediabetes", "hypertension": "hypertension",
                  "dyslipidaemia": "dyslipidaemia", "fh_carrier": "fh", "cervical_cin2plus": "cin2plus",
                  "colorectal_advanced_neoplasia": "colorectal_neoplasia", "developmental_delay": "developmental_delay"}  # fmt: skip


def load_inputs() -> dict[str, Any]:
    t = repo.load()
    return {
        "t": t,
        "gaps": repo.read_table("care_gaps"),
        "flags": repo.read_table("flags"),
        "assign": repo.read_table("assignments"),
        "buckets": repo.read_table("capacity_buckets"),
        "latent": latent_table(repo.load_latent()),
    }


def simulate_pair(inp: dict[str, Any], params: dict[str, Any], seed: int) -> dict[str, Any]:
    sim = Simulator(inp["t"], inp["gaps"], inp["flags"], inp["assign"], inp["buckets"], inp["latent"], params, seed)
    start = date.fromisoformat(C.cfg("simulation")["evaluation"]["start"])
    n_slots = int(inp["buckets"].capacity.sum())
    out = {}
    for policy in ("baseline", "wiqaya"):
        res = sim.run(policy)
        out[policy] = {"res": res,
                       "metrics": policy_metrics(res, inp["gaps"], inp["latent"], start, n_slots, len(inp["flags"]))}  # fmt: skip
    return out


def write_back(run_dir: Any, res: dict[str, Any], policy: str) -> int:
    """New diagnoses from the simulated period, as FHIR Condition resources (NDJSON)."""
    codes = C.codes()["conditions"]
    n = 0
    with (run_dir / f"detections_{policy}.ndjson").open("w", encoding="utf-8", newline="\n") as fh:
        for it in res["items"]:
            for d in it.detections:
                n += 1
                key = DETECTION_CODE[d]
                fh.write(dumps({
                    "resourceType": "Condition", "id": f"sim-{policy}-{n:06d}", "meta": meta(),
                    "verificationStatus": {"coding": [{"system": "http://terminology.hl7.org/CodeSystem/condition-ver-status",
                                                       "code": "provisional"}]},
                    "code": cc(codes[key]["codings"]), "subject": {"reference": f"Patient/{it.person_id}"},
                    "onsetDateTime": iso(it.attended_on) if it.attended_on else None,
                    "note": [{"text": f"Simulated detection under the {policy} policy (simulated cohort)."}],
                }) + "\n")  # fmt: skip
    return n


def run(sensitivity: bool = True) -> dict[str, Any]:
    t_start = time.perf_counter()
    cfg = C.cfg("simulation")
    seed = int(cfg["seeds"]["simulate"])
    inp = load_inputs()
    base_params = cfg["response_model"]
    main = simulate_pair(inp, base_params, seed)
    run_id = f"sim-seed{seed}"
    run_dir = RUNS_DIR / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    as_of = C.t0()
    result: dict[str, Any] = {"run_id": run_id, "label": "Simulated cohort", "as_of": as_of.isoformat(),
                              "weeks": cfg["evaluation"]["weeks"], "capacity_slots": int(inp["buckets"].capacity.sum()),
                              "policies": {}, "segments": {}}  # fmt: skip
    for policy, v in main.items():
        res = v["res"]
        res["comms"].to_parquet(run_dir / f"communications_{policy}.parquet", index=False)
        res["encounters"].to_parquet(run_dir / f"encounters_{policy}.parquet", index=False)
        v["metrics"]["detections_written_back"] = write_back(run_dir, res, policy)
        result["policies"][policy] = v["metrics"]
        result["segments"][policy] = segment_metrics(res, inp["gaps"], inp["t"]["people"], as_of)
        repo.write_table(f"sim_comms_{policy}", res["comms"].assign(run_id=run_id))
    b, w = result["policies"]["baseline"], result["policies"]["wiqaya"]
    result["primary_endpoint"] = {
        "name": "completed screenings/WCVs per 100 contacts",
        "baseline": b["completed_per_100_contacts"], "wiqaya": w["completed_per_100_contacts"],
        "difference": round(w["completed_per_100_contacts"] - b["completed_per_100_contacts"], 2),
    }  # fmt: skip
    if sensitivity:
        result["sensitivity"] = {}
        for name, override in cfg["sensitivity_scenarios"].items():
            params = copy.deepcopy(base_params)
            params.update(override)
            pair = simulate_pair(inp, params, seed)
            bm, wm = pair["baseline"]["metrics"], pair["wiqaya"]["metrics"]
            result["sensitivity"][name] = {
                "override": override,
                "baseline_per_100": bm["completed_per_100_contacts"], "wiqaya_per_100": wm["completed_per_100_contacts"],
                "difference": round(wm["completed_per_100_contacts"] - bm["completed_per_100_contacts"], 2),
                "baseline_gaps_closed_pct": bm["gaps_closed_pct"], "wiqaya_gaps_closed_pct": wm["gaps_closed_pct"],
                "baseline_fn_pct": bm["false_negative_rate_pct"], "wiqaya_fn_pct": wm["false_negative_rate_pct"],
            }  # fmt: skip
    result["seconds"] = round(time.perf_counter() - t_start, 1)
    text = json.dumps(result, indent=1, default=str)
    (run_dir / "metrics.json").write_text(text, encoding="utf-8")
    (RUNS_DIR / "simulation.json").write_text(text, encoding="utf-8")
    return result


def summary(result: dict[str, Any]) -> pd.DataFrame:
    keys = ["contacts", "people_contacted", "reach_pct", "completed_visits", "completed_per_100_contacts",
            "gaps_closed_pct", "median_days_to_attendance", "followup_completion_pct", "false_positive_rate_pct",
            "false_negative_rate_pct", "decline_optout_pct"]  # fmt: skip
    return pd.DataFrame({p: {k: result["policies"][p][k] for k in keys} for p in ("baseline", "wiqaya")})
