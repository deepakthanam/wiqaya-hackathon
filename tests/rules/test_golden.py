"""Golden cases: >= 5 per rule (due, not due, overdue, excluded, eligible early / follow-up)."""

from __future__ import annotations

from datetime import date, timedelta

import pytest

from wiqaya.rules.engine import evaluate
from wiqaya.rules.run import engine_context
from wiqaya.rules.schema import load_rules
from wiqaya.rules.snapshot import CascadeLink, FieldNotDeclaredError, PersonSnapshot, SnapshotView

T0 = date(2026, 11, 1)
RULES = {r.id: r for r in load_rules()}
CTX = engine_context(T0)


def days(n: int) -> date:
    return T0 - timedelta(days=n)


def months(m: float) -> date:
    return T0 - timedelta(days=round(m * 30.4375))


def person(age_years: float = 40, sex: str = "male", **kw) -> PersonSnapshot:
    s = PersonSnapshot("p-test", T0 - timedelta(days=round(age_years * 365.25)), sex)
    for k, v in kw.items():
        setattr(s, k, v)
    return s


def run(rule_id: str, s: PersonSnapshot):
    r = RULES[rule_id]
    return evaluate(r, SnapshotView(s, r.data_required), T0, CTX)


def status(rule_id: str, s: PersonSnapshot) -> str | None:
    g = run(rule_id, s)
    return g.status if g else None


def child(age_months: float, **kw) -> PersonSnapshot:
    return person(age_months / 12, **kw)


def visit_at(birth: date, m: float, offset_days: int = 5) -> date:
    return birth + timedelta(days=round(m * 30.4375) + offset_days)


