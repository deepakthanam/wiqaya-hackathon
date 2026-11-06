"""Outreach message library: loading, validation and rendering of templates.

Templates are keyed by (pathway, audience, channel, language). Validation rules match
PROMPT.md §5.2 and are exercised by tests/test_messages.py and `make content-check`.
"""

from __future__ import annotations

import re
import string
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

from wiqaya.common.paths import MESSAGES_DIR

SLOT_RE = re.compile(r"\{([a-z_]+)\}")
REVIEW_STATUSES = {"source", "machine_draft", "native_reviewed"}


@dataclass(frozen=True)
class Template:
    id: str
    pathway: str
    audience: str
    channel: str
    language: str
    review_status: str
    max_chars: int
    slots: tuple[str, ...]
    decline_text: str
    text: str
    english_gloss: str | None = None

    @property
    def key(self) -> tuple[str, str, str, str]:
        return (self.pathway, self.audience, self.channel, self.language)

    def used_slots(self) -> set[str]:
        return set(SLOT_RE.findall(self.text))

    def render(self, values: dict[str, Any]) -> str:
        missing = self.used_slots() - set(values)
        if missing:
            raise KeyError(f"{self.id}/{self.language}: missing slot values {sorted(missing)}")
        return string.Formatter().vformat(self.text, (), {k: values[k] for k in self.used_slots()})


@dataclass
class Library:
    matrix: dict[str, Any]
    slot_lengths: dict[str, int]
    templates: dict[tuple[str, str, str, str], Template]
    labels: dict[str, dict[str, Any]]
    blocklists: dict[str, dict[str, list[str]]]
    problems: list[str] = field(default_factory=list)

    def get(self, pathway: str, audience: str, channel: str, language: str) -> Template | None:
        return self.templates.get((pathway, audience, channel, language))

    def languages(self) -> list[str]:
        return list(self.matrix["languages"])


