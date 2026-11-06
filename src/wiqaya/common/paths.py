"""Repository paths used across the package."""

from __future__ import annotations

import os
from pathlib import Path

ROOT = Path(os.environ.get("WIQAYA_ROOT", Path(__file__).resolve().parents[3]))
CONFIG = ROOT / "config"
CONTENT = ROOT / "content"
RULES_DIR = CONTENT / "rules"
MESSAGES_DIR = CONTENT / "messages"
NAMES_DIR = CONTENT / "names"
REFERENCE_DIR = CONTENT / "reference"
DATA = Path(os.environ.get("WIQAYA_DATA", ROOT / "data"))
NDJSON_DIR = DATA / "ndjson"
PARQUET_DIR = DATA / "parquet"
HIDDEN_DIR = DATA / "hidden"  # latent ground truth: generator + evaluator only
DUCKDB_PATH = DATA / "duckdb" / "wiqaya.duckdb"
RUNS_DIR = DATA / "runs"
DOCS = ROOT / "docs"
