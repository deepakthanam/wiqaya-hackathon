"""Care-gap engine over a generated cohort: personas, consent, graph (PROMPT.md §6.1-6.2, §11)."""

from __future__ import annotations

import pandas as pd
import pytest

from wiqaya.rules.run import run_gaps


@pytest.fixture(scope="module")
def gaps(small_tables):
    df, stats = run_gaps(tables=small_tables)
    return df, stats


def _rules(df: pd.DataFrame, pid: str) -> dict[str, str]:
    sub = df[df.person_id == pid]
    return dict(zip(sub.rule_id, sub.status, strict=True))


def test_persona_gaps(gaps) -> None:
    df, _ = gaps
    assert _rules(df, "demo-002") == {"CERVICAL_SCREEN": "overdue"}
    d002 = df[(df.person_id == "demo-002")].iloc[0]
    assert 400 <= d002.days_overdue <= 450  # ~14 months
    assert _rules(df, "demo-003") == {"CASCADE_FH": "due"}
    assert _rules(df, "demo-004") == {"CASCADE_FH": "due", "WCV_SCHEDULE": "overdue"}
    assert "CASCADE_FH" in _rules(df, "demo-005")
    assert _rules(df, "demo-010") == {"ADULT_T2D_SCREEN": "overdue", "FOLLOWUP_PREDIABETES": "followup_overdue"}


def test_consent_edge_case_no_cascade(gaps) -> None:
    df, _ = gaps
    assert "CASCADE_FH" not in _rules(df, "demo-020")


def test_cascade_is_clinician_task(gaps) -> None:
    df, _ = gaps
    cascade = df[df.rule_id.str.startswith("CASCADE")]
    assert len(cascade) and cascade.requires_clinician.all()


def test_clinical_data_denied_gets_no_gaps(gaps, small_tables) -> None:
    df, stats = gaps
    c = small_tables["consents"]
    not_granted = set(c[(c.category == "clinical_data") & (c.status != "granted")].person_id)
    assert not_granted, "fixture should contain people without clinical_data consent"
    assert not set(df.person_id) & not_granted
    assert sum(stats["excluded_by_consent"].values()) == len(not_granted)


def test_gaps_version_pinned_and_traced(gaps) -> None:
    df, _ = gaps
    assert df.rule_ref.str.contains("@").all()
    assert (df.fields_read.str.len() > 2).all()


def test_family_graph_drops_unconsented_edges(gaps) -> None:
    _, stats = gaps
    assert stats["graph"]["edges_dropped_consent"] > 0


@pytest.mark.slow
def test_full_run_under_60s() -> None:
    _, stats = run_gaps()
    assert stats["people"] >= 20000
    assert stats["seconds"] < 60
