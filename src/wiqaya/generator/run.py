"""Generator entry point: `make data SEED=42 N=20000`."""

from __future__ import annotations

import hashlib
import json
from datetime import date
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from wiqaya.common import config as C
from wiqaya.common.paths import DATA, HIDDEN_DIR, NDJSON_DIR, PARQUET_DIR
from wiqaya.fhir import ndjson
from wiqaya.fhir.resources import to_resources
from wiqaya.generator import personas
from wiqaya.generator.consent import build_consents
from wiqaya.generator.entities import Cohort
from wiqaya.generator.history import HistoryBuilder
from wiqaya.generator.latent import LatentBuilder
from wiqaya.generator.population import PopulationBuilder

STAGES = ("population", "latent", "consent", "history")


def stage_rngs(seed: int) -> dict[str, np.random.Generator]:
    """One independent generator per stage, so changing one stage does not reshuffle the others."""
    children = np.random.SeedSequence(seed).spawn(len(STAGES))
    return {name: np.random.default_rng(s) for name, s in zip(STAGES, children, strict=True)}


def generate(seed: int, n: int, t0: date | None = None) -> Cohort:
    t0 = t0 or C.t0()
    rng = stage_rngs(seed)
    c = Cohort()
    pb = PopulationBuilder(c, rng["population"], t0)
    personas.create_people(pb)  # pinned personas first, fixed ids
    pb.build(n)
    LatentBuilder(c, rng["latent"], t0).build()
    personas.apply_records(c, t0)
    build_consents(c, rng["consent"], t0)
    HistoryBuilder(c, rng["history"], t0).build()
    return c


def write_hidden(c: Cohort, out: Path = HIDDEN_DIR) -> None:
    """Latent ground truth: generator + evaluator only. Never loaded into DuckDB or HAPI."""
    out.mkdir(parents=True, exist_ok=True)
    rows = []
    for pid in sorted(c.latent):
        lt = c.latent[pid]
        row = {"person_id": pid}
        for k, v in sorted(lt.items()):
            row[k] = json.dumps(v, sort_keys=True) if isinstance(v, dict) else v
        rows.append(row)
    df = pd.DataFrame(rows)
    for col in df.columns:
        if df[col].dtype == object and col != "person_id":
            df[col] = df[col].astype(str)
    df.to_parquet(out / "latent_truth.parquet", index=False, engine="pyarrow")
    (out / "README.txt").write_text(
        "HIDDEN GROUND TRUTH. Read only by wiqaya.generator and wiqaya.evaluate.\n"
        "Never exposed to models, the API or the web app.\n",
        encoding="utf-8",
    )


def content_hash(base: Path = DATA) -> str:
    h = hashlib.sha256()
    for sub in (NDJSON_DIR, PARQUET_DIR, HIDDEN_DIR):
        for p in sorted(sub.glob("*")):
            if p.suffix in (".ndjson", ".parquet"):
                h.update(p.name.encode())
                h.update(p.read_bytes())
    return h.hexdigest()


def run(seed: int, n: int) -> dict[str, Any]:
    from wiqaya.store.flatten import build_duckdb, flatten, write_parquet

    c = generate(seed, n)
    counts = ndjson.write_all(to_resources(c))
    write_hidden(c)
    write_parquet(flatten())
    build_duckdb()
    return {"seed": seed, "n": len(c.people), "households": len(c.households), "resources": counts,
            "hash": content_hash()}  # fmt: skip
