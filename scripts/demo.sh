#!/usr/bin/env bash
# `make demo`: from a clean clone to a running demo (PROMPT.md §1 rule 11, §14).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
start=$(date +%s)
make --no-print-directory setup
make --no-print-directory up
make --no-print-directory pipeline
make --no-print-directory load || echo "WARNING: FHIR sample load reported errors; person pages fall back to DuckDB."
echo "Pipeline ready in $(( $(date +%s) - start ))s. Starting API (:8000) and web (:3000)..."
uv run uvicorn wiqaya.api.app:app --port 8000 & API_PID=$!
trap 'kill $API_PID 2>/dev/null || true' EXIT
echo ""
echo "  Open http://localhost:3000 and click 'Continue as Guest'. Follow docs/DEMO_SCRIPT.md."
echo ""
cd web && corepack pnpm dev
