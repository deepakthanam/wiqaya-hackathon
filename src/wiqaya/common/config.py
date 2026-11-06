"""Config and reference-content loaders (cached)."""

from __future__ import annotations

import json
from datetime import date
from functools import cache, lru_cache
from pathlib import Path
from typing import Any

import yaml

from wiqaya.common.paths import CONFIG, NAMES_DIR, REFERENCE_DIR


def load_yaml(path: Path) -> Any:
    with path.open(encoding="utf-8") as fh:
        return yaml.safe_load(fh)


@cache
def cfg(name: str) -> dict[str, Any]:
    """Load config/<name>.yaml."""
    data: dict[str, Any] = load_yaml(CONFIG / f"{name}.yaml")
    return data


@cache
def reference(name: str) -> Any:
    p = REFERENCE_DIR / name
    if p.suffix == ".json":
        return json.loads(p.read_text(encoding="utf-8"))
    return load_yaml(p)


@lru_cache(maxsize=1)
def districts() -> dict[str, dict[str, Any]]:
    return {d["id"]: d for d in reference("districts.yaml")["districts"]}


@lru_cache(maxsize=1)
def clinics() -> dict[str, dict[str, Any]]:
    return {c["id"]: c for c in reference("clinics_fallback.yaml")["clinics"]}


@lru_cache(maxsize=1)
def van_stops() -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for van in reference("clinics_fallback.yaml")["mobile_van"]:
        for s in van["stops"]:
            out[s["id"]] = {**s, "van_id": van["id"]}
    return out


@lru_cache(maxsize=1)
def names() -> dict[str, dict[str, list[str]]]:
    out = {}
    for p in sorted(NAMES_DIR.glob("*.yaml")):
        d = load_yaml(p)
        out[d["group"]] = d
    return out


@lru_cache(maxsize=1)
def codes() -> dict[str, Any]:
    data: dict[str, Any] = reference("codes.yaml")
    return data


def t0() -> date:
    return date.fromisoformat(cfg("population")["t0"])
