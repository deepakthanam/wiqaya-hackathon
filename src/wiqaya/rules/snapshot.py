"""Person snapshots and field-guarded views.

A rule may only read the fields it declares in `data_required`. `SnapshotView` enforces this
and records every field read, so each care gap carries an exact `fields_read` trace.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Any

Obs = tuple[date, float]


@dataclass(frozen=True)
class CascadeLink:
    """A consented first-degree link from this person to an index person."""

    index_person_id: str
    reason: str  # e.g. "gene:LDLR" or "condition:fh"
    relationship: str  # parent | child | sibling (relationship of THIS person to the index)
    index_date: date


@dataclass
class PersonSnapshot:
    person_id: str
    birth_date: date
    sex: str
    conditions: dict[str, date] = field(default_factory=dict)  # code -> onset (confirmed only)
    observations: dict[str, list[Obs]] = field(default_factory=dict)  # key -> [(date, value)] ascending
    encounters: dict[str, list[date]] = field(default_factory=dict)  # attended encounters by type
    immunizations: dict[str, list[date]] = field(default_factory=dict)
    family_history: frozenset[str] = frozenset()
    genomic: tuple[tuple[str, str, date], ...] = ()  # (gene, classification, date); only if consented
    cascade_links: tuple[CascadeLink, ...] = ()


class FieldNotDeclaredError(PermissionError):
    pass


class SnapshotView:
    """Read-only view exposing only the declared fields; records what was read."""

    def __init__(self, snap: PersonSnapshot, allowed: tuple[str, ...]) -> None:
        self._s = snap
        self._allowed = set(allowed)
        self.fields_read: list[str] = []

    @property
    def person_id(self) -> str:
        return self._s.person_id

    def _check(self, name: str) -> None:
        if name not in self._allowed:
            raise FieldNotDeclaredError(f"field '{name}' not declared in data_required")
        if name not in self.fields_read:
            self.fields_read.append(name)

    def get(self, name: str) -> Any:
        self._check(name)
        if name.startswith("obs:"):
            return self._s.observations.get(name[4:], [])
        if name.startswith("enc:"):
            return self._s.encounters.get(name[4:], [])
        if name == "bmi_latest":
            bmi = self._s.observations.get("bmi", [])
            return bmi[-1][1] if bmi else None
        return getattr(self._s, name)

    def events(self, source: str) -> list[tuple[date, float | None]]:
        """Dated events for a `satisfied_by` source such as 'obs:hba1c' or 'enc:wcv'."""
        val = self.get(source)
        if source.startswith("enc:"):
            return [(d, None) for d in val]
        return list(val)