CASES = [
    # ---- ADULT_T2D_SCREEN
    ("ADULT_T2D_SCREEN", "due-never", person(45, observations={"bmi": [(days(100), 28.0)]}), "overdue"),
    (
        "ADULT_T2D_SCREEN",
        "not-due-recent",
        person(45, observations={"bmi": [(days(100), 28.0)], "hba1c": [(days(200), 5.3)]}),
        None,
    ),
    (
        "ADULT_T2D_SCREEN",
        "due-soon",
        person(45, observations={"bmi": [(days(100), 28.0)], "hba1c": [(months(35.5), 5.3)]}),
        "due",
    ),
    (
        "ADULT_T2D_SCREEN",
        "excluded-t2d",
        person(45, conditions={"t2d": days(900)}, observations={"bmi": [(days(1), 30.0)]}),
        None,
    ),
    ("ADULT_T2D_SCREEN", "normal-bmi", person(45, observations={"bmi": [(days(10), 22.0)]}), None),
    (
        "ADULT_T2D_SCREEN",
        "early-fhx",
        person(28, observations={"bmi": [(days(10), 22.0)]}, family_history=frozenset({"t2d"})),
        "eligible_early",
    ),
    (
        "ADULT_T2D_SCREEN",
        "prediabetes-yearly",
        person(38, observations={"bmi": [(days(10), 29.0)], "hba1c": [(months(18), 6.1)]}),
        "overdue",
    ),
    # ---- ADULT_BP_SCREEN
    ("ADULT_BP_SCREEN", "never", person(30), "overdue"),
    ("ADULT_BP_SCREEN", "young-recent", person(30, observations={"sbp": [(months(20), 118)]}), None),
    ("ADULT_BP_SCREEN", "older-annual-overdue", person(50, observations={"sbp": [(months(20), 118)]}), "overdue"),
    ("ADULT_BP_SCREEN", "older-due-soon", person(50, observations={"sbp": [(months(11), 118)]}), "due"),
    ("ADULT_BP_SCREEN", "excluded-htn", person(50, conditions={"hypertension": days(400)}), None),
    ("ADULT_BP_SCREEN", "child", person(12), None),
    # ---- ADULT_LIPID_CVD
    ("ADULT_LIPID_CVD", "never", person(50), "overdue"),
    ("ADULT_LIPID_CVD", "recent", person(50, observations={"ldl": [(months(30), 120)]}), None),
    ("ADULT_LIPID_CVD", "due", person(50, observations={"ldl": [(months(59), 120)]}), "due"),
    ("ADULT_LIPID_CVD", "too-young", person(35), None),
    ("ADULT_LIPID_CVD", "excluded-fh", person(50, conditions={"fh": days(20)}), None),
    # ---- CERVICAL_SCREEN
    (
        "CERVICAL_SCREEN",
        "cytology-overdue",
        person(36, "female", observations={"cytology": [(months(50), 0)]}),
        "overdue",
    ),
    ("CERVICAL_SCREEN", "hpv-5y-ok", person(36, "female", observations={"hpv": [(months(50), 0)]}), None),
    ("CERVICAL_SCREEN", "recent", person(36, "female", observations={"cytology": [(months(12), 0)]}), None),
    ("CERVICAL_SCREEN", "male", person(36, "male"), None),
    ("CERVICAL_SCREEN", "too-old", person(70, "female"), None),
    ("CERVICAL_SCREEN", "excluded-cin", person(40, "female", conditions={"cin2plus": days(100)}), None),
    # ---- COLORECTAL_SCREEN
    ("COLORECTAL_SCREEN", "never", person(55), "overdue"),
    ("COLORECTAL_SCREEN", "fit-recent", person(55, observations={"fit": [(months(6), 0)]}), None),
    ("COLORECTAL_SCREEN", "fit-due", person(55, observations={"fit": [(months(11.5), 0)]}), "due"),
    ("COLORECTAL_SCREEN", "too-young", person(40), None),
    ("COLORECTAL_SCREEN", "excluded", person(60, conditions={"colorectal_neoplasia": days(50)}), None),
    # ---- BREAST_SCREEN
    ("BREAST_SCREEN", "never", person(50, "female"), "overdue"),
    ("BREAST_SCREEN", "recent", person(50, "female", observations={"mammogram": [(months(10), 1)]}), None),
    ("BREAST_SCREEN", "due", person(50, "female", observations={"mammogram": [(months(23.5), 1)]}), "due"),
    ("BREAST_SCREEN", "male", person(50, "male"), None),
    ("BREAST_SCREEN", "too-young", person(35, "female"), None),
    # ---- FOLLOWUP_PREDIABETES
    ("FOLLOWUP_PREDIABETES", "overdue", person(40, observations={"hba1c": [(months(18), 6.1)]}), "followup_overdue"),
    ("FOLLOWUP_PREDIABETES", "due-soon", person(40, observations={"hba1c": [(months(11), 6.0)]}), "due"),
    (
        "FOLLOWUP_PREDIABETES",
        "retested",
        person(40, observations={"hba1c": [(months(18), 6.1), (months(4), 5.5)]}),
        None,
    ),
    ("FOLLOWUP_PREDIABETES", "normal", person(40, observations={"hba1c": [(months(18), 5.4)]}), None),
    (
        "FOLLOWUP_PREDIABETES",
        "excluded-t2d",
        person(40, conditions={"t2d": days(10)}, observations={"hba1c": [(months(18), 6.2)]}),
        None,
    ),
    # ---- FOLLOWUP_BP_ELEVATED
    (
        "FOLLOWUP_BP_ELEVATED",
        "overdue",
        person(40, observations={"sbp": [(months(6), 134)], "dbp": [(months(6), 78)]}),
        "followup_overdue",
    ),
    (
        "FOLLOWUP_BP_ELEVATED",
        "dbp-trigger",
        person(40, observations={"sbp": [(months(1), 120)], "dbp": [(months(1), 84)]}),
        "due",
    ),
    (
        "FOLLOWUP_BP_ELEVATED",
        "normal",
        person(40, observations={"sbp": [(months(6), 118)], "dbp": [(months(6), 76)]}),
        None,
    ),
    (
        "FOLLOWUP_BP_ELEVATED",
        "rechecked-normal",
        person(
            40, observations={"sbp": [(months(6), 134), (months(2), 118)], "dbp": [(months(6), 82), (months(2), 75)]}
        ),
        None,
    ),
    (
        "FOLLOWUP_BP_ELEVATED",
        "excluded-htn",
        person(
            40,
            conditions={"hypertension": days(300)},
            observations={"sbp": [(months(6), 150)], "dbp": [(months(6), 95)]},
        ),
        None,
    ),
    # ---- CHILD_BMI_FOLLOWUP
    ("CHILD_BMI_FOLLOWUP", "overdue", person(8, observations={"bmi_pct": [(months(9), 97)]}), "followup_overdue"),
    ("CHILD_BMI_FOLLOWUP", "due", person(8, observations={"bmi_pct": [(months(4), 97)]}), "due"),
    (
        "CHILD_BMI_FOLLOWUP",
        "followed-up",
        person(8, observations={"bmi_pct": [(months(9), 97)]}, encounters={"chronic_review": [months(5)]}),
        None,
    ),
    ("CHILD_BMI_FOLLOWUP", "normal", person(8, observations={"bmi_pct": [(months(9), 60)]}), None),
    ("CHILD_BMI_FOLLOWUP", "adult", person(25, observations={"bmi_pct": [(months(9), 97)]}), None),
    # ---- CASCADE_FH
    (
        "CASCADE_FH",
        "child-of-index",
        person(4, cascade_links=(CascadeLink("i", "gene:LDLR", "child", days(40)),)),
        "due",
    ),
    (
        "CASCADE_FH",
        "sibling-tested-after",
        person(
            45,
            cascade_links=(CascadeLink("i", "condition:fh", "sibling", days(40)),),
            observations={"ldl": [(days(10), 150)]},
        ),
        None,
    ),
    (
        "CASCADE_FH",
        "sibling-tested-before",
        person(
            45,
            cascade_links=(CascadeLink("i", "condition:fh", "sibling", days(40)),),
            observations={"ldl": [(days(400), 150)]},
        ),
        "due",
    ),
    ("CASCADE_FH", "no-links", person(45), None),
    (
        "CASCADE_FH",
        "brca-link-ignored",
        person(45, cascade_links=(CascadeLink("i", "gene:BRCA1", "sibling", days(40)),)),
        None,
    ),
    # ---- CASCADE_BRCA
    (
        "CASCADE_BRCA",
        "adult-sibling",
        person(40, "female", cascade_links=(CascadeLink("i", "gene:BRCA2", "sibling", days(40)),)),
        "due",
    ),
    (
        "CASCADE_BRCA",
        "minor-child",
        person(12, cascade_links=(CascadeLink("i", "gene:BRCA1", "child", days(40)),)),
        None,
    ),
    (
        "CASCADE_BRCA",
        "fh-link-ignored",
        person(40, cascade_links=(CascadeLink("i", "gene:LDLR", "sibling", days(40)),)),
        None,
    ),
    (
        "CASCADE_BRCA",
        "adult-child",
        person(25, cascade_links=(CascadeLink("i", "gene:BRCA1", "child", days(40)),)),
        "due",
    ),
    ("CASCADE_BRCA", "no-links", person(40), None),
]


