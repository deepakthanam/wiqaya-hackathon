"""Read-only data store for the API (loaded once from DuckDB + run outputs). Writes go to session overlays."""

from __future__ import annotations

import json
import os
from datetime import date
from functools import lru_cache
from typing import Any

import httpx
import networkx as nx
import pandas as pd

from wiqaya.common import config as C
from wiqaya.common.paths import DUCKDB_PATH, RUNS_DIR
from wiqaya.graph.family import build_graph
from wiqaya.rules.schema import Rule, load_rules
from wiqaya.store import repo


class Store:
    def __init__(self) -> None:
        names = ("people", "households", "relationships", "observations", "conditions", "genomic", "consents",
                 "family_history", "encounters", "immunizations")  # fmt: skip
        t = repo.load(names, DUCKDB_PATH)
        self.people: pd.DataFrame = t["people"]
        self.households: pd.DataFrame = t["households"]
        self.relationships: pd.DataFrame = t["relationships"]
        self.observations: pd.DataFrame = t["observations"]
        self.conditions: pd.DataFrame = t["conditions"]
        self.genomic: pd.DataFrame = t["genomic"]
        self.consents: pd.DataFrame = t["consents"]
        self.family_history: pd.DataFrame = t["family_history"]
        self.encounters: pd.DataFrame = t["encounters"]
        self.immunizations: pd.DataFrame = t["immunizations"]
        self.gaps = repo.read_table("care_gaps", DUCKDB_PATH)
        self.flags = repo.read_table("flags", DUCKDB_PATH)
        self.assignments = repo.read_table("assignments", DUCKDB_PATH)
        self.buckets = repo.read_table("capacity_buckets", DUCKDB_PATH)
        self.fairness_log = repo.read_table("fairness_log", DUCKDB_PATH)
        self.p = self.people.set_index("id", drop=False)
        self.flag_by_id = self.flags.set_index("flag_id", drop=False)
        self.flag_by_person = self.flags.set_index("person_id", drop=False)
        self.rules: dict[str, Rule] = {r.id: r for r in load_rules()}
        self.cmap = repo.consent_map(self.consents)
        self.graph: nx.Graph = build_graph(self.relationships, self.cmap)[0]
        self.as_of: date = C.t0()
        self.simulation: dict[str, Any] = self._json("simulation.json")
        self.models: dict[str, Any] = self._json("models.json")
        self.run_id = str(self.simulation.get("run_id", "unknown"))

    @staticmethod
    def _json(name: str) -> dict[str, Any]:
        p = RUNS_DIR / name
        return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}

    def age(self, pid: str) -> int:
        return int((self.as_of - self.p.at[pid, "birth_date"]).days // 365.25)

    def granted(self, pid: str, category: str) -> bool:
        return self.cmap.get((pid, category)) == "granted"

    def gaps_for(self, pid: str) -> pd.DataFrame:
        return self.gaps[self.gaps.person_id == pid]

    def household_members(self, hid: str) -> pd.DataFrame:
        return self.people[self.people.household_id == hid]


@lru_cache(maxsize=1)
def get_store() -> Store:
    return Store()


def hapi_patient(pid: str) -> tuple[dict[str, Any] | None, str]:
    """Person detail reads HAPI first (system of record); DuckDB is the fallback (banner shown)."""
    base = os.environ.get("FHIR_BASE_URL", "http://localhost:8080/fhir").rstrip("/")
    try:
        r = httpx.get(f"{base}/Patient/{pid}", timeout=1.5, headers={"Accept": "application/fhir+json"})
        if r.status_code == 200:
            data: dict[str, Any] = r.json()
            return data, "hapi"
        return None, "duckdb (not in FHIR sample load)" if r.status_code == 404 else "duckdb (FHIR server error)"
    except httpx.HTTPError:
        return None, "duckdb (FHIR server unavailable)"
