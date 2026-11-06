# Deployment

## Default target: a single Ubuntu VPS with Docker Compose and Caddy

```
Internet ──443──▶ Caddy (auto HTTPS) ──▶ web:3000 (Next.js) ──/api/v1──▶ api:8000 (FastAPI)
                                                                         │
                                                internal network only ──▶ hapi:8080 ──▶ hapi-db (Postgres)
```

- **HAPI is never published.** The deploy override removes its port, so only `api` and the one-off `loader` reach it on the internal network.
- **Seed data is generated at image build time** with the fixed seed (`SEED=42`, `N=20000`): data → gaps → train → simulate (with sensitivity) → evaluate. Every visitor sees the same run id.
- **The `loader` service** waits for HAPI, loads the FHIR sample (`FHIR_LOAD=sample`) and exits.

### Steps
1. Get a VPS with 4 vCPU and 16 GB RAM (8 GB works with `N=10000`), Ubuntu 24.04, Docker Engine and the Compose plugin. Point a DNS A record at it (e.g. `wiqaya.example.org`).
2. Clone the repository and create the environment file:
   ```bash
   cp .env.example .env
   # set: DOMAIN=wiqaya.example.org, SESSION_SECRET=$(openssl rand -hex 32), HAPI_DB_PASSWORD=<random>
   ```
3. Build and start:
   ```bash
   docker compose -f docker-compose.yml -f docker-compose.deploy.yml --profile app up -d --build
   ```
   The first build takes about 10 minutes, because it generates and trains on the synthetic cohort.
4. Open `https://$DOMAIN` and click **Continue as Guest**.

### Hardening in place
- Guest session creation is rate-limited (`GUEST_RATE_LIMIT`, default 30/min per IP).
- Sessions are signed cookies (HttpOnly, SameSite=Lax) that expire after 2 hours. Writes go to a per-session in-memory overlay.
- There are no admin write endpoints, no password store and no user accounts.
- Security headers come from the API, Next.js and Caddy: HSTS, nosniff, frame-deny, no-referrer, permissions policy.
- HAPI and Postgres sit on the internal network only. The Postgres password comes from `.env`.
- Logs: Caddy access logs; the API writes audit JSONL to `data/audit/`.

## Pilot path: Azure Container Apps in a UAE region
- Run the same images in a Container Apps environment in **UAE North**.
- **API:**
  - Internal ingress.
  - Data comes from a read-only **Malaffi FHIR** connection through the same `fhir/client` interface, replacing loader A.
- **Web:** external ingress behind Azure Front Door with a WAF.
- **HAPI FHIR:**
  - Swap HAPI for **Azure Health Data Services (FHIR R4)**, or keep HAPI on Azure Database for PostgreSQL.
  - Private endpoints only.
- **Secrets:** Azure Key Vault (session secret, DB credentials) through managed identity.
- **Read model:** DuckDB becomes Azure Synapse or Fabric over the FHIR export (`$export` → Parquet).
- **Governance:**
  - Microsoft Entra ID replaces guest access, with role mapping coordinator / clinician / planner / admin.
  - The audit log goes to Log Analytics.
  - Data residency stays in the UAE region.
  - A DOH data-protection impact assessment is needed before go-live.

## Local
```bash
make demo        # setup + HAPI + pipeline + FHIR sample load + API and web servers (about 10 min)
make e2e         # Playwright smoke test
```
