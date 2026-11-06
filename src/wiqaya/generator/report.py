"""Population summary report (PROMPT.md §4 acceptance): data/runs/<ts>/population_report.md."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd

from wiqaya.common import config as C
from wiqaya.common.paths import RUNS_DIR
from wiqaya.store import repo

LATENT = ["undiagnosed_t2d", "prediabetes", "hypertension", "dyslipidaemia", "fh_carrier", "hbb_carrier",
          "brca_carrier", "developmental_delay", "child_high_bmi", "cervical_cin2plus", "colorectal_advanced_neoplasia"]  # fmt: skip


def _table(df: pd.DataFrame) -> str:
    cols = list(df.columns)
    lines = ["| " + " | ".join(cols) + " |", "|" + "---|" * len(cols)]
    for row in df.itertuples(index=False):
        lines.append("| " + " | ".join(str(x) for x in row) + " |")
    return "\n".join(lines)


def write_report(meta: dict[str, Any], gaps: pd.DataFrame, gap_stats: dict[str, Any]) -> Path:
    t = repo.load(("people", "households", "consents", "conditions", "genomic"))
    latent = repo.load_latent()
    pop = C.cfg("population")
    people, hh = t["people"], t["households"]
    n = len(people)
    out = RUNS_DIR / datetime.now().strftime("%Y%m%dT%H%M%S")
    out.mkdir(parents=True, exist_ok=True)
    nat = people["nationality_group"].value_counts(normalize=True).rename("observed").to_frame()
    nat["config"] = pd.Series(pop["nationality_mix"])
    nat = nat.reset_index().rename(columns={"index": "group", "nationality_group": "group"}).round(3)
    sizes = hh.groupby("housing_type")["size"].describe()[["count", "mean", "min", "max"]].round(2).reset_index()
    size_dist = hh["size"].value_counts().sort_index().rename("households").reset_index()
    prev = pd.DataFrame({"condition": LATENT, "prevalence_%": [
        round(100 * latent[c].astype(str).str.lower().eq("true").mean(), 2) if c in latent else None for c in LATENT]})  # fmt: skip
    cons = t["consents"].groupby(["category", "status"]).size().unstack(fill_value=0)
    cons = (cons.div(cons.sum(axis=1), axis=0) * 100).round(1).reset_index()
    adults = people[pd.to_datetime(people["birth_date"]) <= pd.Timestamp(C.t0()) - pd.DateOffset(years=18)]
    overdue_people = gaps[gaps["status"].isin(["overdue", "followup_overdue", "missed"])]["person_id"].nunique()
    lines = [
        "# Population report — Simulated cohort", "",
        f"Seed `{meta['seed']}` · N = {n} people · {len(hh)} households · content hash `{meta['hash'][:16]}…`", "",
        "> Every record is synthetic. Numeric parameters are placeholder ASSUMPTIONS (config/population.yaml).", "",
        "## Nationality mix: observed vs config", "", _table(nat), "",
        "## Households by housing type", "", _table(sizes), "",
        "## Household size distribution", "", _table(size_dist), "",
        f"Adults: {len(adults)} ({100 * len(adults) / n:.1f}%). Labour-accommodation residents: "
        f"{(people['housing_type'] == 'labour_accommodation').mean() * 100:.1f}% (config "
        f"{pop['households']['labour_share_of_people'] * 100:.0f}%).", "",
        "## Latent condition prevalence (hidden ground truth, % of all people)", "", _table(prev), "",
        f"Genomic findings: {len(t['genomic'])} records for {t['genomic']['person_id'].nunique()} people "
        f"({100 * t['genomic']['person_id'].nunique() / n:.2f}% of cohort; target 1–2%).", "",
        "## Care gaps at T0", "",
        f"- People with at least one open gap: {gap_stats['people_with_gap']} "
        f"({100 * gap_stats['people_with_gap'] / n:.1f}%)",
        f"- People with at least one **overdue** gap: {overdue_people} ({100 * overdue_people / n:.1f}%)",
        f"- Excluded by consent (clinical_data not granted): {gap_stats['excluded_by_consent']}",
        "", "```json", json.dumps(gap_stats["by_rule"], indent=1), "```", "",
        "## Consent shares (% within category)", "", _table(cons), "",
    ]  # fmt: skip
    path = out / "population_report.md"
    path.write_text("\n".join(lines), encoding="utf-8")
    (out / "meta.json").write_text(json.dumps({**meta, "gap_stats": gap_stats}, indent=1, default=str),
                                   encoding="utf-8")  # fmt: skip
    return path
