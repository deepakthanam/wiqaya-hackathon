"""`make content-check`: consistency checks across config, reference content, rules and messages."""

from __future__ import annotations

import re
from typing import Any

from wiqaya.common import config as C
from wiqaya.outreach.library import load_library, validate_library
from wiqaya.rules.schema import load_rules

CONFIGS = ("population", "simulation", "capacity", "calendar", "segments", "schedules")


def check_rules() -> tuple[list[str], list[dict[str, Any]]]:
    problems: list[str] = []
    report: list[dict[str, Any]] = []
    lib = load_library()
    codes = C.codes()
    obs_keys = set(codes["observations"])
    cond_keys = set(codes["conditions"])
    schedules = C.cfg("schedules")
    rules = load_rules()
    ids = [r.id for r in rules]
    if len(set(ids)) != len(ids):
        problems.append("duplicate rule ids")
    for r in rules:
        where = r.ref
        if not r.source.verified and r.status != "unverified_source":
            problems.append(f"{where}: source not verified but status is {r.status} (must be unverified_source)")
        if r.source.verified and not r.source.retrieved_on:
            problems.append(f"{where}: verified source needs retrieved_on")
        if not re.match(r"^https?://", r.source.url):
            problems.append(f"{where}: source url missing")
        if r.message_pathway is not None and r.message_pathway not in lib.matrix["pathways"]:
            problems.append(f"{where}: unknown message_pathway {r.message_pathway}")
        if r.message_pathway is None and r.id not in lib.matrix["no_templates_for_rules"]:
            problems.append(f"{where}: no message_pathway and not listed in no_templates_for_rules")
        if r.schedule_ref and r.schedule_ref not in schedules:
            problems.append(f"{where}: unknown schedule_ref {r.schedule_ref}")
        for f in (*r.data_required, *r.satisfied_by):
            if f.startswith("obs:") and f[4:] not in obs_keys:
                problems.append(f"{where}: unknown observation key {f}")
        for f in r.satisfied_by:
            if f not in r.data_required:
                problems.append(f"{where}: satisfied_by {f} not declared in data_required")
        for cnd in r.applies_to.exclude_conditions:
            if cnd not in cond_keys:
                problems.append(f"{where}: unknown condition {cnd}")
        if r.applies_to.exclude_conditions and "conditions" not in r.data_required:
            problems.append(f"{where}: exclude_conditions needs 'conditions' in data_required")
        report.append({"rule": where, "verified": r.source.verified, "status": r.status, "url": r.source.url})
    return problems, report


def check_reference() -> list[str]:
    problems: list[str] = []
    for name in CONFIGS:
        try:
            C.cfg(name)
        except Exception as exc:  # pragma: no cover - reported, not raised
            problems.append(f"config/{name}.yaml: {exc}")
    districts = C.districts()
    pop = C.cfg("population")
    for section in ("district_deprivation_proxy",):
        missing = set(districts) - set(pop[section])
        if missing:
            problems.append(f"population.{section} missing districts {sorted(missing)}")
    for group, weights in pop["district_weights_family"].items():
        unknown = set(weights) - set(districts)
        if unknown:
            problems.append(f"district_weights_family.{group}: unknown districts {sorted(unknown)}")
    mix = sum(pop["nationality_mix"].values())
    if abs(mix - 1.0) > 1e-6:
        problems.append(f"nationality_mix sums to {mix}")
    for c in C.clinics().values():
        if c["district_id"] not in districts:
            problems.append(f"clinic {c['id']}: unknown district")
    if set(C.names()) < set(pop["nationality_mix"]):
        problems.append("names missing for some nationality groups")
    cv = C.reference("clinvar_cache.json")
    if not cv.get("illustrative_only"):
        problems.append("clinvar_cache.json must be marked illustrative_only")
    return problems


def run() -> tuple[list[str], dict[str, Any]]:
    problems = check_reference()
    rp, report = check_rules()
    problems += rp
    lib = load_library()
    problems += validate_library(lib)
    summary = {
        "rules": len(report),
        "rules_verified": sum(1 for r in report if r["verified"]),
        "rules_unverified": [r["rule"] for r in report if not r["verified"]],
        "templates": len(lib.templates),
        "machine_draft_templates": sum(1 for t in lib.templates.values() if t.review_status == "machine_draft"),
        "languages": lib.languages(),
    }
    return problems, summary
