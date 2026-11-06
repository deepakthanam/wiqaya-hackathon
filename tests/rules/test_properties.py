"""Hypothesis properties (PROMPT.md §10): age bounds and consent denial."""

from __future__ import annotations

from datetime import date, timedelta

from hypothesis import given, settings
from hypothesis import strategies as st

from wiqaya.rules.engine import evaluate
from wiqaya.rules.run import engine_context
from wiqaya.rules.schema import load_rules
from wiqaya.rules.snapshot import PersonSnapshot, SnapshotView

T0 = date(2026, 11, 1)
CTX = engine_context(T0)
AGE_BOUNDED = [r for r in load_rules() if r.applies_to.age_years is not None and r.kind != "cascade"]


def snapshot(age: float, sex: str, bmi: float, fhx: bool, last_days: int | None) -> PersonSnapshot:
    s = PersonSnapshot("p", T0 - timedelta(days=round(age * 365.25)), sex)
    s.observations = {"bmi": [(T0 - timedelta(days=30), bmi)], "bmi_pct": [(T0 - timedelta(days=200), 97.0)],
                      "hba1c": [(T0 - timedelta(days=400), 6.0)], "sbp": [(T0 - timedelta(days=200), 140.0)],
                      "dbp": [(T0 - timedelta(days=200), 90.0)]}  # fmt: skip
    if last_days is not None:
        s.observations["ldl"] = [(T0 - timedelta(days=last_days), 120.0)]
    s.family_history = frozenset({"t2d"} if fhx else set())
    return s


@settings(max_examples=300, deadline=None)
@given(
    rule_idx=st.integers(0, len(AGE_BOUNDED) - 1),
    age=st.floats(0, 100),
    sex=st.sampled_from(["female", "male"]),
    bmi=st.floats(15, 45),
    fhx=st.booleans(),
    last=st.one_of(st.none(), st.integers(1, 4000)),
)
def test_rule_never_fires_outside_age_bounds(rule_idx, age, sex, bmi, fhx, last) -> None:
    rule = AGE_BOUNDED[rule_idx]
    bounds = rule.applies_to.age_years
    assert bounds is not None
    # Early eligibility can lower the minimum age; widen the window accordingly.
    lo = min([bounds.min or 0] + [e.age_years.min or 0 for e in rule.eligible_early])
    hi = bounds.max if bounds.max is not None else 200
    gap = evaluate(rule, SnapshotView(snapshot(age, sex, bmi, fhx, last), rule.data_required), T0, CTX)
    if gap is not None:
        assert lo <= age <= hi, (rule.id, age)


@settings(max_examples=25, deadline=None)
@given(seed=st.integers(0, 10_000))
def test_clinical_data_denied_never_gets_gap(seed, small_tables) -> None:
    import pandas as pd

    from wiqaya.rules.run import run_gaps

    t = dict(small_tables)
    c = t["consents"].copy()
    rng = pd.Series(range(len(c))).sample(frac=1, random_state=seed).index
    # Deny clinical_data for a random third of people.
    people = sorted(set(c.person_id))
    denied = {people[i] for i in rng[: len(people) // 3] if i < len(people)}
    mask = (c.category == "clinical_data") & c.person_id.isin(denied)
    c.loc[mask, "status"] = "denied"
    t["consents"] = c
    df, _ = run_gaps(tables=t)
    actually_denied = set(c[(c.category == "clinical_data") & (c.status != "granted")].person_id)
    assert not set(df.person_id) & actually_denied