def _wcv_cases():
    b = child(52).birth_date  # 4y4m: 4-year visit window closed ~2 months ago
    yield ("WCV_SCHEDULE", "4y-overdue", child(52, encounters={"wcv": [visit_at(b, 36)]}), "overdue")
    b2 = child(48.5).birth_date
    yield ("WCV_SCHEDULE", "4y-due", child(48.5), "due")
    yield ("WCV_SCHEDULE", "4y-done", child(50, encounters={"wcv": [visit_at(child(50).birth_date, 48)]}), None)
    yield ("WCV_SCHEDULE", "adult", person(25), None)
    b3 = child(10).birth_date
    yield (
        "WCV_SCHEDULE",
        "infant-12m-upcoming",
        child(11, encounters={"wcv": [visit_at(child(11).birth_date, 9)]}),
        "due",
    )
    _ = (b2, b3)
    # DEV_SCREEN
    yield ("DEV_SCREEN", "18m-due", child(18), "due")
    yield (
        "DEV_SCREEN",
        "18m-done",
        child(19, observations={"dev_screen": [(visit_at(child(19).birth_date, 18), 0.0)]}),
        None,
    )
    yield ("DEV_SCREEN", "9m-overdue", child(13, observations={}), "overdue")
    yield ("DEV_SCREEN", "too-old", person(5), None)
    yield ("DEV_SCREEN", "30m-due", child(30), "due")
    # AUTISM_SCREEN
    yield ("AUTISM_SCREEN", "18m-due", child(18), "due")
    yield (
        "AUTISM_SCREEN",
        "24m-done",
        child(25, observations={"autism_screen": [(visit_at(child(25).birth_date, 24), 0.0)]}),
        None,
    )
    yield ("AUTISM_SCREEN", "24m-overdue", child(29), "overdue")
    yield ("AUTISM_SCREEN", "too-young", child(6), None)
    yield ("AUTISM_SCREEN", "too-old", person(4), None)
    # IMMUNISATION_CATCHUP
    full = {}
    c13 = child(13)
    import yaml

    from wiqaya.common.paths import CONFIG

    sched = yaml.safe_load((CONFIG / "schedules.yaml").read_text(encoding="utf-8"))["immunisation"]["doses"]
    for d in sched:
        when = visit_at(c13.birth_date, d["age_months"])
        if when < T0:
            full.setdefault(d["vaccine"], []).append(when)
    yield ("IMMUNISATION_CATCHUP", "complete", child(13, immunizations={k: list(v) for k, v in full.items()}), None)
    missing_mmr = {k: list(v) for k, v in full.items() if k != "mmr"}
    yield ("IMMUNISATION_CATCHUP", "missing-mmr", child(13, immunizations=missing_mmr), "overdue")
    yield ("IMMUNISATION_CATCHUP", "newborn-due", child(0.2), "due")
    yield ("IMMUNISATION_CATCHUP", "adult", person(30), None)
    yield ("IMMUNISATION_CATCHUP", "unvaccinated-infant", child(7), "overdue")


