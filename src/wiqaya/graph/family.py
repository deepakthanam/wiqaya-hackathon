"""Consent-filtered family graph and cascade index links (PROMPT.md §6.2).

An edge is kept only when BOTH people granted `family_links` consent. Genomic findings count as an index
reason only when the index person granted `genomic` consent.
"""

from __future__ import annotations

from datetime import date
from typing import Any

import networkx as nx
import pandas as pd

from wiqaya.rules.schema import Rule
from wiqaya.rules.snapshot import CascadeLink

FIRST_DEGREE = {"mother": "parent", "father": "parent", "child": "child", "sibling": "sibling"}


def build_graph(relationships: pd.DataFrame, cmap: dict[tuple[str, str], str]) -> tuple[nx.Graph, dict[str, int]]:
    g = nx.Graph()
    stats = {"edges_total": 0, "edges_kept": 0, "edges_dropped_consent": 0}
    seen: set[tuple[str, str]] = set()
    for r in relationships.itertuples(index=False):
        a, b = r.person_id, r.related_person_id
        key = (min(a, b), max(a, b))
        if key in seen:
            # Keep the directed relation type from a's point of view as an edge attribute.
            if g.has_edge(a, b):
                g.edges[a, b].setdefault("rel", {})[(a, b)] = r.type
            continue
        seen.add(key)
        stats["edges_total"] += 1
        if cmap.get((a, "family_links")) == "granted" and cmap.get((b, "family_links")) == "granted":
            g.add_edge(a, b, rel={(a, b): r.type}, degree=int(r.degree))
            stats["edges_kept"] += 1
        else:
            stats["edges_dropped_consent"] += 1
    return g, stats


def index_people(
    rules: tuple[Rule, ...],
    genomic: pd.DataFrame,
    conditions: pd.DataFrame,
    cmap: dict[tuple[str, str], str],
    as_of: date,
) -> dict[str, list[tuple[str, date]]]:
    """person_id -> [(reason, date)] for every cascade rule's index criteria."""
    genes = {g for r in rules if r.cascade for g in r.cascade.index_genes}
    conds = {c for r in rules if r.cascade for c in r.cascade.index_conditions}
    out: dict[str, list[tuple[str, date]]] = {}
    for row in genomic.itertuples(index=False):
        if row.gene in genes and row.date <= as_of and cmap.get((row.person_id, "genomic")) == "granted":
            out.setdefault(row.person_id, []).append((f"gene:{row.gene}", row.date))
    for row in conditions.itertuples(index=False):
        if row.key in conds and row.verification == "confirmed" and row.onset_date <= as_of:
            out.setdefault(row.person_id, []).append((f"condition:{row.key}", row.onset_date))
    return out


def cascade_links(g: nx.Graph, index: dict[str, list[tuple[str, date]]]) -> dict[str, list[CascadeLink]]:
    """Walk degree-1 blood relatives of each index person in the consented graph."""
    links: dict[str, list[CascadeLink]] = {}
    for idx, reasons in index.items():
        if idx not in g:
            continue
        for nb in g.neighbors(idx):
            rel_from_index = g.edges[idx, nb]["rel"].get((idx, nb))
            relationship = FIRST_DEGREE.get(rel_from_index or "")
            if relationship is None:
                continue
            for reason, d in reasons:
                links.setdefault(nb, []).append(CascadeLink(idx, reason, relationship, d))
    return links


def neighbourhood(g: nx.Graph, person_id: str, depth: int = 2) -> dict[str, Any]:
    """Nodes/edges within `depth` hops (for the family-graph panel)."""
    if person_id not in g:
        return {"nodes": [person_id], "edges": [], "in_graph": False}
    nodes = nx.single_source_shortest_path_length(g, person_id, cutoff=depth)
    sub = g.subgraph(nodes)
    edges = []
    for a, b, data in sub.edges(data=True):
        edges.append({"source": a, "target": b, "type": data["rel"].get((a, b)) or data["rel"].get((b, a))})
    return {"nodes": sorted(nodes), "edges": edges, "in_graph": True}
