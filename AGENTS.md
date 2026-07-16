# Eidolon Agent Instructions

These instructions are mandatory for Codex and every coding agent working in this repository.

## Project summary

Eidolon is a private, text-only AI companion application. Its depth comes from
backend-owned memory, persona continuity, relationship state, prompt assembly,
privacy controls, and scheduled text behaviour. It is not a multimedia avatar
application.

The MVP is deployed. Work should improve the existing product without replacing
its architecture, weakening its safety boundaries, or treating production as a
disposable test environment.

## Sources of truth

Read the smallest relevant set before changing code:

- `README.md` for setup, repository layout, and the documentation map
- `docs/PRODUCT.md` for product scope and user-facing behaviour
- `docs/ARCHITECTURE.md` for component boundaries and runtime flows
- `docs/DATA_MODEL.md` for durable state and migration expectations
- `docs/API.md` for the route inventory and API conventions
- `docs/COMPANION_SYSTEMS.md` for prompts, memory, relationships, and jobs
- `docs/SAFETY.md` for non-negotiable content and privacy boundaries
- `docs/OPERATIONS.md` for deployment, release, backup, and validation work
- `docs/ROADMAP.md` for current priorities and deferred work
- `docs/GOAL_PROGRESS.md` for one concise entry per completed user task

When documentation and executable code disagree, do not silently choose one.
Confirm the implementation, correct stale documentation in the same change, and
call out any product decision that cannot be inferred safely.

## Active production topology

- Frontend: Cloudflare Pages static export from `apps/web`
- Backend: Google Cloud Run container built from `apps/api`
- Database: Supabase PostgreSQL through the Session pooler
- Inference: Groq through the backend-only provider adapter
- Secrets: Google Secret Manager or Cloud Run secret bindings
- Source and CI: GitHub; CI runs on pull requests and pushes to `main`

The provider and database are behind interfaces so a future migration remains
possible, but Oracle/Ollama is not the active production target.

The personal deployment should remain within the operator's chosen free-tier
limits. Free tiers are external policies, not a guarantee the code can make. Do
not add a paid service, enable a chargeable feature, raise instance floors, or
materially increase resource usage without explicit user approval.

## Hard constraints

- Development happens on a low-spec Chromebook through GitHub Codespaces.
- Do not run a local model on the Chromebook.
- Keep the client lightweight and text-first.
- No voice, audio, avatar, video, AR, image generation, Live2D, or heavy 3D work.
- No browser-side inference and no provider key in frontend code.
- Do not add Redis, Celery, Kubernetes, LangChain, Pinecone, Chroma, or another
  datastore/queue merely for convenience.
- Do not replace established dependencies without a concrete need.
- Never commit `.env`, secrets, tokens, credentials, private URLs, private IPs,
  database dumps, or production user data.

## Required stack

Frontend:

- Next.js App Router
- TypeScript
- React
- Tailwind CSS
- static production export
- native fetch with Server-Sent Events for streaming

Backend:

- Python 3.12+
- FastAPI and Uvicorn
- Pydantic v2 and pydantic-settings
- SQLAlchemy 2.x async with asyncpg
- Alembic
- APScheduler as a wake-up mechanism only

Database:

- PostgreSQL 16
- pgvector
- pg_trgm where useful
- PostgreSQL as the source of truth for accounts, sessions, characters,
  conversations, messages, memories, relationships, diagnostics, and jobs

LLM providers:

- deterministic mock for development and automated tests
- Groq for the active production deployment
- Ollama adapter retained as an optional development/self-hosting path
- no fine-tuning in the MVP

Infrastructure:

- GitHub Codespaces for development
- Docker Compose for local PostgreSQL only
- Cloudflare Pages for the production frontend
- Google Cloud Run for the production API
- Supabase Session pooler for production PostgreSQL access
- Google Secret Manager/Cloud Run bindings for secrets

## Production and Git rules

- Editing local files does not change production.
- Treat `main` as the production branch.
- Use a feature branch and pull request for normal work.
- The user has given standing permission to commit and push completed task work.
  After validation, stage every task-owned change (including new and deleted
  files), inspect the staged diff, commit it, and push the current feature branch.
