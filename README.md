# Eidolon

Eidolon is a private, text-only AI companion application built around durable
memory, character continuity, relationship state, and streamed conversation.
The FastAPI backend owns all durable state and safety decisions; the language
model generates text only.

This repository is configured for the following production deployment:

| Layer | Production service |
| --- | --- |
| Frontend | Cloudflare Pages, static Next.js export |
| Backend | Google Cloud Run, containerized FastAPI |
| Database | Supabase PostgreSQL through the Session pooler |
| AI | Groq, called only by the backend |
| Authentication | Eidolon's existing JWT access tokens and rotating HttpOnly refresh sessions |

Supabase Auth is not used. Database credentials, Groq keys, JWT secrets, and
refresh tokens never belong in the frontend.

## Repository and deployment roots

| Target | Root directory | Build/start setting | Output/port |
| --- | --- | --- | --- |
| Cloudflare Pages | `apps/web` | `npm run build` | `out` |
| Cloud Run build context | `apps/api` | `Dockerfile` | container port `8080` |
| Local backend | `apps/api` | `uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload` | `8000` |
| Local frontend | `apps/web` | `npm run dev` | `3000` |

Cloud Run injects `PORT`; the image starts Uvicorn on `0.0.0.0:${PORT}`. Do not
set `PORT` as a user-defined Cloud Run variable.

## What is included

- Account registration, login, rotating refresh sessions, logout, throttling,
  private export, scoped cleanup, and account deletion
- Multiple authored companions and conversations
- Exact Server-Sent Events (SSE) streaming from Groq through FastAPI to the
  browser
- PostgreSQL-backed messages, memories, journals, relationships, diagnostics,
  auth sessions, and scheduled jobs
- Hybrid pgvector and text-similarity recall
- Backend-owned persona prompts, relationship evolution, safety gates, private
  turns, and adult-mode eligibility
- A deterministic mock provider for development and tests only
- Alembic migrations and PostgreSQL advisory locks for safe concurrent container
  startup

## Local start

Requirements:

- Docker with Docker Compose
- Python 3.12 or newer
- Node.js 22 and npm
- Git

Create local configuration from the repository root:

```bash
test -f .env || cp .env.example .env
test -f apps/web/.env.local || cp apps/web/.env.example apps/web/.env.local
```

The example selects `LLM_PROVIDER=mock`, so local development does not require a
Groq key. `.env` and `apps/web/.env.local` are ignored by Git.

Start PostgreSQL:

```bash
docker compose up -d postgres
```

Install, migrate, and start the backend:

```bash
cd apps/api
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
alembic upgrade head
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

In a second terminal, install and start the frontend:

```bash
cd apps/web
npm ci
npm run dev
```

Open <http://localhost:3000>. Useful backend endpoints are:

- API documentation: <http://localhost:8000/docs>
- Liveness: <http://localhost:8000/health>
- Readiness/database connectivity: <http://localhost:8000/ready>
- Database diagnostic: <http://localhost:8000/health/db>
- Provider diagnostic: <http://localhost:8000/health/llm>

After the one-time installs, the three recurring start commands are:

```bash
# Terminal 1, repository root
docker compose up -d postgres
```

```bash
# Terminal 2, repository root
cd apps/api
source .venv/bin/activate
alembic upgrade head
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

```bash
# Terminal 3, repository root
cd apps/web
npm run dev
```

Stop local PostgreSQL with `docker compose down`. The named volume is retained;
`docker compose down -v` intentionally deletes it.

### Run the production container locally

With local PostgreSQL running and the root `.env` configured:

```bash
docker build -t eidolon-api ./apps/api
docker run --rm --network host --env-file .env -e PORT=8080 eidolon-api
```

The container runs `alembic upgrade head` before Uvicorn. Each migration process
takes the same PostgreSQL advisory lock, so concurrent Cloud Run starts serialize
schema upgrades instead of racing them. A failed migration prevents the API from
starting.

## Production environment

### Cloud Run variables

Configure these on the Cloud Run backend. Values marked secret should be sourced
from Google Secret Manager or the Cloud Run secret UI, not a checked-in file.

