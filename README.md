# Eidolon

Eidolon is a private, text-only AI companion built around durable memory,
authored character continuity, evolving relationship state, privacy controls,
and streamed conversation. The backend owns state and safety decisions; the
language model generates prose.

## Current deployment

| Layer | Production service |
| --- | --- |
| Frontend | Cloudflare Pages static Next.js export |
| Backend | Google Cloud Run FastAPI container |
| Database | Supabase PostgreSQL Session pooler |
| Inference | Groq, called only by the backend |
| Authentication | Eidolon JWT access tokens and PostgreSQL refresh sessions |

```text
Browser -> Cloudflare Pages -> HTTPS JSON/SSE -> Cloud Run
                                                |-> Supabase PostgreSQL
                                                `-> Groq
```

Cloudflare serves the static client; the browser calls Cloud Run directly.
Supabase Auth is not used. Database credentials, provider keys, JWT secrets, and
refresh tokens never belong in frontend code.

## Capabilities

- local account registration, login, rotating HttpOnly refresh sessions, and
  PostgreSQL-backed throttling
- multiple authored companions and conversations
- exact Server-Sent Events token streaming with stop/retry/reroll/edit support
- evidence-grounded post-turn cognition with selective semantic memory,
  claim correction, source-linked shared moments, and quiet continuity receipts
- visible living threads for explicit plans, promises, rituals, repairs, and
  follow-ups, with user-controlled closure and deletion
- deterministic relationship and emotional continuity refined by bounded,
  source-grounded interaction evidence
- normal/private threads, one-turn privacy, thread-specific Shared Scenes, and
  separately scoped optional adult continuity
- PostgreSQL-backed scheduled cognition and earned proactive notes anchored to
  real shared moments, open threads, or milestones
- structural adult-mode gates and non-negotiable hard safety boundaries
- owner-scoped Debug visibility without raw prompts or secrets
- private data export, scoped cleanup, and account erasure

## Documentation

| Document | Purpose |
| --- | --- |
| [AGENTS.md](AGENTS.md) | Mandatory repository rules for coding agents |
| [Product](docs/PRODUCT.md) | Product scope, experience, privacy, and non-goals |
| [Architecture](docs/ARCHITECTURE.md) | Components, trust boundaries, and runtime flows |
| [Data model](docs/DATA_MODEL.md) | Durable entities, ownership, and migration rules |
| [API](docs/API.md) | Maintained route inventory and API conventions |
| [Companion systems](docs/COMPANION_SYSTEMS.md) | Prompt, memory, relationship, and job behaviour |
| [Safety](docs/SAFETY.md) | Content, privacy, authentication, and data boundaries |
| [Operations](docs/OPERATIONS.md) | Setup, validation, releases, deploys, backups, rollback |
| [Roadmap](docs/ROADMAP.md) | Current priorities and deferred work |
| [Goal progress](docs/GOAL_PROGRESS.md) | Concise outcomes and validation for completed tasks |

FastAPI's generated `/docs`, the Pydantic schemas, SQLAlchemy models, Alembic
migrations, and tests remain the executable low-level contract.

## Repository layout

```text
apps/api/                 FastAPI app, providers, services, models, migrations, tests
apps/web/                 Static-export Next.js frontend
docs/                     Maintained product and engineering documentation
.github/workflows/ci.yml  Pull-request and main-branch validation
docker-compose.yml        Local PostgreSQL 16 with pgvector
scripts/init-db.sql       Local database extension initialization
infra/                    Legacy self-hosting examples retained for reference
Makefile                  Common local and validation commands
```

## Local quick start

Requirements:

- Docker with Docker Compose
- Python 3.12+
- Node.js 22 and npm
- Git

Create local environment files only if they do not exist:

```bash
test -f .env || cp .env.example .env
test -f apps/web/.env.local || cp apps/web/.env.example apps/web/.env.local
```

The examples use local PostgreSQL and the deterministic mock provider, so local
development does not need a Groq key.

Start PostgreSQL:

```bash
docker compose up -d postgres
```

Install, migrate, and run the API:

```bash
cd apps/api
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
alembic upgrade head
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

In a second terminal, install and run the frontend:

```bash
cd apps/web
npm ci
npm run dev
```

Open `http://localhost:3000`. Useful API endpoints:

- `http://localhost:8000/docs`
- `http://localhost:8000/health`
- `http://localhost:8000/ready`
- `http://localhost:8000/health/db`
- `http://localhost:8000/health/llm`

After the one-time installation, the recurring commands are:

```bash
# repository root
docker compose up -d postgres
```

```bash
# API terminal
cd apps/api
source .venv/bin/activate
alembic upgrade head
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

```bash
# web terminal
cd apps/web
npm run dev
```

Stop local PostgreSQL with `docker compose down`. Adding `-v` deletes the local
database volume and should be intentional.

## Configuration

Backend settings are documented with safe placeholders in `.env.example`.
Frontend settings are in `apps/web/.env.example`.

Local files are ignored by Git:

- `.env`
- `apps/web/.env.local`

Production secrets belong in Google Secret Manager or Cloud Run secret bindings.
The only required Cloudflare build variable is the public API origin:

```dotenv
NEXT_PUBLIC_API_BASE_URL=https://your-cloud-run-service-url
```

Never put a database URL, Groq key, JWT secret, or any credential in a
`NEXT_PUBLIC_*` variable.

## Validation

With local PostgreSQL running:

```bash
make verify
```

The combined target runs migrations, backend tests, Ruff checks, frontend lint,
TypeScript checks, and the production frontend build. Automated tests exclude
the opt-in live provider test.

See [Operations](docs/OPERATIONS.md) for individual commands, container checks,
and the live-test opt-in.

## Development and production releases

Editing local files does not change the live application. `main` is treated as
the production branch, so normal work should use a feature branch and pull
request:

```bash
git switch main
git pull --ff-only
git switch -c feature/short-description
```

Validate, commit specific files, push the branch, wait for both CI jobs, then
merge through GitHub. Cloudflare and Cloud Build deploy triggers are configured
outside this repository and must be checked in their dashboards.

A Cloudflare branch preview is not an isolated backend. If it uses the production
API URL, it can access production data and may fail exact-origin CORS. Use the
local full stack for data-mutating functional tests unless a real staging API and
database exist.

Full release, migration, secret-preservation, backup, rollback, and production
verification guidance is in [Operations](docs/OPERATIONS.md).

## Production build contracts

| Target | Root | Build/start | Result |
| --- | --- | --- | --- |
| Cloudflare Pages | `apps/web` | `npm run build` | `out` |
| Cloud Run | `apps/api` | `Dockerfile` | non-root API on injected `PORT`/8080 |

The Cloud Run image runs `alembic upgrade head` under a PostgreSQL advisory lock
before starting Uvicorn. Every database model change therefore needs a reviewed,
tested, backward-compatible Alembic migration.

## Production health

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

`/health` is process liveness. `/ready` verifies PostgreSQL with a bounded query
and never returns a connection string or exception detail.

## Product boundaries

Eidolon is text-only. Voice, avatars, images, video, AR, Live2D, fine-tuning,
Redis, Celery, Kubernetes, LangChain, and external vector databases are outside
the MVP.

Legal adult fictional text roleplay is structurally gated. The application does
not permit minors or ambiguous ages in sexual contexts, sexual coercion or
exploitation, illegal sexual content, or real-world instructions for harm,
stalking, abuse, or exploitation. Adult mode requires the user age gate and an
explicitly adult companion; hard boundaries always remain active.

The core rule remains: the backend owns state; the model generates text.
