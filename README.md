# Eidolon

Eidolon is a private, text-only AI companion application built around continuity:
durable memory, authored persona, relationship state, episodic callbacks, and
proactive text presence. The backend owns every durable fact and policy decision;
the language model is responsible only for generating the next reply.

The current MVP includes a production-shaped FastAPI/PostgreSQL backend, a
mobile-first Next.js interface, real GroqCloud streaming, an Ollama path for
self-hosted inference, and an explicit deterministic mock used only for
development and tests.

## Current capabilities

- Account registration, login, refresh-token rotation, logout, rate limiting,
  private export, scoped data cleanup, and account deletion
- Multiple companions with authored persona, greeting, atmosphere, boundaries,
  adult eligibility, memory posture, and proactive-presence preferences
- Multiple conversations with search, unread state, shared scenes, edit/delete,
  reroll, retry, Stop, and exact SSE token streaming
- Durable message history with exactly-once completed assistant persistence and
  recoverable user turns after provider failure or cancellation
- Bounded eight-section prompt assembly with safety, persona, relationship,
  relevant memory, episodic continuity, recent history, response guidance, and
  the current user message
- Hybrid PostgreSQL recall using pgvector and text similarity, reversible memory
  forgetting, pinning, source-linked memories, deduplication, and conflicts
- Relationship state, milestones, repair guidance, episodic journals, callbacks,
  promises, open threads, and user-authored reflections
- PostgreSQL-backed scheduled work for post-chat cognition and proactive notes,
  with advisory locking, quiet hours, cooldowns, retries, and failure isolation
- Conversation and one-turn privacy modes that exclude private material from
  later learning, relationship changes, journals, and proactive work
- Privacy-safe provider readiness, generation telemetry, and authenticated debug
  diagnostics without prompts, message text, keys, exception bodies, or URLs
- Mobile-first text interface with Memories, Relationship, Moments, Settings,
  companion onboarding, reduced-motion support, and a lightweight web manifest

## Architecture

| Layer | Implementation |
| --- | --- |
| Web | Next.js App Router, React, TypeScript, Tailwind CSS |
| API | FastAPI, Pydantic v2, SQLAlchemy 2 async, APScheduler |
| Database | PostgreSQL 16, pgvector, pg_trgm, Alembic migrations |
| Streaming | Server-Sent Events from provider to FastAPI to browser |
| Inference | GroqCloud first, Ollama supported, explicit mock for dev/tests |
| Local infrastructure | Docker Compose for PostgreSQL only |
| Production path | Oracle Cloud Always Free ARM, systemd, Caddy, Ollama |

PostgreSQL is the source of truth for accounts, companions, conversations,
messages, memories, relationship state, journals, auth sessions, diagnostics,
and scheduled jobs. Provider-side conversation storage is not used.

## Requirements

- Git
- Docker with Docker Compose
- Python 3.12 or newer
- Node.js 22 and npm
- A Groq API key for real Groq replies, or explicit mock mode for local UI work
- Ollama only when selecting the self-hosted provider

## Quick start

### 1. Create local configuration

From the repository root:

```bash
cp .env.example .env
cp apps/web/.env.example apps/web/.env.local
```

Keep `.env` and `apps/web/.env.local` untracked. They are ignored by Git.

Choose one backend provider in `.env`.

For real Groq streaming:

```dotenv
APP_ENV=development
LLM_PROVIDER=groq
GROQ_API_KEY=your-private-server-side-key
GROQ_MODEL=llama-3.3-70b-versatile
```

For deterministic local development without a model call:

```dotenv
APP_ENV=development
LLM_PROVIDER=mock
GROQ_API_KEY=
```

Never put `GROQ_API_KEY` in `apps/web`, a `NEXT_PUBLIC_*` variable, source
control, logs, or browser storage.

### 2. Start PostgreSQL

```bash
docker compose up -d postgres
```

The Compose service exposes PostgreSQL on `localhost:5432`, creates the
development database, and enables pgvector and pg_trgm through
`scripts/init-db.sql`.

### 3. Install and migrate the API

```bash
cd apps/api
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
alembic upgrade head
```

### 4. Start the API

Still in `apps/api` with the virtual environment active:

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