| Variable | Required production value |
| --- | --- |
| `APP_ENV` | `production` |
| `DATABASE_URL` | Secret: Supabase Session pooler URL on port `5432` |
| `GROQ_API_KEY` | Secret: Groq server-side API key |
| `JWT_SECRET` | Secret: random 32-4096-byte Eidolon signing value |
| `LLM_PROVIDER` | `groq` |
| `WEB_ORIGIN` | Exact HTTPS Cloudflare production origin, without a trailing slash |
| `CORS_ORIGINS` | Comma-separated additional exact HTTPS origins, or the same production origin |
| `REFRESH_COOKIE_SECURE` | `true` |
| `REFRESH_COOKIE_SAMESITE` | `none` for default `pages.dev` -> `run.app` hosting; see auth note below |
| `GROQ_MODEL` | `openai/gpt-oss-120b` by default, or another enabled production model |

Recommended database pool values are intentionally conservative:

```dotenv
DATABASE_POOL_SIZE=5
DATABASE_MAX_OVERFLOW=0
DATABASE_POOL_TIMEOUT_SECONDS=30
DATABASE_POOL_RECYCLE_SECONDS=300
```

The maximum possible database connections from this service are approximately
`(DATABASE_POOL_SIZE + DATABASE_MAX_OVERFLOW) * Cloud Run max instances`. Keep
that total below the Supabase plan's available connection allowance.

Other supported runtime controls are documented in `.env.example`, including
token lifetimes, login/registration throttling, Groq timeouts/retries, and the
PostgreSQL-backed scheduler.

Production startup deliberately fails when:

- `DATABASE_URL`, `GROQ_API_KEY`, or `JWT_SECRET` is absent or still a placeholder
- the database is not PostgreSQL through the async driver
- the selected provider is mock or Ollama
- secure refresh cookies are disabled
- browser origins are absent, wildcarded, non-HTTPS, or contain a path

There is no production fallback to SQLite, an in-memory database, or generated
mock replies.

### Cloudflare Pages variable

Set exactly one public build variable in Cloudflare Pages:

```dotenv
NEXT_PUBLIC_API_BASE_URL=https://your-cloud-run-service-url
```

It is embedded into browser JavaScript at build time and is therefore public.
Never create `NEXT_PUBLIC_DATABASE_URL`, `NEXT_PUBLIC_GROQ_API_KEY`,
`NEXT_PUBLIC_JWT_SECRET`, or any equivalent secret variable. Production frontend
builds fail when `NEXT_PUBLIC_API_BASE_URL` is missing or is not an HTTP(S) URL.

## Supabase setup

1. Create a Supabase project.
2. In the database Connect dialog, select **Session pooler**, not Transaction
   pooler or the direct IPv6 connection.
3. Confirm the connection uses the shared pooler hostname and port `5432`.
4. URL-encode special characters in the database password.
5. Store the resulting URL as the Cloud Run `DATABASE_URL` secret. Use the
   SQLAlchemy driver prefix and encrypted connection parameter:

```text
postgresql+asyncpg://postgres.<project-ref>:<url-encoded-password>@aws-0-<region>.pooler.supabase.com:5432/postgres?ssl=require
```

Plain `postgres://` and `postgresql://` prefixes are normalized to
`postgresql+asyncpg://`. `sslmode=require` is normalized to the `asyncpg`
`ssl=require` form.

The initial Alembic migration enables `vector` and `pg_trgm` and then creates the
Eidolon schema. The supplied Supabase database user must retain permission to
enable those supported extensions and create tables.

## Deploy the backend to Cloud Run

The backend Docker build context is exactly `apps/api`.

Example Artifact Registry and build commands, run from the repository root:

```bash
export PROJECT_ID=your-google-cloud-project
export REGION=your-cloud-run-region
export REPOSITORY=eidolon

gcloud config set project "$PROJECT_ID"
gcloud services enable artifactregistry.googleapis.com run.googleapis.com cloudbuild.googleapis.com secretmanager.googleapis.com
gcloud artifacts repositories create "$REPOSITORY" --repository-format=docker --location="$REGION"
gcloud builds submit apps/api --tag "$REGION-docker.pkg.dev/$PROJECT_ID/$REPOSITORY/eidolon-api:latest"
```

Create these three Secret Manager secrets through the Google Cloud console or
CLI, with a current enabled version for each:

