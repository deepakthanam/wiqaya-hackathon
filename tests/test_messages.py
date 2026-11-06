"""Message library checks (PROMPT.md §5.2)."""

from __future__ import annotations

import pytest

from wiqaya.outreach.library import load_library, nominal_length, validate_library


@pytest.fixture(scope="module")
def lib():
    load_library.cache_clear()
    return load_library()


def test_library_has_no_problems(lib) -> None:
    problems = validate_library(lib)
    assert not problems, "\n".join(problems[:50]) + f"\n... {len(problems)} problems"


def test_every_language_complete(lib) -> None:
    m = lib.matrix
    for pathway, spec in m["pathways"].items():
        channels = m["outreach_channels"] if spec["kind"] == "outreach" else m["confirmation_channels"]
        for aud in spec["audiences"]:
            for ch in channels:
                for lang in m["languages"]:
                    assert lib.get(pathway, aud, ch, lang), (pathway, aud, ch, lang)


def test_render_fills_all_slots(lib) -> None:
    for t in lib.templates.values():
        values = {s: f"<{s}>" for s in t.slots}
        out = t.render(values)
        assert "{" not in out, t.id


def test_sms_within_two_segments(lib) -> None:
    for t in lib.templates.values():
        if t.channel == "sms":
            limit = 320 if lib.matrix["script"][t.language] == "latin" else 140
            assert nominal_length(t, lib.slot_lengths) <= limit, (t.id, t.language)


def test_cascade_never_names_relative(lib) -> None:
    forbidden = set(lib.matrix["cascade_forbidden_slots"])
    for t in lib.templates.values():
        if t.pathway == "cascade_family":
            assert not set(t.slots) & forbidden


def test_blocklist_catches_diagnosis_word(lib) -> None:
    from dataclasses import replace

    from wiqaya.outreach.library import blocked_terms

    t = lib.get("adult_t2d", "adult", "whatsapp", "en")
    bad = replace(t, text=t.text + " This is about diabetes.")
    assert any("diabetes" in h for h in blocked_terms(lib, bad))


def test_no_templates_for_brca(lib) -> None:
    assert "CASCADE_BRCA" in lib.matrix["no_templates_for_rules"]
    assert not any("brca" in t.pathway.lower() for t in lib.templates.values())
