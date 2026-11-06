"""Models, priority, fairness floor and capacity (PROMPT.md §6.3-6.4, Milestone 4)."""

from __future__ import annotations

from datetime import date

import numpy as np
import pandas as pd
import pytest

from wiqaya.capacity.fit import bundle_households, candidates, greedy
from wiqaya.capacity.slots import build_capacity
from wiqaya.models.fairness import apply_floor
from wiqaya.models.features import FEATURES_R, FORBIDDEN_R, risk_features
from wiqaya.models.priority import build_flags
from wiqaya.rules.run import run_gaps

T0 = date(2026, 11, 1)


def test_model_r_excludes_segments() -> None:
    assert not set(FEATURES_R) & FORBIDDEN_R
    assert "nationality_group" in FORBIDDEN_R and "preferred_language" in FORBIDDEN_R


def test_risk_features_have_no_segment_columns(small_tables) -> None:
    X = risk_features(small_tables, T0)
    assert not set(X.columns) & FORBIDDEN_R
    assert (X.age >= 18).all()


@pytest.fixture(scope="module")
def flags(small_tables):
    gaps, _ = run_gaps(tables=small_tables)
    people = small_tables["people"]
    rng = np.random.default_rng(0)
    adults = people[people.birth_date <= date(2008, 11, 1)].id
    risk = pd.Series(rng.random(len(adults)), index=adults.values)
    noshow = pd.Series(rng.random(people.id.nunique()), index=people.id.values)
    return gaps, build_flags(gaps, people, risk, noshow, {}, T0)


def test_every_gap_stays_on_worklist(flags) -> None:
    gaps, f = flags
    assert set(gaps.person_id) == set(f.person_id)
    assert f["rank"].tolist() == list(range(1, len(f) + 1))


def test_cascade_relatives_rank_high(flags) -> None:
    _, f = flags
    casc = f[f.top_pathway == "cascade"]
    assert len(casc) and (casc.risk_percentile >= 0.99).all()


def test_fairness_floor_met_and_logged(flags, small_tables) -> None:
    _, f = flags
    people = small_tables["people"]
    # Deliberately bias the ranking against one nationality group, then apply the floor.
    nat = f.person_id.map(people.set_index("id").nationality_group)
    biased = f.assign(priority=np.where(nat == "pakistani", f.priority - 1, f.priority))
    biased = biased.sort_values("priority", ascending=False).reset_index(drop=True)
    biased["rank"] = range(1, len(biased) + 1)
    k = len(biased) // 4
    out, log, report = apply_floor(biased, people, k, floor_ratio=0.8)
    assert log, "expected adjustments"
    assert all(e["dimension"] and e["promoted"] and e["demoted"] for e in log)
    assert report["nationality_group"]["pakistani"]["meets_floor"]
    assert sorted(out.flag_id) == sorted(biased.flag_id)  # nobody dropped


def test_capacity_respected_and_households_bundled(flags, small_tables) -> None:
    gaps, f = flags
    people = small_tables["people"]
    buckets = build_capacity(len(gaps), people, T0, 12)
    items = f.head(int(1.6 * buckets.capacity.sum()))
    cand = candidates(items, people, buckets)
    rows = pd.DataFrame(greedy(items, cand, buckets))
    rows, _ = bundle_households(rows, items, buckets)
    used = rows.merge(items[["flag_id", "slot_type"]], on="flag_id").groupby(["site_id", "week", "slot_type"]).size()
    cap = buckets.set_index(["site_id", "week", "slot_type"]).capacity
    assert all(v <= cap[k] for k, v in used.items())
    assert rows.flag_id.is_unique