- `eidolon-database-url` -> Supabase Session pooler URL
- `eidolon-groq-api-key` -> Groq API key
- `eidolon-jwt-secret` -> output of `openssl rand -hex 32`

Give the Cloud Run runtime identity `roles/secretmanager.secretAccessor` on those
three secrets. A dedicated identity keeps the scope explicit:

```bash
gcloud iam service-accounts create eidolon-api-runtime \
  --display-name "Eidolon Cloud Run runtime"

export RUNTIME_SERVICE_ACCOUNT="eidolon-api-runtime@$PROJECT_ID.iam.gserviceaccount.com"

for SECRET in eidolon-database-url eidolon-groq-api-key eidolon-jwt-secret; do
  gcloud secrets add-iam-policy-binding "$SECRET" \
    --member "serviceAccount:$RUNTIME_SERVICE_ACCOUNT" \
    --role roles/secretmanager.secretAccessor
done
```

Deploy after replacing the two origin placeholders with the final Cloudflare
Pages production origin:

```bash
gcloud run deploy eidolon-api \
  --image "$REGION-docker.pkg.dev/$PROJECT_ID/$REPOSITORY/eidolon-api:latest" \
  --region "$REGION" \
  --service-account "$RUNTIME_SERVICE_ACCOUNT" \
  --allow-unauthenticated \
  --port 8080 \
  --timeout 300 \
  --concurrency 20 \
  --max-instances 2 \
  --set-secrets DATABASE_URL=eidolon-database-url:latest,GROQ_API_KEY=eidolon-groq-api-key:latest,JWT_SECRET=eidolon-jwt-secret:latest \
  --set-env-vars APP_ENV=production,LLM_PROVIDER=groq,GROQ_MODEL=openai/gpt-oss-120b,WEB_ORIGIN=https://your-project.pages.dev,CORS_ORIGINS=https://your-project.pages.dev,REFRESH_COOKIE_SECURE=true,REFRESH_COOKIE_SAMESITE=none,DATABASE_POOL_SIZE=5,DATABASE_MAX_OVERFLOW=0,ENABLE_DEBUG_ROUTES=false
```

Public Cloud Run ingress is necessary for the browser to call the API; Eidolon
still enforces its own authentication on private application routes. `/health`
is liveness-only. `/ready` executes `SELECT 1` and returns only bounded status
fields, never a connection string or exception detail. In Cloud Run health-check
settings, use `/health` for liveness and `/ready` for readiness/startup checks.

The Cloud Run request timeout must exceed the configured Groq timeout so SSE
requests can finish cleanly. The stream response sends `Cache-Control: no-cache,
no-transform` and `X-Accel-Buffering: no`; Cloudflare Pages does not proxy the
stream because the browser calls Cloud Run directly.

Groq model IDs are operational configuration and can be deprecated. The previous
`llama-3.3-70b-versatile` default is scheduled to leave Groq's free/developer
tiers on 2026-08-16, so this deployment defaults to its documented production
replacement. Check Groq's current model/deprecation pages before each deploy.

### Scheduler behavior on Cloud Run

Scheduled jobs remain durable and PostgreSQL-locked. With Cloud Run's default
request-based CPU and scale-to-zero behavior, APScheduler can only make progress
while an instance is active, so proactive delivery is best-effort/catch-up rather
than wall-clock exact. Always-allocated CPU and a minimum instance improve timing
but can add cost. Set `ENABLE_SCHEDULER=false` if proactive work is not wanted on
this deployment.

## Deploy the frontend to Cloudflare Pages

Create a Pages project connected to this repository with these exact settings:

| Cloudflare setting | Value |
| --- | --- |
| Framework preset | Next.js (Static HTML Export) |
| Root directory | `apps/web` |
| Build command | `npm run build` |
| Build output directory | `out` |
| Production variable | `NEXT_PUBLIC_API_BASE_URL=https://<Cloud Run service URL>` |

Use Node.js 22 for the Pages build environment. `next.config.mjs` sets
`output: "export"`, and `public/_headers` supplies the static security headers
that Cloudflare copies into the deployment.

