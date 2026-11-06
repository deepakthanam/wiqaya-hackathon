FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PYTHONUTF8=1 UV_LINK_MODE=copy
COPY --from=ghcr.io/astral-sh/uv:0.13.5 /uv /usr/local/bin/uv
RUN apt-get update && apt-get install -y --no-install-recommends libgomp1 && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY pyproject.toml uv.lock README.md ./
RUN uv sync --frozen --no-dev --no-install-project
COPY src ./src
COPY config ./config
COPY content ./content
COPY docs ./docs
RUN uv sync --frozen --no-dev

# Seed data is generated at build time with the fixed seed (PROMPT.md §13): same run for every visitor.
ARG SEED=42
ARG N=20000
RUN uv run --no-dev wiqaya data --seed ${SEED} --n ${N} \
 && uv run --no-dev wiqaya train \
 && uv run --no-dev wiqaya simulate --sensitivity \
 && uv run --no-dev wiqaya evaluate

EXPOSE 8000
CMD ["uv", "run", "--no-dev", "uvicorn", "wiqaya.api.app:app", "--host", "0.0.0.0", "--port", "8000"]