ALL = CASES + list(_wcv_cases())


@pytest.mark.parametrize(("rule_id", "name", "snap", "expected"), ALL, ids=[f"{c[0]}:{c[1]}" for c in ALL])
def test_golden(rule_id: str, name: str, snap: PersonSnapshot, expected: str | None) -> None:
    assert status(rule_id, snap) == expected


def test_at_least_five_cases_per_rule() -> None:
    counts: dict[str, int] = {}
    for c in ALL:
        counts[c[0]] = counts.get(c[0], 0) + 1
    assert set(counts) == set(RULES)
    assert min(counts.values()) >= 5, counts


def test_gap_is_traced_and_pinned() -> None:
    g = run("ADULT_T2D_SCREEN", person(45, observations={"bmi": [(days(100), 28.0)]}))
    assert g is not None
    assert g.rule_ref == "ADULT_T2D_SCREEN@1.0.0"
    assert "obs:hba1c" in g.fields_read and "birth_date" in g.fields_read
    assert g.evidence["bmi_latest"] == 28.0


def test_undeclared_field_is_refused() -> None:
    v = SnapshotView(person(40), ("birth_date",))
    with pytest.raises(FieldNotDeclaredError):
        v.get("genomic")


def test_engine_is_pure() -> None:
    s = person(45, observations={"bmi": [(days(100), 28.0)]})
    a, b = run("ADULT_T2D_SCREEN", s), run("ADULT_T2D_SCREEN", s)
    assert a == b
