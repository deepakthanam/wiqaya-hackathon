#!/usr/bin/env bash
# Push the Wiqaya API to a free Hugging Face Docker Space (D-049).
#
#   scripts/deploy/hf_space.sh <hf-username>/<space-name>
#   DRY_RUN=1 scripts/deploy/hf_space.sh x/y    # build the package in a temp folder, print it, push nothing
#
# Packages only COMMITTED files (git archive), so .env and API keys are never included.
# Git asks for credentials on push: your Hugging Face username, and a write token as the password.
set -euo pipefail

SPACE="${1:?usage: scripts/deploy/hf_space.sh <hf-username>/<space-name>}"
ROOT="$(git rev-parse --show-toplevel)"
REV="$(git -C "$ROOT" rev-parse --short HEAD)"
OUT="$(mktemp -d)"
[ "${DRY_RUN:-0}" = "1" ] || trap 'rm -rf "$OUT"' EXIT

if [ -n "$(git -C "$ROOT" status --porcelain -- src config content docs pyproject.toml uv.lock docker/api.Dockerfile)" ]; then
  echo "Note: uncommitted changes are NOT included; the Space gets commit $REV." >&2
fi

git -C "$ROOT" archive HEAD pyproject.toml uv.lock README.md src config content docs docker/api.Dockerfile \
  | tar -x -C "$OUT"
mv "$OUT/docker/api.Dockerfile" "$OUT/Dockerfile"
rmdir "$OUT/docker"

# Spaces run the container as user 1000: make /app (including data/ for the audit log) writable by that user,
# and start uvicorn from the virtualenv directly so no uv cache is needed at runtime.
cat >> "$OUT/Dockerfile" <<'EOF'

# ---- Hugging Face Space additions (scripts/deploy/hf_space.sh) ----
RUN useradd -m -u 1000 user && chown -R user /app
USER user
ENV HOME=/home/user
CMD ["sh", "-c", "exec /app/.venv/bin/uvicorn wiqaya.api.app:app --host 0.0.0.0 --port ${PORT:-8000} --proxy-headers --forwarded-allow-ips='*'"]
EOF

# A Space's README must start with its config block.
{
  cat <<'EOF'
---
title: Wiqaya API
emoji: 🩺
colorFrom: green
colorTo: gray
sdk: docker
app_port: 8000
pinned: false
short_description: Wiqaya prototype API. Synthetic data only.
---

> This Space runs the Wiqaya API only. Use the web app on Vercel. Health check: `/api/v1/healthz`.

EOF
  cat "$OUT/README.md"
} > "$OUT/README.space.md"
mv "$OUT/README.space.md" "$OUT/README.md"

if [ "${DRY_RUN:-0}" = "1" ]; then echo "$OUT"; exit 0; fi

cd "$OUT"
git init -q -b main
git add -A
git -c user.name="wiqaya-deploy" -c user.email="deploy@localhost" commit -q -m "Wiqaya API from commit $REV"
echo "Pushing commit $REV to https://huggingface.co/spaces/$SPACE ..."
git push --force "https://huggingface.co/spaces/$SPACE" main
echo "Done. Build log: https://huggingface.co/spaces/$SPACE?logs=build"
