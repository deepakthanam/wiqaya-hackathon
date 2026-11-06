"""Fetch a few pathogenic ClinVar variant records per gene via NCBI E-utilities (illustrative only).

Writes ``content/reference/clinvar_cache.json`` with ``{gene, variation_id, name, clinical_significance}``
per record. Query syntax was checked on 2026-11-07 against ``einfo.fcgi?db=clinvar`` (fields GENE, PROP,
RVST) and the ClinVar help page, which documents ``"clinsig pathogenic"[Properties]`` (it also matches
"Pathogenic/Likely pathogenic" and related aggregate classifications). Expert-panel-reviewed records are
preferred; genes with fewer than ``PER_GENE`` such records fall back to any pathogenic record.

Usage: ``uv run python scripts/fetch_clinvar.py [--offline] [--force]``. On failure, writes gene-level
"illustrative variant" placeholders (if no cache exists) and exits 0. NCBI rate limit: <=3 requests/s.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import date
from pathlib import Path
from typing import Any

import httpx

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "content" / "reference" / "clinvar_cache.json"
EUTILS = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
HEADERS = {"User-Agent": "wiqaya-hackathon-prototype/0.1 (research)"}
GENES = ["LDLR", "APOB", "PCSK9", "BRCA1", "BRCA2", "HBB"]
PER_GENE = 5
QUERY_TEMPLATES = [
    '{gene}[gene] AND "clinsig pathogenic"[Properties] AND "reviewed by expert panel"[RVST]',
    '{gene}[gene] AND "clinsig pathogenic"[Properties]',
]
ACCEPTED = {"Pathogenic", "Pathogenic/Likely pathogenic"}
ATTRIBUTION = (
    "ClinVar, National Center for Biotechnology Information (NCBI), U.S. National Library of Medicine; "
    "https://www.ncbi.nlm.nih.gov/clinvar/. Illustrative reference only, not for clinical use."
)


class Client:
    """Tiny E-utilities client that keeps under 3 requests/second."""

    def __init__(self) -> None:
        self._http = httpx.Client(headers=HEADERS, timeout=30)
        self._last = 0.0

    def get(self, tool: str, **params: Any) -> dict[str, Any]:
        wait = 0.4 - (time.monotonic() - self._last)
        if wait > 0:
            time.sleep(wait)
        self._last = time.monotonic()
        resp = self._http.get(f"{EUTILS}/{tool}.fcgi", params={"db": "clinvar", "retmode": "json", **params})
        resp.raise_for_status()
        return resp.json()


def fetch_gene(client: Client, gene: str) -> list[dict[str, Any]]:
    found: dict[str, dict[str, Any]] = {}
    for template in QUERY_TEMPLATES:
        ids = client.get("esearch", term=template.format(gene=gene), retmax=25)["esearchresult"]["idlist"]
        if not ids:
            continue
        result = client.get("esummary", id=",".join(ids))["result"]
        for uid in result.get("uids", []):
            rec = result[uid]
            sig = rec.get("germline_classification", {}).get("description", "")
            # Skip multi-gene CNVs and anything not plainly pathogenic.
            if rec.get("gene_sort") != gene or sig not in ACCEPTED or uid in found:
                continue
            found[uid] = {
                "gene": gene,
                "variation_id": uid,
                "accession": rec.get("accession_version"),
                "name": rec.get("title"),
                "clinical_significance": sig,
                "review_status": rec["germline_classification"].get("review_status"),
            }
            if len(found) >= PER_GENE:
                return list(found.values())
    return list(found.values())


def fallback() -> dict[str, list[dict[str, Any]]]:
    return {
        g: [
            {
                "gene": g,
                "variation_id": None,
                "name": "illustrative variant",
                "clinical_significance": "Pathogenic (illustrative)",
            }
        ]
        for g in GENES
    }


def write(genes: dict[str, list[dict[str, Any]]], live: bool) -> None:
    payload = {
        "retrieved_on": date.today().isoformat(),
        "source": "NCBI ClinVar via E-utilities" if live else "fallback (fetch failed)",
        "attribution": ATTRIBUTION,
        "illustrative_only": True,
        "query_template": QUERY_TEMPLATES[0] + "  (fallback: " + QUERY_TEMPLATES[1] + ")",
        "genes": genes,
    }
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--offline", action="store_true", help="do not hit the network; use the existing file")
    ap.add_argument("--force", action="store_true", help="re-fetch even if the output exists")
    args = ap.parse_args()

    if OUT.exists() and (args.offline or not args.force):
        print(f"{OUT.relative_to(ROOT)} exists; skipping fetch (use --force to refresh).")
        return 0
    if args.offline:
        write(fallback(), live=False)
        print("Offline and no cache: wrote illustrative gene-level placeholders.")
        return 0

    client = Client()
    try:
        genes = {g: fetch_gene(client, g) for g in GENES}
    except (httpx.HTTPError, ValueError, KeyError) as exc:
        print(f"WARNING: ClinVar fetch failed ({exc}); writing illustrative placeholders.", file=sys.stderr)
        write(fallback(), live=False)
        return 0
    for g, recs in genes.items():
        if not recs:
            genes[g] = fallback()[g]
    write(genes, live=True)
    for g, recs in genes.items():
        print(f"  {g:6s} {len(recs)} records")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
