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
   # optional AI planner analyst: ANTHROPIC_API_KEY=<key> (leave empty to keep it off)
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
- Security headers come from the API, Next.js and Caddy: HSTS, nosniff, frame-deny, a referrer policy (origin only across sites, which OpenStreetMap tiles require), permissions policy.
- HAPI and Postgres sit on the internal network only. The Postgres password comes from `.env`.
- Logs: Caddy access logs; the API writes audit JSONL to `data/audit/`.

## Hackathon public URL: web on Vercel, API on a container host (D-047)

```
Browser ──▶ Vercel (Next.js, web/) ──rewrite /api/v1/*──▶ API container (FastAPI, docker/api.Dockerfile)
```

Vercel hosts the web app only. The API cannot run as Vercel serverless functions:
- it keeps guest sessions, the write overlay and analyst jobs in memory;
- analyst jobs run in a background thread after the request returns;
- it needs the generated read model (about 30 MB) and the trained models.

So the API runs as one long-lived container. Railway, Render and Fly.io all build `docker/api.Dockerfile` as it is. Choose a plan with **at least 1 GB RAM**: the API uses about 350 MB, and the image build trains the models. Run **exactly one instance**, because sessions live in memory.

The browser only ever talks to the Vercel domain. Next.js proxies `/api/v1/*` to `API_ORIGIN`, so the session cookie stays first-party and no CORS setup is needed. HAPI FHIR is not needed for the public demo: the consoles read the DuckDB read model.

### Step 1: API container (Railway shown; Render and Fly.io are similar)
1. In Railway, choose **New project → Deploy from GitHub repo** and pick `deepakthanam/wiqaya-hackathon`.
2. In the service settings, set **Dockerfile path** to `docker/api.Dockerfile`. Leave the root directory empty.
3. Under **Variables**, set:
   - `SESSION_SECRET` = a random 64-character hex string (`openssl rand -hex 32`);
   - optionally, for the AI analyst: `ANTHROPIC_API_KEY`, `AGENT_MODEL=claude-haiku-5-5`, `AGENT_QUESTIONS_PER_HOUR=15`.
4. Under **Networking**, choose **Generate domain**. The container listens on `$PORT`.
5. The first build takes about 10 minutes, because it generates and trains on the cohort. When it finishes, check that `https://<api-domain>/api/v1/healthz` returns `{"status":"ok",...}`.

### Step 2: web on Vercel
1. In Vercel, choose **Add New → Project** and import `deepakthanam/wiqaya-hackathon`.
2. Set **Root Directory** to `web`. Vercel detects Next.js and pnpm (from `packageManager`).
3. Add the environment variable `API_ORIGIN` = `https://<api-domain>`, with no trailing slash, for Production and Preview.
4. Click **Deploy**. Rewrites are fixed at build time, so if `API_ORIGIN` changes later, redeploy.
5. Open the Vercel URL and click **Continue as Guest**.

With the CLI instead: run `npm i -g vercel`, then `cd web`, `vercel link`, `vercel env add API_ORIGIN production` and `vercel --prod`.

### Notes
- **Cost control:** the analyst is off unless `ANTHROPIC_API_KEY` is set on the API service. Each question costs a fraction of a cent on Haiku. `AGENT_QUESTIONS_PER_HOUR` limits each session. To cap spend, also set a monthly limit in the Anthropic console.
- **Restarts:** a redeploy clears guest sessions and analyst history. Visitors are sent back to the guest screen (D-044).
- **Visitor IP:** the guest rate limit uses `X-Forwarded-For` (`--proxy-headers`). A client can spoof this header, which only weakens a soft limit.

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
