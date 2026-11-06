"""Content checks: rules, sources, reference data (PROMPT.md §5, Milestone 1)."""

from wiqaya.common.content_check import run
from wiqaya.rules.schema import load_rules


def test_content_check_clean() -> None:
    problems, summary = run()
    assert not problems, problems
    assert summary["rules"] == 15


def test_every_rule_is_demo_encoding_or_flagged() -> None:
    for r in load_rules():
        assert r.status in ("demo_encoding_requires_clinical_validation", "unverified_source")
        assert r.source.name and r.source.year and r.source.url


def test_cascade_rules_require_clinician() -> None:
    for r in load_rules():
        if r.pathway == "cascade":
            assert r.requires_clinician
