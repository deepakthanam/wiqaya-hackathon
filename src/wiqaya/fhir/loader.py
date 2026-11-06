"""Loader A: NDJSON -> HAPI FHIR via transaction bundles (<= 500 entries).

FHIR_LOAD=sample (default): all demo personas' households + random households until >= 2,000 people.
FHIR_LOAD=full: everyone. In a pilot this loader is replaced by a read from Malaffi via the same client.
"""

from __future__ import annotations

import os
import random
from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor
from typing import Any

import httpx

from wiqaya.common.paths import NDJSON_DIR
from wiqaya.fhir import ndjson

ORDER = ("Organization", "Location", "Patient", "Group", "RelatedPerson", "Encounter", "Appointment", "Observation",
         "Condition", "Immunization", "FamilyMemberHistory", "Consent", "Communication", "DetectedIssue")  # fmt: skip
BUNDLE = 500


def base_url() -> str:
    return os.environ.get("FHIR_BASE_URL", "http://localhost:8080/fhir").rstrip("/")


def _subject(res: dict[str, Any]) -> str | None:
    for key in ("subject", "patient"):
        if key in res:
            return str(res[key]["reference"].split("/", 1)[1])
    if res["resourceType"] == "Appointment":
        return str(res["participant"][0]["actor"]["reference"].split("/", 1)[1])
    if res["resourceType"] == "Patient":
        return str(res["id"])
    return None


def sample_people(mode: str, seed: int = 7, target: int = 2000) -> set[str] | None:
    if mode == "full":
        return None
    groups = list(ndjson.read("Group"))
    demo = [g for g in groups if g["id"].startswith("hh-demo")]
    rest = sorted((g for g in groups if not g["id"].startswith("hh-demo")), key=lambda g: g["id"])
    random.Random(seed).shuffle(rest)
    chosen: set[str] = set()
    for g in demo + rest:
        if len(chosen) >= target and not g["id"].startswith("hh-demo"):
            break
        chosen.update(m["entity"]["reference"].split("/", 1)[1] for m in g["member"])
    return chosen


def iter_resources(people: set[str] | None) -> Iterator[tuple[str, dict[str, Any]]]:
    for rtype in ORDER:
        for res in ndjson.read(rtype, NDJSON_DIR):
            if people is not None:
                if rtype == "Group":
                    if not all(m["entity"]["reference"].split("/", 1)[1] in people for m in res["member"]):
                        continue
                elif rtype not in ("Organization", "Location"):
                    subj = _subject(res)
                    if subj is not None and subj not in people:
                        continue
            yield rtype, res


def bundles(people: set[str] | None) -> Iterator[tuple[str, dict[str, Any]]]:
    current: list[dict[str, Any]] = []
    current_type = ""
    for rtype, res in iter_resources(people):
        if current and (rtype != current_type or len(current) >= BUNDLE):
            yield current_type, _bundle(current)
            current = []
        current_type = rtype
        current.append({"resource": res, "request": {"method": "PUT", "url": f"{rtype}/{res['id']}"}})
    if current:
        yield current_type, _bundle(current)


def _bundle(entries: list[dict[str, Any]]) -> dict[str, Any]:
    return {"resourceType": "Bundle", "type": "transaction", "entry": entries}


def load(mode: str | None = None, workers: int = 4) -> dict[str, Any]:
    mode = mode or os.environ.get("FHIR_LOAD", "sample")
    people = sample_people(mode)
    url = base_url()
    counts: dict[str, int] = {}
    errors: list[str] = []
    with httpx.Client(timeout=300, headers={"Content-Type": "application/fhir+json"}) as client:

        def post(item: tuple[str, dict[str, Any]]) -> tuple[str, int, str | None]:
            rtype, b = item
            r = client.post(url, json=b)
            return rtype, len(b["entry"]), None if r.status_code < 300 else f"{rtype}: {r.status_code} {r.text[:300]}"

        # Resource types load in dependency order; bundles within a type load in parallel.
        by_type: dict[str, list[tuple[str, dict[str, Any]]]] = {}
        for item in bundles(people):
            by_type.setdefault(item[0], []).append(item)
        with ThreadPoolExecutor(max_workers=workers) as pool:
            for rtype in ORDER:
                for t, n, err in pool.map(post, by_type.get(rtype, [])):
                    counts[t] = counts.get(t, 0) + n
                    if err:
                        errors.append(err)
    return {"mode": mode, "people": len(people) if people is not None else "all", "loaded": counts,
            "errors": errors[:5], "error_count": len(errors)}  # fmt: skip


def get(path: str) -> dict[str, Any]:
    with httpx.Client(timeout=10) as client:
        r = client.get(f"{base_url()}/{path}", headers={"Accept": "application/fhir+json"})
        r.raise_for_status()
        data: dict[str, Any] = r.json()
        return data
