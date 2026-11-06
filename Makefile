# Wiqaya Makefile. Needs a POSIX shell (Linux/macOS, or Git Bash on Windows).
SHELL := bash
.DEFAULT_GOAL := help

SEED ?= 42
N ?= 20000
FHIR_LOAD ?= sample
HAPI_PORT ?= 8080
FHIR_BASE_URL ?= http://localhost:$(HAPI_PORT)/fhir
UV := uv run
export PYTHONIOENCODING := utf-8
export PYTHONUTF8 := 1
TODO := $(UV) wiqaya todo

.PHONY: help setup env up down logs wait-hapi fhir-metadata lint typecheck test test-all e2e \
        content-check data load gaps train simulate sensitivity evaluate api web demo synthea \
        licenses clean fetch-reference pipeline

help: ## List targets
	@grep -E '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) | awk 'BEGIN{FS=":.*?## "}{printf "  \033[36m%-15s\033[0m %s\n",$$1,$$2}'

env: ## Create .env from .env.example if missing
	@test -f .env || cp .env.example .env

setup: env ## Install Python deps (uv) [web deps arrive in M7]
	uv sync

# --- Services -------------------------------------------------------------------------------
up: env ## Start HAPI FHIR + Postgres and wait until HAPI answers
	docker compose up -d hapi-db hapi
	@$(MAKE) --no-print-directory wait-hapi

down: ## Stop all services (keeps volumes)
	docker compose --profile app down

logs: ## Tail HAPI logs
	docker compose logs -f hapi

wait-hapi: ## Wait (up to ~4 min) for the HAPI CapabilityStatement
	@echo "Waiting for HAPI at $(FHIR_BASE_URL)/metadata ..."
	@for i in $$(seq 1 120); do \
	  if curl -fsS -H 'Accept: application/fhir+json' "$(FHIR_BASE_URL)/metadata" 2>/dev/null | grep -q '"CapabilityStatement"'; then \
	    echo "HAPI is up."; exit 0; fi; sleep 2; done; \
	  echo "HAPI did not come up in time; see 'make logs'."; exit 1

fhir-metadata: ## Print a summary of the HAPI CapabilityStatement
	@curl -fsS -H 'Accept: application/fhir+json' "$(FHIR_BASE_URL)/metadata" | \
	  $(UV) python -c "import sys,json;c=json.load(sys.stdin);print(c['resourceType'],c.get('fhirVersion'),c.get('software',{}).get('name'),c.get('software',{}).get('version'))"

# --- Quality --------------------------------------------------------------------------------
lint: ## ruff (Python) [eslint arrives in M7]
	$(UV) ruff check src tests
	$(UV) ruff format --check src tests

typecheck: ## mypy (strict on rules, governance, api)
	$(UV) mypy

test: ## Fast unit tests
	$(UV) pytest

test-all: ## All tests including slow and integration
	$(UV) pytest -m ''

e2e: ## Playwright smoke test (M7)
	@$(TODO) e2e

# --- Pipeline (stubs until their milestone) ---------------------------------------------------
content-check: ## Validate rules, sources and message templates
	$(UV) python scripts/verify_sources.py $(if $(ONLINE),,--offline)
	$(UV) wiqaya content-check
	$(UV) pytest -q tests/test_messages.py tests/test_content.py

fetch-reference: ## Re-fetch OSM clinics and ClinVar (network)
	$(UV) python scripts/fetch_osm_clinics.py --force
	$(UV) python scripts/fetch_clinvar.py --force

data: ## Generate the synthetic cohort: make data SEED=42 N=20000
	$(UV) wiqaya data --seed $(SEED) --n $(N)

load: ## Load NDJSON into HAPI (FHIR_LOAD=sample|full); DuckDB is built by `make data`
	$(UV) wiqaya load --mode $(FHIR_LOAD)

gaps: ## Run the care-gap engine and family graph
	$(UV) wiqaya gaps

train: ## Train and calibrate models, rank, fairness floor, fit capacity
	$(UV) wiqaya train

simulate: ## Run baseline vs Wiqaya 12-week simulation (no sensitivity)
	$(UV) wiqaya simulate --no-sensitivity

sensitivity: ## Simulation + 3 alternative response-parameter sets
	$(UV) wiqaya simulate --sensitivity

evaluate: ## Write docs/EVALUATION.md
	$(UV) wiqaya evaluate

pipeline: ## data -> gaps -> train -> sensitivity -> evaluate (no HAPI)
	$(MAKE) --no-print-directory data
	$(MAKE) --no-print-directory train
	$(MAKE) --no-print-directory sensitivity
	$(MAKE) --no-print-directory evaluate

api: ## Run the API locally with reload (M6)
	$(UV) uvicorn wiqaya.api.app:app --reload --port 8000

web: ## Run the web app in dev mode (M7)
	@$(TODO) web

demo: ## Full demo from a clean clone (M8)
	@$(TODO) demo

synthea: ## Optional Synthea path (stretch)
	@$(TODO) synthea

licenses: ## Generate docs/THIRD_PARTY_LICENSES.md (M8)
	@$(TODO) licenses

clean: ## Remove generated data (keeps docker volumes)
	rm -rf data/ndjson data/parquet data/duckdb data/runs
