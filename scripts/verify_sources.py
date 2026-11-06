"""Re-fetch every rule's source URL and report whether it still resolves.

Usage: uv run python scripts/verify_sources.py [--offline]
Writes content/reference/source_check.json. A rule whose URL and verification_url both fail should be
set to `status: unverified_source` (content-check enforces the status/verified pairing).
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from wiqaya.rules.schema import load_rules  # noqa: E402

UA = "wiqaya-hackathon-prototype/0.1 (source verification)"
OUT = ROOT / "content" / "reference" / "source_check.json"


def fetch(client: httpx.Client, url: str) -> int:
    try:
        return client.get(url).status_code
    except httpx.HTTPError:
        return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--offline", action="store_true", help="skip network checks")
    args = ap.parse_args()
    if args.offline:
        print("offline: skipping URL checks (rules keep their recorded verification state)")
        return 0
    results = []
    with httpx.Client(follow_redirects=True, timeout=20, headers={"User-Agent": UA}) as client:
        for r in load_rules():
            primary = fetch(client, r.source.url)
            alt = fetch(client, r.source.verification_url) if r.source.verification_url else None
            ok = 200 <= primary < 300 or (alt is not None and 200 <= alt < 300)
            # 403 = publisher blocks automated clients; the recorded manual verification stands.
            state = "OK" if ok else ("BLOCKED" if primary == 403 else "FAIL")
            results.append(
                {
                    "rule": r.ref,
                    "url": r.source.url,
                    "status": primary,
                    "state": state,
                    "verification_url": r.source.verification_url,
                    "verification_status": alt,
                }
            )
            print(f"{state:7s} {r.ref:28s} {primary} {alt or ''}")
    OUT.write_text(json.dumps({"checked_on": date.today().isoformat(), "results": results}, indent=2), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