- Never include unrelated user work merely because `git add -A` is convenient.
- Never push completed development work directly to `main`. When starting from
  `main`, create an `agent/<short-description>` branch first.
- Open or update a pull request after pushing when repository access permits.
- Do not merge the pull request, deploy manually, or change cloud configuration
  without an explicit user request for that production action.
- GitHub Actions CI and hosting deployment triggers are separate. A passing CI
  workflow does not prove a host deployed, and a host may deploy without waiting
  for CI unless its external trigger is configured to do so.
- A Cloudflare branch preview is only a frontend preview. If it points at the
  production API, it can read or mutate production data and may be rejected by
  exact-origin CORS. Do not describe it as a staging environment.
- Preserve Cloud Run environment variables, secret bindings, service identity,
  instance limits, timeout, and CORS settings when deploying a new image.

## Product boundaries

The app may support legal adult fictional text roleplay between adults, but it
must enforce structural boundaries:

- no minors or ambiguous-age characters in sexual contexts
- no sexual coercion, exploitation, or abuse
- no illegal sexual content
- no real-world instructions for harm, stalking, exploitation, or abuse
- adult mode requires user age-gate confirmation and an explicit adult
  character age
- relationship repair/tension gates and hard boundaries remain authoritative
- “uncensored” never means “no rules”

Do not put explicit sexual samples in code, tests, fixtures, seed data, or docs.

## Core architecture principle

The backend owns state. The LLM generates prose.

The backend owns identity, character configuration, conversation history,
memory, relationship and emotional state, prompt construction, safety gates,
privacy rules, scheduled jobs, proactive-message decisions, and debug
visibility. Durable facts belong in PostgreSQL and must not depend on provider
conversation history.

## Engineering rules

- Build thin vertical slices and preserve existing flows.
- Keep files small, explicit, typed, and boring.
- Use Pydantic schemas at API boundaries.
- Scope every user-owned database operation to the authenticated owner.
- Use SQLAlchemy models and Alembic migrations for schema changes.
- Never change a model without adding and testing the matching migration.
- Cloud Run starts with `alembic upgrade head`; prefer backward-compatible,
  additive migrations and stage destructive changes.
- Preserve the PostgreSQL migration advisory lock.
- Add deterministic tests for backend services and endpoints.
- Mock Groq/Ollama HTTP in automated tests; live provider tests stay opt-in.
- Avoid global mutable state except explicit application lifecycle objects.
- Keep generated fixtures SFW and failures readable.
- Keep raw prompts, message prose, secrets, provider response bodies, and stack
  traces out of diagnostics.
- Reuse existing abstractions before adding dependencies.

## Documentation rules

- Update the relevant retained document when behaviour, architecture, routes,
  schema, deployment, or safety rules change.
- After each completed user task, add one concise entry to
  `docs/GOAL_PROGRESS.md` covering outcome and validation.
- `docs/GOAL_PROGRESS.md` is the only progress log. Do not add micro-checkpoint
  diaries, copied goal prompts, or dated audit dumps.
- Do not create a new document when an existing retained document has the right
  scope.
- Keep `README.md` focused on orientation and quick start.
- FastAPI's generated `/docs`, Pydantic schemas, SQLAlchemy models, migrations,
  and tests remain the executable detail; Markdown should explain stable
  contracts and decisions instead of copying every implementation line.

## Done means

A change is complete only when:

- relevant tests pass
- linters, type checks, and builds pass
- migrations upgrade successfully when the database changed
- existing flows still work
- no forbidden or unapproved dependency/service was added
- no secret or private data was introduced
- affected documentation matches the implementation
- `docs/GOAL_PROGRESS.md` contains a concise task entry
- all task-owned changes are staged, reviewed, committed, and pushed to the
  feature branch unless an external authentication/service failure blocks it

## Validation commands

Start local PostgreSQL before backend validation:

```bash
docker compose up -d postgres
```

Backend:

```bash
cd apps/api
pip install -e ".[dev]"
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
npm run typecheck
npm run build
```

From the repository root, `make verify` runs the normal combined checks after
dependencies and PostgreSQL are available.

## If blocked

If work is blocked:

1. stop changing files,
2. explain the exact blocker and preserved state,
3. state the smallest user decision or external change needed,
4. do not invent credentials, infrastructure, provider access, or deployment
   success.
