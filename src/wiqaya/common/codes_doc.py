"""Generate docs/CODES.md from content/reference/codes.yaml (single source of truth)."""

from __future__ import annotations

from typing import Any

from wiqaya.common import config as C
from wiqaya.common.paths import DOCS
from wiqaya.rules.schema import load_rules


def _rows(section: dict[str, Any], systems: dict[str, str], local: str) -> list[str]:
    rows = []
    for key, spec in section.items():
        codings = spec.get("codings", [spec]) if isinstance(spec, dict) else []
        for cd in codings:
            sys_uri = local if cd["system"] == "local" else systems[cd["system"]]
            rows.append(f"| `{key}` | {sys_uri} | `{cd['code']}` | {cd['display']} |")
    return rows


def render() -> str:
    c = C.codes()
    systems, local = c["systems"], c["local_system"]
    out = [
        "# Code systems and codes",
        "",
        "Generated from `content/reference/codes.yaml` by `wiqaya docs-codes`. Do not edit by hand.",
        "",
        "Rule: a standard code (LOINC, SNOMED CT, CVX, HL7 v3) is used only where it was verified on",
        "tx.fhir.org or the publisher's site on 2026-11-07 (evidence: `content/reference/codes_verification.yaml`).",
        f"Everything else uses the local code system `{local}`.",
        "",
        "## Code systems",
        "",
        "| Name | URI |",
        "|---|---|",
        *[f"| {k} | {v} |" for k, v in systems.items()],
        f"| local | {local} |",
        "",
    ]
    for title, key in (("Observations", "observations"), ("Conditions", "conditions"),
                       ("Family history", "family_history"), ("Vaccines", "vaccines")):  # fmt: skip
        out += [f"## {title}", "", "| Key | System | Code | Display |", "|---|---|---|---|"]
        out += _rows(c[key], systems, local)
        out.append("")
    out += ["## Genomic findings (Observation)", "",
            "Modelled loosely on the HL7 FHIR Genomics Reporting IG: one `Observation` per finding with",
            "LOINC `69548-6` *Genetic variant assessment* and a component for the gene studied (`48018-6`).",
            "Variant references come from ClinVar and are **illustrative only**.", "",
            "| Part | System | Code | Display |", "|---|---|---|---|"]  # fmt: skip
    out += _rows(c["genomic"], systems, local)
    out += ["", "## Encounter types (local)", "", "| Key | Code |", "|---|---|"]
    out += [f"| `{k}` | `{v}` |" for k, v in c["encounter_types"].items()]
    out += ["", "## Family relationships (HL7 v3-RoleCode)", "", "| Internal type | Code |", "|---|---|"]
    out += [f"| `{k}` | `{v}` |" for k, v in c["relationships"].items()]
    out += ["", "## Care gaps (`DetectedIssue.code`, local)", "", "| Rule | Code |", "|---|---|"]
    out += [f"| {r.ref} | `{r.output_codes['gap_code'].replace('local:', '')}` |" for r in load_rules()]
    out += ["", "## Other local codes", "",
            "| Code | Use |", "|---|---|",
            "| `synthetic` | `meta.tag` on every resource: *Simulated cohort* |",
            "| `consent-<category>` | `Consent.category` per consent category (clinical_data, family_links, genomic, "
            "contact_sms, contact_whatsapp, contact_call, chw_visit) |",
            "| extension URLs under `http://wiqaya.health/StructureDefinition/` | person attributes (nationality group, "
            "literacy proxy, phone type, insurance tier, household, housing type), rule version, priority |",
            "", "## Not verified (local codes used instead)", "",
            "- Autism screening instrument result (M-CHAT LOINC not found)",
            "- Mammogram BI-RADS assessment category (LOINC not found)",
            "- Generic developmental screening result (only proprietary ASQ-specific LOINC codes exist)",
            "- CIN 2+ grouping (SNOMED has CIN 2 `285838002`; no single CIN 2+ concept; kept local)",
            "- Colorectal advanced neoplasia (SNOMED adenomatous polyp of colon `428054006` is narrower; kept local)",
            ""]  # fmt: skip
    return "\n".join(out)


def write() -> None:
    (DOCS / "CODES.md").write_text(render(), encoding="utf-8")