After the first Pages deployment, make sure its exact production origin matches
both `WEB_ORIGIN` and `CORS_ORIGINS` on Cloud Run. Add preview origins explicitly
when testing authenticated preview deployments; credentialed CORS intentionally
does not accept `*`.

## Authentication across the two hosts

Eidolon preserves its existing authentication:

- access tokens are short-lived and held in browser memory
- refresh tokens are random, hashed in PostgreSQL, rotated, and delivered only
  through the HttpOnly `eidolon_refresh` cookie
- browser API calls use `credentials: include`
- login, registration, refresh, and logout validate the request origin

The default `pages.dev` and `run.app` domains are cross-site, so configure
`REFRESH_COOKIE_SECURE=true` and `REFRESH_COOKIE_SAMESITE=none`. Some browsers or
privacy modes block third-party cookies entirely. For the most reliable session
refresh, use custom subdomains under one registrable domain, for example
`app.example.com` and `api.example.com`, while still keeping CORS origins exact.

## Production verification

After both deployments:

```bash
export API_URL=https://your-cloud-run-service-url
curl --fail "$API_URL/health"
curl --fail "$API_URL/ready"
```

Expected responses:

```json
{"status":"ok","service":"eidolon-api"}
```

```json
{"status":"ready","database":"ok"}
```

Then open the Cloudflare site, register a test account, send a message, verify
incremental token rendering, reload the page, and confirm the refresh session and
conversation history survive. Check the browser network panel for an unbuffered
`text/event-stream` response from `/chat/stream`.

## Validation

Start local PostgreSQL first:

```bash
docker compose up -d postgres
```

Backend checks:

```bash
cd apps/api
pip install -e ".[dev]"
alembic upgrade head
pytest -m "not live"
ruff check .
ruff format --check .
```

Frontend checks:

```bash
cd apps/web
npm ci
npm run lint
npm run typecheck
npm run build
```

Container check:

```bash
docker build -t eidolon-api ./apps/api
```

The opt-in Groq test makes a real provider call and is excluded from normal test
runs:

```bash
cd apps/api
RUN_GROQ_LIVE_TEST=1 pytest -q -m live tests/test_groq_live.py
```

## Troubleshooting

- `DATABASE_URL must be set explicitly`: set the Cloud Run secret to the
  Supabase Session pooler URL, not the local example URL.
- Supabase connection failure: confirm Session mode, port `5432`, password URL
  encoding, `ssl=require`, and project availability.
- `GROQ_API_KEY is required`: add an enabled secret version and map it to the
  Cloud Run environment variable.
- Frontend build says `NEXT_PUBLIC_API_BASE_URL` is required: add it to the
  Cloudflare Pages production build variables and redeploy.
- Browser CORS failure: compare the browser `Origin` exactly with `WEB_ORIGIN`
  and `CORS_ORIGINS`; omit paths and trailing slashes.
- Login works but reload signs out: verify `SameSite=None; Secure`, credentialed
  requests, and the browser's third-party-cookie policy; custom same-site
  subdomains are the robust fix.
- `/health` passes but `/ready` fails: the API process is alive but cannot query
  Supabase. Inspect Cloud Run logs; the endpoint intentionally hides details.
- Stream ends early: verify the Cloud Run timeout, Groq timeout, and response
  headers. Do not place a buffering proxy between the browser and Cloud Run.

## Repository layout

```text
apps/api/                 FastAPI app, Dockerfile, Alembic, models, and tests
apps/web/                 Static-export Next.js frontend
docs/                     Product, architecture, data, safety, UX, and ops docs
infra/                    Legacy self-hosting examples retained for reference
scripts/init-db.sql       Local PostgreSQL extension initialization
docker-compose.yml        Local PostgreSQL 16 + pgvector
Makefile                  Common local and validation commands
```

## Product boundaries

Eidolon supports fictional adult text roleplay only within structural safety
boundaries. It does not permit minors or ambiguous ages in sexual contexts,
sexual coercion or exploitation, illegal sexual content, or real-world
instructions for harm, stalking, abuse, or exploitation. Adult mode requires the
user age gate and an explicitly adult companion.

Voice, avatars, images, video, AR, Live2D, fine-tuning, Redis, Celery,
Kubernetes, LangChain, and external vector databases are outside the MVP.

The core rule remains: the backend owns state; the language model generates
text.
