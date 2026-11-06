"""Loader B: flatten FHIR NDJSON -> Parquet -> DuckDB (the analytics read model).

FHIR is the system of record; these tables are derived from the same NDJSON that loads into HAPI.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import duckdb
import pandas as pd

from wiqaya.common import config as C
from wiqaya.common.paths import DUCKDB_PATH, NDJSON_DIR, PARQUET_DIR
from wiqaya.fhir import ndjson
from wiqaya.fhir.resources import EXT, GEO

GENOMIC_PANEL = "69548-6"


def _ext(res: dict[str, Any], name: str) -> Any:
    for e in res.get("extension", []):
        if e["url"] == EXT + name:
            for k, v in e.items():
                if k.startswith("value"):
                    return v
    return None


def _geo(exts: list[dict[str, Any]]) -> tuple[float | None, float | None]:
    for e in exts:
        if e["url"] == GEO:
            vals = {x["url"]: x["valueDecimal"] for x in e["extension"]}
            return vals["latitude"], vals["longitude"]
    return None, None


def _ref(r: dict[str, Any] | None) -> str | None:
    return r["reference"].split("/", 1)[1] if r else None


def reverse_maps() -> dict[str, dict[tuple[str, str], str]]:
    c = C.codes()
    systems = {**c["systems"], "local": c["local_system"]}
    out: dict[str, dict[tuple[str, str], str]] = {}
    for section in ("observations", "conditions", "vaccines"):
        m = {}
        for key, spec in c[section].items():
            for cd in spec["codings"]:
                m[(systems[cd["system"]], str(cd["code"]))] = key
        out[section] = m
    out["family_history"] = {(systems[v["system"]], v["code"]): k for k, v in c["family_history"].items()}
    out["encounter_types"] = {(c["local_system"], v): k for k, v in c["encounter_types"].items()}
    return out


def _key(cc: dict[str, Any], m: dict[tuple[str, str], str]) -> str | None:
    for cd in cc.get("coding", []):
        k = m.get((cd["system"], cd["code"]))
        if k:
            return k
    return None


def _local_code(cc_list: list[dict[str, Any]], prefix: str) -> str | None:
    for cc in cc_list:
        for cd in cc.get("coding", []):
            if str(cd.get("code", "")).startswith(prefix):
                return str(cd["code"])[len(prefix) :]
    return None


def flatten(src: Path = NDJSON_DIR) -> dict[str, pd.DataFrame]:
    rm = reverse_maps()
    T: dict[str, list[dict[str, Any]]] = {k: [] for k in (
        "people", "households", "relationships", "encounters", "observations", "conditions", "immunizations",
        "family_history", "genomic", "consents", "communications", "clinics", "van_stops")}  # fmt: skip
    for r in ndjson.read("Patient", src):
        lat, lon = _geo(r["address"][0].get("extension", []))
        T["people"].append({
            "id": r["id"], "given": r["name"][0]["given"][0], "family": r["name"][0]["family"], "sex": r["gender"],
            "birth_date": r["birthDate"], "district_id": r["address"][0]["district"], "lat": lat, "lon": lon,
            "preferred_language": r["communication"][0]["language"]["coding"][0]["code"],
            "assigned_clinic_id": _ref(r["generalPractitioner"][0]),
            "nationality_group": _ext(r, "nationality-group"), "literacy_proxy": _ext(r, "literacy-proxy"),
            "phone_type": _ext(r, "phone-type"), "insurance_tier": _ext(r, "insurance-tier"),
            "household_id": _ext(r, "household"), "housing_type": _ext(r, "housing-type"),
            "has_regular_clinic": _ext(r, "has-regular-clinic"), "role": _ext(r, "household-role"),
        })  # fmt: skip
    for r in ndjson.read("Group", src):
        lat, lon = _geo(r.get("extension", []))
        T["households"].append({
            "id": r["id"], "district_id": _ext(r, "district"), "housing_type": _ext(r, "housing-type"),
            "primary_language": _ext(r, "primary-language"), "nationality_group": _ext(r, "nationality-group"),
            "size": r["quantity"], "lat": lat, "lon": lon,
        })  # fmt: skip
    for r in ndjson.read("RelatedPerson", src):
        rel = _local_code(r["relationship"], "rel-")
        T["relationships"].append({"person_id": _ref(r["patient"]), "related_person_id": r["identifier"][0]["value"],
                                   "type": rel, "degree": _ext(r, "relationship-degree")})  # fmt: skip
    for r in ndjson.read("Encounter", src):
        T["encounters"].append({"id": r["id"], "person_id": _ref(r["subject"]), "date": r["period"]["start"],
                                "type": _key(r["type"][0], rm["encounter_types"]),
                                "clinic_id": _ref(r.get("serviceProvider")), "attended": True,
                                "scheduled_via": _ext(r, "scheduled-via")})  # fmt: skip
    for r in ndjson.read("Appointment", src):
        actors = [_ref(p["actor"]) for p in r["participant"]]
        T["encounters"].append({"id": r["id"], "person_id": actors[0], "date": r["start"][:10],
                                "type": _key(r["serviceType"][0], rm["encounter_types"]),
                                "clinic_id": _ext(r, "clinic"), "attended": False,
                                "scheduled_via": _ext(r, "scheduled-via")})  # fmt: skip
    for r in ndjson.read("Observation", src):
        pid, d, enc = _ref(r["subject"]), r["effectiveDateTime"][:10], _ref(r.get("encounter"))
        code = r["code"]["coding"][0]["code"]
        if code == GENOMIC_PANEL:
            comp = {c["code"]["coding"][0]["code"]: c for c in r["component"]}
            gene = next(c["valueCodeableConcept"]["text"] for k, c in comp.items() if k == "48018-6")
            variant = next(c["valueString"] for k, c in comp.items() if k == "obs-variant-ref")
            T["genomic"].append({"id": r["id"], "person_id": pid, "gene": gene, "variant": variant,
                                 "classification": r["valueCodeableConcept"]["coding"][0]["code"].replace("variant-", ""),
                                 "date": d})  # fmt: skip
            continue
        if code == "85354-9":
            for i, comp_ in enumerate(r["component"]):
                key = _key(comp_["code"], rm["observations"])
                T["observations"].append({"id": f"{r['id']}-{i}", "person_id": pid, "date": d, "key": key,
                                          "value": comp_["valueQuantity"]["value"], "encounter_id": enc})  # fmt: skip
            continue
        key = _key(r["code"], rm["observations"])
        value = r["valueQuantity"]["value"] if "valueQuantity" in r else r.get("valueInteger", 0)
        T["observations"].append({"id": r["id"], "person_id": pid, "date": d, "key": key, "value": float(value),
                                  "encounter_id": enc})  # fmt: skip
    for r in ndjson.read("Condition", src):
        T["conditions"].append({"id": r["id"], "person_id": _ref(r["subject"]), "key": _key(r["code"], rm["conditions"]),
                                "onset_date": r["onsetDateTime"][:10],
                                "verification": "confirmed" if r["verificationStatus"]["coding"][0]["code"] == "confirmed"
                                else "suspected"})  # fmt: skip
    for r in ndjson.read("Immunization", src):
        T["immunizations"].append({"id": r["id"], "person_id": _ref(r["patient"]),
                                   "vaccine": _key(r["vaccineCode"], rm["vaccines"]),
                                   "date": r["occurrenceDateTime"][:10]})  # fmt: skip
    role = {"PRN": "parent", "MTH": "mother", "FTH": "father", "SIB": "sibling"}
    for r in ndjson.read("FamilyMemberHistory", src):
        for cnd in r["condition"]:
            T["family_history"].append({"id": r["id"], "person_id": _ref(r["patient"]),
                                        "relative_type": role.get(r["relationship"]["coding"][0]["code"], "family"),
                                        "condition_key": _key(cnd["code"], rm["family_history"]),
                                        "onset_age": cnd.get("onsetAge", {}).get("value")})  # fmt: skip
    status = {"active": "granted", "rejected": "denied", "proposed": "not_asked"}
    for r in ndjson.read("Consent", src):
        T["consents"].append({"id": r["id"], "person_id": _ref(r["patient"]),
                              "category": _local_code(r["category"], "consent-"),
                              "status": status[r["status"]], "date": r["dateTime"][:10]})  # fmt: skip
    for r in ndjson.read("Communication", src):
        payload = r["payload"][0]["contentString"]
        T["communications"].append({
            "id": r["id"], "person_id": _ref(r["subject"]), "sent_at": r["sent"][:10],
            "channel": _local_code(r["medium"], "channel-"), "template_id": payload.split()[0].split(":", 1)[1],
            "language": _ext(r, "language"), "response": _ext(r, "response"), "policy": _ext(r, "policy"),
            "pathway": _ext(r, "pathway"), "simulated": True,
        })  # fmt: skip
    for r in ndjson.read("Organization", src):
        lat, lon = _geo(r["address"][0].get("extension", []))
        T["clinics"].append({"id": r["id"], "name": r["name"], "district_id": r["address"][0]["district"], "lat": lat,
                             "lon": lon, "indoor_mall_adjacent": _ext(r, "indoor-mall-adjacent")})  # fmt: skip
    for r in ndjson.read("Location", src):
        T["van_stops"].append({"id": r["id"], "name": r["name"], "district_id": r["address"]["district"],
                               "lat": r["position"]["latitude"], "lon": r["position"]["longitude"],
                               "weekday": _ext(r, "van-weekday")})  # fmt: skip
    dfs = {}
    for name, rows in T.items():
        df = pd.DataFrame(rows)
        sort_cols = [c for c in ("id", "person_id", "related_person_id") if c in df.columns]
        if not df.empty and sort_cols:
            df = df.sort_values(sort_cols, kind="mergesort").reset_index(drop=True)
        for col in ("date", "birth_date", "onset_date", "sent_at"):
            if col in df.columns:
                df[col] = pd.to_datetime(df[col]).dt.date
        dfs[name] = df
    return dfs


def write_parquet(dfs: dict[str, pd.DataFrame], out: Path = PARQUET_DIR) -> None:
    out.mkdir(parents=True, exist_ok=True)
    for name, df in dfs.items():
        df.to_parquet(out / f"{name}.parquet", index=False, engine="pyarrow")


def build_duckdb(parquet: Path = PARQUET_DIR, db_path: Path = DUCKDB_PATH) -> None:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    if db_path.exists():
        db_path.unlink()
    con = duckdb.connect(str(db_path))
    try:
        for p in sorted(parquet.glob("*.parquet")):
            con.execute(f"CREATE TABLE {p.stem} AS SELECT * FROM read_parquet('{p.as_posix()}')")
    finally:
        con.close()
