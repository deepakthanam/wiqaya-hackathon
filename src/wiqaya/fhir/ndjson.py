"""FHIR NDJSON read/write (one file per resource type)."""

from __future__ import annotations

import json
from collections.abc import Iterable, Iterator
from pathlib import Path
from typing import Any

from wiqaya.common.paths import NDJSON_DIR


def dumps(res: dict[str, Any]) -> str:
    return json.dumps(res, ensure_ascii=False, separators=(",", ":"))


def write_all(resources: Iterable[tuple[str, dict[str, Any]]], out: Path = NDJSON_DIR) -> dict[str, int]:
    out.mkdir(parents=True, exist_ok=True)
    for old in out.glob("*.ndjson"):
        old.unlink()
    handles: dict[str, Any] = {}
    counts: dict[str, int] = {}
    try:
        for rtype, res in resources:
            if rtype not in handles:
                handles[rtype] = (out / f"{rtype}.ndjson").open("w", encoding="utf-8", newline="\n")
            handles[rtype].write(dumps(res) + "\n")
            counts[rtype] = counts.get(rtype, 0) + 1
    finally:
        for h in handles.values():
            h.close()
    return dict(sorted(counts.items()))


def read(rtype: str, base: Path = NDJSON_DIR) -> Iterator[dict[str, Any]]:
    path = base / f"{rtype}.ndjson"
    if not path.exists():
        return
    with path.open(encoding="utf-8") as fh:
        for line in fh:
            if line.strip():
                yield json.loads(line)
