"""Fetch clinic/doctor/hospital locations in the Abu Dhabi emirate from the OSM Overpass API.

Writes ``content/reference/osm_clinics.geojson``: a FeatureCollection of Points whose properties are
only ``osm_type``, ``osm_id``, ``amenity`` and ``district_id`` (nearest district centroid within 25 km).
Names, brands and every other tag are deliberately dropped: we use OSM only for location density.

Usage: ``uv run python scripts/fetch_osm_clinics.py [--offline] [--force]``.
On network failure it prints a warning and exits 0; the app then uses ``clinics_fallback.yaml``.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from datetime import date
from pathlib import Path
from typing import Any

import httpx
import yaml

ROOT = Path(__file__).resolve().parents[1]
DISTRICTS = ROOT / "content" / "reference" / "districts.yaml"
OUT = ROOT / "content" / "reference" / "osm_clinics.geojson"
OVERPASS_URL = "https://overpass-api.de/api/interpreter"
USER_AGENT = "wiqaya-hackathon-prototype/0.1 (research)"
# Abu Dhabi Emirate admin boundary = OSM relation/3766481 -> Overpass area id 3600000000 + 3766481.
QUERY = """[out:json][timeout:120];
area(id:3603766481)->.emirate;
(
  node["amenity"~"^(clinic|doctors|hospital)$"](area.emirate);
  way["amenity"~"^(clinic|doctors|hospital)$"](area.emirate);
);
out center;"""
MAX_KM = 25.0


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi, dlmb = p2 - p1, math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlmb / 2) ** 2
    return 6371.0 * 2 * math.asin(math.sqrt(a))


def nearest_district(lat: float, lon: float, districts: list[dict[str, Any]]) -> str | None:
    best = min(districts, key=lambda d: haversine_km(lat, lon, d["lat"], d["lon"]))
    return best["id"] if haversine_km(lat, lon, best["lat"], best["lon"]) <= MAX_KM else None


def to_features(elements: list[dict[str, Any]], districts: list[dict[str, Any]]) -> list[dict[str, Any]]:
    feats = []
    for el in elements:
        lat = el.get("lat", el.get("center", {}).get("lat"))
        lon = el.get("lon", el.get("center", {}).get("lon"))
        if lat is None or lon is None:
            continue
        props = {
            "osm_type": el["type"],
            "osm_id": el["id"],
            "amenity": el.get("tags", {}).get("amenity"),
            "district_id": nearest_district(lat, lon, districts),
        }
        geom = {"type": "Point", "coordinates": [round(lon, 6), round(lat, 6)]}
        feats.append({"type": "Feature", "geometry": geom, "properties": props})
    feats.sort(key=lambda f: (f["properties"]["osm_type"], f["properties"]["osm_id"]))
    return feats


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--offline", action="store_true", help="do not hit the network; use the existing file")
    ap.add_argument("--force", action="store_true", help="re-fetch even if the output exists")
    args = ap.parse_args()

    if args.offline or (OUT.exists() and not args.force):
        if OUT.exists():
            print(f"{OUT.relative_to(ROOT)} exists; skipping fetch (use --force to refresh).")
        else:
            print("Offline and no OSM cache: the app will use clinics_fallback.yaml.")
        return 0

    districts = yaml.safe_load(DISTRICTS.read_text(encoding="utf-8"))["districts"]
    try:
        resp = httpx.post(OVERPASS_URL, data={"data": QUERY}, headers={"User-Agent": USER_AGENT}, timeout=180)
        resp.raise_for_status()
        elements = resp.json()["elements"]
    except (httpx.HTTPError, ValueError, KeyError) as exc:
        print(f"WARNING: Overpass fetch failed ({exc}); app will use clinics_fallback.yaml.", file=sys.stderr)
        return 0

    fc = {
        "type": "FeatureCollection",
        "properties": {
            "attribution": "© OpenStreetMap contributors, ODbL 1.0",
            "retrieved_on": date.today().isoformat(),
            "source": OVERPASS_URL,
            "query": QUERY,
            "note": "Names and all other tags stripped; locations only.",
        },
        "features": to_features(elements, districts),
    }
    OUT.write_text(json.dumps(fc, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    counts: dict[str, int] = {}
    for f in fc["features"]:
        key = f["properties"]["district_id"] or "(none)"
        counts[key] = counts.get(key, 0) + 1
    print(f"Wrote {len(fc['features'])} features to {OUT.relative_to(ROOT)}")
    for key, n in sorted(counts.items(), key=lambda kv: -kv[1]):
        print(f"  {key:20s} {n}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