def _load_yaml(path: Path) -> Any:
    with path.open(encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def channel_limit(matrix: dict[str, Any], channel: str, language: str) -> int:
    lim = matrix["limits"][channel]
    if isinstance(lim, dict):
        return int(lim[matrix["script"][language]])
    return int(lim)


def nominal_length(t: Template, slot_lengths: dict[str, int]) -> int:
    """Length of the text with every slot replaced by its nominal maximum length."""
    return len(SLOT_RE.sub(lambda m: "x" * slot_lengths.get(m.group(1), 20), t.text))


@lru_cache(maxsize=1)
def load_library(base: Path = MESSAGES_DIR) -> Library:
    matrix = _load_yaml(base / "matrix.yaml")
    slot_lengths = _load_yaml(base / "slots.yaml")["slots"]
    templates: dict[tuple[str, str, str, str], Template] = {}
    problems: list[str] = []
    labels: dict[str, dict[str, Any]] = {}
    blocklists: dict[str, dict[str, list[str]]] = {}
    for path in sorted((base / "templates").glob("*.yaml")):
        doc = _load_yaml(path)
        lang = doc["language"]
        for raw in doc["templates"]:
            t = Template(
                id=raw["id"],
                pathway=raw["pathway"],
                audience=raw["audience"],
                channel=raw["channel"],
                language=lang,
                review_status=raw.get("review_status", doc.get("review_status", "machine_draft")),
                max_chars=int(raw.get("max_chars", channel_limit(matrix, raw["channel"], lang))),
                slots=tuple(raw["slots"]),
                decline_text=raw["decline_text"],
                text=" ".join(str(raw["text"]).split()),
                english_gloss=raw.get("english_gloss"),
            )
            if t.key in templates:
                problems.append(f"duplicate template {t.key}")
            templates[t.key] = t
    for path in sorted((base / "labels").glob("*.yaml")):
        doc = _load_yaml(path)
        labels[doc["language"]] = doc
    for path in sorted((base / "blocklist").glob("*.yaml")):
        doc = _load_yaml(path)
        blocklists[doc["language"]] = {k: v for k, v in doc.items() if isinstance(v, list)}
    return Library(matrix, slot_lengths, templates, labels, blocklists, problems)


def _contains_term(text: str, term: str, language: str) -> bool:
    if language in ("en", "tl"):
        return re.search(rf"(?<![\w]){re.escape(term)}(?![\w])", text, flags=re.IGNORECASE) is not None
    # Non-Latin scripts: plain substring match (word boundaries are unreliable for these scripts).
    return term in text


def blocked_terms(lib: Library, t: Template) -> list[str]:
    """Blocklist hits for a template. English terms are checked in every language too."""
    text_wo_slots = SLOT_RE.sub(" ", t.text)
    hits: list[str] = []
    for lang in {t.language, "en"}:
        bl = lib.blocklists.get(lang, {})
        groups = ["diagnosis", "fear", "guilt"]
        if lib.matrix["pathways"][t.pathway].get("clinician_approved_only"):
            groups.append("cascade_extra")
        for g in groups:
            for term in bl.get(g, []):
                if _contains_term(text_wo_slots, term, lang if lang == t.language else "en"):
                    hits.append(f"{g}:{term}")
    return hits


def validate_library(lib: Library) -> list[str]:
    """Return a list of human-readable problems; empty means the library passes."""
    problems = list(lib.problems)
    m = lib.matrix
    allowed_slots = set(lib.slot_lengths)
    for pathway, spec in m["pathways"].items():
        channels = m["outreach_channels"] if spec["kind"] == "outreach" else m["confirmation_channels"]
        for audience in spec["audiences"]:
            for channel in channels:
                for lang in m["languages"]:
                    if (pathway, audience, channel, lang) not in lib.templates:
                        problems.append(f"missing template {pathway}/{audience}/{channel}/{lang}")
    for t in lib.templates.values():
        where = f"{t.id}[{t.language}]"
        if t.pathway not in m["pathways"]:
            problems.append(f"{where}: unknown pathway {t.pathway}")
            continue
        if t.review_status not in REVIEW_STATUSES:
            problems.append(f"{where}: bad review_status {t.review_status}")
        if t.language == m["source_language"] and t.review_status != "source":
            problems.append(f"{where}: English templates must be review_status=source")
        if t.language != m["source_language"] and t.review_status == "source":
            problems.append(f"{where}: non-English templates cannot be 'source'")
        used = t.used_slots()
        if not used <= set(t.slots):
            problems.append(f"{where}: undeclared slots {sorted(used - set(t.slots))}")
        if not set(t.slots) <= allowed_slots:
            problems.append(f"{where}: unknown slots {sorted(set(t.slots) - allowed_slots)}")
        limit = channel_limit(m, t.channel, t.language)
        if t.max_chars > limit:
            problems.append(f"{where}: max_chars {t.max_chars} exceeds channel limit {limit}")
        n = nominal_length(t, lib.slot_lengths)
        if n > min(t.max_chars, limit):
            problems.append(f"{where}: nominal length {n} > limit {min(t.max_chars, limit)}")
        if not t.decline_text or " ".join(t.decline_text.split()) not in t.text:
            problems.append(f"{where}: decline option '{t.decline_text}' not found in text")
        if m["pathways"][t.pathway].get("clinician_approved_only"):
            bad = set(t.slots) & set(m["cascade_forbidden_slots"])
            if bad:
                problems.append(f"{where}: cascade template uses forbidden slots {sorted(bad)}")
        hits = blocked_terms(lib, t)
        if hits:
            problems.append(f"{where}: blocklisted terms {hits}")
        if t.language != m["source_language"] and not t.english_gloss:
            problems.append(f"{where}: non-English template needs english_gloss")
    for lang in m["languages"]:
        if lang not in lib.labels:
            problems.append(f"missing labels file for {lang}")
        if lang not in lib.blocklists:
            problems.append(f"missing blocklist file for {lang}")
    en_labels = lib.labels.get("en", {})
    for lang, lab in lib.labels.items():
        for section in ("visit_labels", "pathway_labels", "words"):
            missing = set(en_labels.get(section, {})) - set(lab.get(section, {}))
            if missing:
                problems.append(f"labels[{lang}].{section} missing {sorted(missing)}")
    return problems
