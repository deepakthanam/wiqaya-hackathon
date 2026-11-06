"""Repository layer over the DuckDB read model. Engines read data only through here.

The hidden latent table is NOT in DuckDB; `load_latent` refuses callers outside generator/evaluate.
"""

from __future__ import annotations

import inspect
from pathlib import Path
from typing import Any

import duckdb
import pandas as pd

from wiqaya.common.paths import DUCKDB_PATH, HIDDEN_DIR

TABLES = ("people", "households", "relationships", "encounters", "observations", "conditions", "immunizations",
          "family_history", "genomic", "consents", "communications", "clinics", "van_stops")  # fmt: skip


def connect(path: Path = DUCKDB_PATH, read_only: bool = True) -> duckdb.DuckDBPyConnection:
    return duckdb.connect(str(path), read_only=read_only)


def load(tables: tuple[str, ...] = TABLES, path: Path = DUCKDB_PATH) -> dict[str, pd.DataFrame]:
    con = connect(path)
    try:
        existing = {r[0] for r in con.execute("SELECT table_name FROM information_schema.tables").fetchall()}
        return {t: _dates(con.execute(f"SELECT * FROM {t}").df()) for t in tables if t in existing}
    finally:
        con.close()


DATE_COLS = ("date", "birth_date", "onset_date", "sent_at", "due_date", "created_at")


def _dates(df: pd.DataFrame) -> pd.DataFrame:
    for col in DATE_COLS:
        if col in df.columns and len(df):
            df[col] = pd.to_datetime(df[col]).dt.date
    return df


def write_table(name: str, df: pd.DataFrame, path: Path = DUCKDB_PATH) -> None:
    con = connect(path, read_only=False)
    try:
        con.register("_df", df)
        con.execute(f"CREATE OR REPLACE TABLE {name} AS SELECT * FROM _df")
        con.unregister("_df")
    finally:
        con.close()


def read_table(name: str, path: Path = DUCKDB_PATH) -> pd.DataFrame:
    con = connect(path)
    try:
        return _dates(con.execute(f"SELECT * FROM {name}").df())
    finally:
        con.close()


ALLOWED_LATENT_READERS = ("wiqaya.generator", "wiqaya.evaluate", "wiqaya.simulate")


def load_latent(path: Path = HIDDEN_DIR / "latent_truth.parquet") -> pd.DataFrame:
    """Hidden ground truth. Only the generator, simulator and evaluator may read it."""
    caller = inspect.stack()[1].frame.f_globals.get("__name__", "")
    if not caller.startswith(ALLOWED_LATENT_READERS) and not caller.startswith("tests"):
        raise PermissionError(f"{caller} may not read latent ground truth")
    return pd.read_parquet(path)


def consent_map(consents: pd.DataFrame) -> dict[tuple[str, str], str]:
    return {(r.person_id, r.category): r.status for r in consents.itertuples(index=False)}


def granted(cmap: dict[tuple[str, str], str], pid: str, category: str) -> bool:
    return cmap.get((pid, category)) == "granted"


def records_by_person(df: pd.DataFrame) -> dict[str, list[Any]]:
    out: dict[str, list[Any]] = {}
    for row in df.itertuples(index=False):
        out.setdefault(row.person_id, []).append(row)
    return out
