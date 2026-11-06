"""Render the outreach message for a flag: template choice, slot filling, timing (PROMPT.md §6.5).

Deterministic templating is the default. The optional LLM paraphrase (LLM_ENABLED=true) may only fill slots or
rephrase structured reasons; its output is validated and falls back to the deterministic text on any failure.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from datetime import date, datetime, time
from typing import Any

from wiqaya.common import calendar as cal
from wiqaya.outreach.library import blocked_terms, load_library

PATHWAY_FALLBACK_AUDIENCE = {"caregiver_of_elder": "adult"}


@dataclass
class Rendered:
    template_id: str
    pathway: str
    audience: str
    channel: str
    language: str
    review_status: str
    text: str
    english_gloss: str
    rtl: bool
    send_at: str
    timing_notes: list[str] = field(default_factory=list)
    llm_used: bool = False
    clinician_approval_required: bool = False

    def as_dict(self) -> dict[str, Any]:
        return self.__dict__.copy()


def _short(clinic_name: str) -> str:
    return clinic_name.split("–")[-1].strip()[:14]


def label(language: str, section: str, key: str) -> str:
    lib = load_library()
    lab = lib.labels.get(language) or lib.labels["en"]
    v = lab.get(section, {}).get(key) or lib.labels["en"][section].get(key, key)
    return str(v)


def visit_label(language: str, milestone: str | None) -> str:
    if not milestone:
        return label(language, "pathway_labels", "wcv")
    if milestone.startswith("y"):
        return label(language, "visit_labels", "yearly").replace("{years}", milestone[1:])
    return label(language, "visit_labels", milestone)


def render(
    *,
    pathway: str,
    audience: str,
    channel: str,
    language: str,
    values: dict[str, Any],
    send_from: datetime,
    clinician_approval_required: bool = False,
) -> Rendered:
    lib = load_library()
    t = lib.get(pathway, audience, channel, language)
    if t is None and audience in PATHWAY_FALLBACK_AUDIENCE:
        audience = PATHWAY_FALLBACK_AUDIENCE[audience]
        t = lib.get(pathway, audience, channel, language)
    if t is None:
        language = "en"
        t = lib.get(pathway, audience, channel, "en")
    if t is None:
        raise KeyError(f"no template for {pathway}/{audience}/{channel}")
    text = t.render(values)
    en = lib.get(pathway, audience, channel, "en")
    gloss = t.english_gloss or (en.render(values) if en else text)
    if t.english_gloss:
        gloss = re.sub(r"\{([a-z_]+)\}", lambda m: str(values.get(m.group(1), m.group(0))), t.english_gloss)
    send_at, notes = cal.next_send_time(send_from)
    out = Rendered(t.id, pathway, audience, channel, language, t.review_status, text, " ".join(gloss.split()),
                   language in lib.matrix["rtl"], send_at.isoformat(timespec="minutes"), notes,
                   clinician_approval_required=clinician_approval_required)  # fmt: skip
    if os.environ.get("LLM_ENABLED", "false").lower() == "true":
        out = _llm_paraphrase(out, t)
    return out


def validate_llm_output(original: str, candidate: str, max_chars: int, language: str) -> bool:
    """Fence for optional LLM output: no new numbers, no blocklisted words, within length."""
    if not candidate or len(candidate) > max_chars:
        return False
    if set(re.findall(r"\d+", candidate)) - set(re.findall(r"\d+", original)):
        return False
    lib = load_library()
    probe = next(iter(t for t in lib.templates.values() if t.language == language))
    from dataclasses import replace

    return not blocked_terms(lib, replace(probe, text=candidate))


def _llm_paraphrase(out: Rendered, template: Any) -> Rendered:
    """Placeholder hook: no LLM provider is bundled. Any provider output must pass validate_llm_output."""
    return out


def default_send_time(d: date) -> datetime:
    return datetime.combine(d, time(10, 0))
