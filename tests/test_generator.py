"""Generator: determinism, personas, privacy of latent truth (PROMPT.md §4, working rule 3)."""

from __future__ import annotations

import hashlib
import json

import pytest

from wiqaya.fhir.ndjson import dumps
from wiqaya.fhir.resources import to_resources
from wiqaya.generator.personas import PERSONA_IDS
from wiqaya.generator.run import generate


def cohort_hash(c) -> str:
    h = hashlib.sha256()
    for _, res in to_resources(c):
        h.update(dumps(res).encode())
    h.update(json.dumps(c.latent, sort_keys=True, default=str).encode())
    return h.hexdigest()


def test_same_seed_is_byte_identical() -> None:
    assert cohort_hash(generate(7, 400)) == cohort_hash(generate(7, 400))


def test_different_seed_differs() -> None:
    assert cohort_hash(generate(7, 400)) != cohort_hash(generate(8, 400))


def test_personas_present_with_fixed_ids(small_cohort) -> None:
    ids = {p.id for p in small_cohort.people}
    assert set(PERSONA_IDS) <= ids
    father = next(p for p in small_cohort.people if p.id == "demo-001")
    assert (father.given, father.family, father.district_id) == ("Khalid", "Al-Hammadi", "khalifa_city")


def test_every_resource_tagged_simulated(small_cohort) -> None:
    for _, res in to_resources(small_cohort):
        assert any(t["code"] == "synthetic" for t in res["meta"]["tag"]), res["id"]


def test_household_first_structure(small_cohort) -> None:
    labour = [h for h in small_cohort.households if h.housing_type == "labour_accommodation"]
    assert labour, "expected labour-accommodation households"
    sizes = {h.size for h in labour if not h.id.startswith("hh-demo")}
    assert min(sizes) >= 4 and max(sizes) <= 12


def test_latent_truth_not_readable_by_engines() -> None:
    import types

    # Emulate a model/API module trying to read the hidden table.
    mod = types.ModuleType("wiqaya.models.fake")
    exec("from wiqaya.store import repo\ndef f():\n    return repo.load_latent()", mod.__dict__)
    with pytest.raises(PermissionError):
        mod.f()


@pytest.mark.slow
def test_full_cohort_hash_reproducible(tmp_path) -> None:
    a = cohort_hash(generate(42, 20000))
    b = cohort_hash(generate(42, 20000))
    assert a == b
