"""Per-session write overlay (PROMPT.md §13): decisions and preferences never touch the base data.

Each guest session gets its own overlay that expires after SESSION_TTL_MINUTES (default 120).
"""

from __future__ import annotations

import os
import threading
import time
from collections import deque
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from wiqaya.common.paths import DATA

TTL_SECONDS = int(os.environ.get("SESSION_TTL_MINUTES", "120")) * 60


@dataclass
class Overlay:
    created: float = field(default_factory=time.time)
    decisions: dict[str, dict[str, Any]] = field(default_factory=dict)
    preferences: dict[str, dict[str, Any]] = field(default_factory=dict)


class OverlayStore:
    def __init__(self) -> None:
        self._data: dict[str, Overlay] = {}
        self._lock = threading.Lock()

    def get(self, sid: str) -> Overlay:
        with self._lock:
            self._expire()
            if sid not in self._data:
                self._data[sid] = Overlay()
            return self._data[sid]

    def _expire(self) -> None:
        now = time.time()
        for k in [k for k, v in self._data.items() if now - v.created > TTL_SECONDS]:
            del self._data[k]


@dataclass(frozen=True)
class AuditEvent:
    ts: str
    actor_role: str
    session: str
    action: str
    entity: str
    entity_id: str
    fields_read: tuple[str, ...]


class AuditLog:
    """Append-only audit of person-level reads (memory ring + JSONL file)."""

    def __init__(self, maxlen: int = 5000) -> None:
        self._events: deque[AuditEvent] = deque(maxlen=maxlen)
        self._lock = threading.Lock()
        self.path = DATA / "audit" / "audit.jsonl"

    def write(self, role: str, session: str, action: str, entity: str, entity_id: str, fields: list[str]) -> None:
        import json

        ev = AuditEvent(datetime.now(UTC).isoformat(timespec="seconds"), role, session[:8], action, entity, entity_id,
                        tuple(sorted(set(fields))))  # fmt: skip
        with self._lock:
            self._events.append(ev)
            try:
                self.path.parent.mkdir(parents=True, exist_ok=True)
                with self.path.open("a", encoding="utf-8") as fh:
                    fh.write(json.dumps(ev.__dict__) + "\n")
            except OSError:
                pass

    def recent(self, limit: int = 100) -> list[dict[str, Any]]:
        with self._lock:
            return [e.__dict__ | {"fields_read": list(e.fields_read)} for e in list(self._events)[-limit:]][::-1]