The API reads `apps/api/.env` first and the repository-root `.env` second. The
personal development scheduler starts with the API by default. Set
`ENABLE_SCHEDULER=false` for API-only work.

### 5. Install and start the web app

In a second terminal:

```bash
cd apps/web
npm ci
npm run dev
```

Open:

- Web app: <http://localhost:3000>
- API documentation: <http://localhost:8000/docs>
- API health: <http://localhost:8000/health>
- Database health: <http://localhost:8000/health/db>
- Model health: <http://localhost:8000/health/llm>

Verify the services from a terminal:

```bash
curl http://localhost:8000/health
curl http://localhost:8000/health/db
curl http://localhost:8000/health/llm
```

Stop local PostgreSQL when finished:

```bash
docker compose down
```

The named database volume is retained. `docker compose down -v` also deletes
local database data and should only be used intentionally.

## Start-command summary

After the one-time installs and migrations, use three terminals from the
repository root:

```bash
# Terminal 1: database
docker compose up -d postgres
```

```bash
# Terminal 2: API
cd apps/api
source .venv/bin/activate
alembic upgrade head
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

```bash
# Terminal 3: web
cd apps/web
npm run dev
```

Equivalent Make targets are available:

```bash
make db-up
source apps/api/.venv/bin/activate
make api-dev
make web-dev
```

Run the API and web targets in separate terminals.

## GitHub Codespaces

Forward ports 3000 and 8000, then use their HTTPS URLs instead of browser-side
`localhost`.

In the repository-root `.env`:

```dotenv
WEB_ORIGIN=https://<codespace-name>-3000.app.github.dev
CORS_ORIGINS=https://<codespace-name>-3000.app.github.dev
REFRESH_COOKIE_SECURE=true
```

In `apps/web/.env.local`:

```dotenv
NEXT_PUBLIC_API_BASE_URL=https://<codespace-name>-8000.app.github.dev
```

Restart both dev servers after changing environment variables. If the frontend
and backend are hosted on genuinely different sites, use
`REFRESH_COOKIE_SAMESITE=none` together with `REFRESH_COOKIE_SECURE=true`.

If registration reports `Failed to fetch`, check the forwarded API URL, port
visibility, `WEB_ORIGIN`, `CORS_ORIGINS`, and the browser network panel first.

## Model providers

### Groq

Groq is the default real provider. The supported settings are documented in
`.env.example`; the main controls are:

```dotenv
LLM_PROVIDER=groq
GROQ_API_KEY=your-private-server-side-key
GROQ_MODEL=llama-3.3-70b-versatile
GROQ_BASE_URL=https://api.groq.com/openai/v1
LLM_TEMPERATURE=0.8
LLM_MAX_OUTPUT_TOKENS=1200
LLM_TIMEOUT_SECONDS=45
LLM_CONTEXT_BUDGET_TOKENS=8000
LLM_MAX_RETRIES=2
LLM_RETRY_BASE_SECONDS=0.5
```

Startup fails clearly if Groq is selected without a key. Transient 429, server,
timeout, and transport failures use bounded retries. Authentication, quota,
model, context, malformed-response, refusal, and empty-response failures are
classified into safe user-visible outcomes.

### Ollama

For self-hosted inference:

```dotenv
LLM_PROVIDER=ollama
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=llama3.1:8b
```

Install and run Ollama separately. Tests do not require it.

### Mock

Mock mode is allowed only in development or testing:

```dotenv
APP_ENV=development
LLM_PROVIDER=mock
```

It is deterministic and suitable for UI work and tests. A live provider never
falls back to fake mock text.

### Fallbacks

`LLM_FALLBACK_PROVIDER` and `LLM_FALLBACK_MODEL` are optional. Fallback occurs
only before the primary provider emits text. Eidolon never joins fallback text
onto a partial response and never persists a partial assistant message.

## Streaming and post-chat behavior

The browser submits a user turn and consumes typed SSE events from FastAPI. The
accepted user row is committed before provider inference. A successful stream
persists exactly one completed assistant row linked to that user row. Stop,
disconnect, or provider failure discards partial assistant text and preserves a
retryable or cancelled user turn.

Successful non-private exchanges create durable `chat_postprocess` jobs. These
jobs update candidate memories, episodic continuity, promises, callbacks, and
open threads. Post-processing failure cannot undo a completed chat and is retried
independently from PostgreSQL.

## Authentication and privacy

- Access tokens are short-lived and held in browser memory.
- Refresh tokens use an HttpOnly `eidolon_refresh` cookie scoped to `/auth`.
- Production requires a private 32-4096-byte `JWT_SECRET` and secure cookies.
- Login and registration throttles are enforced through PostgreSQL before
  expensive password hashing.
- Private turns remain visible to their owner but are excluded from later prompt
  history, memory extraction, journals, relationship effects, and proactive work.
- Adult mode requires a user age gate, an explicitly adult companion, consent
  settings, and structural content boundaries.

Generate a production JWT secret with:

```bash
openssl rand -hex 32
```

## Scheduler and proactive messages

APScheduler wakes the worker, but PostgreSQL owns durable job state, retries,
locks, and outcomes. The runtime uses advisory locking so multiple API processes
do not process the same scheduler tick concurrently. Configuration includes:

- `ENABLE_SCHEDULER`
- `SCHEDULER_INTERVAL_SECONDS`
- `SCHEDULER_JOB_LIMIT`
- `SCHEDULER_MAX_RETRIES`
- `SCHEDULER_RETRY_BASE_SECONDS`
- `PROACTIVE_INACTIVITY_HOURS`
- `PROACTIVE_COOLDOWN_HOURS`

Companion-level preferences add timezone-aware morning/goodnight windows, quiet
hours, and note cooldowns.

## Validation

Start PostgreSQL before backend tests:

```bash
docker compose up -d postgres
```

Backend:

```bash
cd apps/api
source .venv/bin/activate
alembic upgrade head
pytest -m "not live"
ruff check .
ruff format --check .
```

Frontend:

```bash
cd apps/web
npm ci
npm run lint
npm run build
```

Or, after installing both apps:

```bash
make verify
```

The real Groq smoke test is opt-in and excluded from CI:

```bash
cd apps/api
source .venv/bin/activate
RUN_GROQ_LIVE_TEST=1 pytest -q -m live tests/test_groq_live.py
```

It uses the configured backend key without printing it and verifies real SSE,
grounded context, persistence, provider/model metadata, timing, token usage, and
exactly one completed user/assistant pair after reload.

## Repository layout

```text
apps/api/                 FastAPI app, providers, services, models, migrations, tests
apps/web/                 Next.js interface and client-side controllers
docs/                     Product, architecture, data, prompt, safety, UX, and ops docs
infra/caddy/              Example reverse-proxy configuration
infra/systemd/            Example API systemd unit
infra/deploy/             Example SSH deployment script
scripts/init-db.sql       Local PostgreSQL extension initialization
scripts/backup-db.example.sh
docker-compose.yml        Local PostgreSQL service
Makefile                  Common development and validation commands
```

Useful detailed references:

- `docs/03_ARCHITECTURE.md`
- `docs/05_DATA_MODEL.md`
- `docs/06_API_CONTRACT.md`
- `docs/07_PROMPT_ASSEMBLY.md`
- `docs/08_MEMORY_SYSTEM.md`
- `docs/10_BACKGROUND_JOBS.md`
- `docs/11_SAFETY_AND_BOUNDARIES.md`
- `docs/12_FRONTEND_UX.md`
- `docs/13_DEPLOYMENT_TARGET.md`
- `docs/14_TESTING_AND_ACCEPTANCE.md`
- `docs/GOAL_PROGRESS.md`

## Backup and deployment

Before trusting Eidolon with important data, configure regular PostgreSQL
backups. `scripts/backup-db.example.sh` is a reviewed starting point; generated
backup files belong under ignored `backups/`, never in Git.

The personal production target is an Oracle Cloud Always Free ARM VM with
PostgreSQL 16/pgvector, FastAPI under systemd, Caddy for HTTPS, and Ollama for a
zero-recurring-cost inference path. Example files live under `infra/`. Review and
adapt them before use; they contain no cloud resources, credentials, or private
addresses.

## Deliberate non-goals

The MVP intentionally excludes voice, audio, avatars, image/video generation,
AR, Live2D, native mobile clients, fine-tuning, Kubernetes, Redis, Celery,
LangChain, and external vector databases. Immersion comes from text and durable
state, not multimedia or dependency weight.

## Core rule

The backend owns state. The language model generates text.
