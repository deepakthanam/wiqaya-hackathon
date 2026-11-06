#!/usr/bin/env bash
# Playwright smoke test (PROMPT.md §10). Starts the API (:8000) and web app (:3000) if they are not running.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PIDS=()
cleanup() { for p in "${PIDS[@]:-}"; do kill "$p" 2>/dev/null || true; done; }
trap cleanup EXIT

if ! curl -fsS localhost:8000/api/v1/healthz >/dev/null 2>&1; then
  (cd "$ROOT" && uv run uvicorn wiqaya.api.app:app --port 8000 >/dev/null 2>&1) & PIDS+=($!)
fi
if ! curl -fsS -o /dev/null localhost:3000 2>/dev/null; then
  (cd "$ROOT/web" && corepack pnpm dev >/dev/null 2>&1) & PIDS+=($!)
fi
for _ in $(seq 1 90); do
  if curl -fsS localhost:8000/api/v1/healthz >/dev/null 2>&1 && curl -fsS -o /dev/null localhost:3000 2>/dev/null; then break; fi
  sleep 2
done
cd "$ROOT/web"
corepack pnpm exec playwright install chromium >/dev/null
corepack pnpm e2e
