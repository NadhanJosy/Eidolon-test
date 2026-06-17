# Goal Progress

Codex should update this file during `/goal` runs.

## Current status

Local MVP is implemented and validated. FastAPI and Next.js dev servers start locally, `/health` returns the exact expected payload, and the app supports register/login/chat/stream/refresh with persisted history plus persona, memory, relationship, proactive/debug, adult gates, export, and deploy/backup templates.

## Debug update - frontend registration `Failed to fetch`

Root cause inspected on 2026-06-17:
- Frontend register calls `POST /auth/register` with `{ email, password, display_name }`, which matches the backend `RegisterRequest` schema.
- Backend `POST /auth/register` works and returns a bearer token; cookies/credentials mode is not required.
- The likely Codespaces failure was browser reachability/CORS configuration: the frontend defaulted to `http://localhost:8000`, which a browser outside the Codespace may not reach, and backend CORS only allows configured `WEB_ORIGIN`/`CORS_ORIGINS`.
- Frontend network errors previously surfaced as raw browser `Failed to fetch`, hiding the API base URL and Codespaces/CORS guidance.

Fixes:
- Frontend API client now keeps `NEXT_PUBLIC_API_BASE_URL` as the explicit override, infers the matching `-8000.app.github.dev` API URL from a Codespaces `-3000.app.github.dev` frontend URL when no override is set, and shows actionable network/CORS errors.
- Streaming chat now uses the same API client error handling as JSON requests.
- Backend CORS origin parsing now trims whitespace and trailing slashes for `WEB_ORIGIN` and `CORS_ORIGINS`.
- `.env.example`, `apps/web/.env.example`, and `README.md` document Codespaces URL variables without hardcoding a specific Codespace URL.

## Checkpoints

| # | Checkpoint | Status | Notes |
|---|---|---|---|
| 1 | Repo scaffolding sanity check | complete | Existing `.env.example`, `.gitignore`, `docker-compose.yml`, `Makefile`, CI placeholder, deployment templates, and database init script inspected. PostgreSQL pgvector container starts locally. |
| 2 | Backend health endpoint | complete | FastAPI app created with exact `GET /health` response and `/health/db`, `/health/llm`. |
| 3 | Database foundation | complete | Async SQLAlchemy 2, settings, Alembic, UUID models/migration for users, refresh tokens, characters, conversations, messages, memory items, relationship states, scheduled jobs. |
| 4 | Mock chat endpoint | complete | Mock LLM provider, `POST /chat/messages`, persisted user/assistant messages, `GET /conversations/{id}/messages`. |
| 5 | Frontend chat shell | complete | Next.js App Router, TypeScript, Tailwind, auth-first screen, dark mobile-friendly chat UI. |
| 6 | SSE streaming | complete | `POST /chat/stream` emits `message_start`, `token`, `message_done`; frontend progressively renders chunks and persists final assistant once. |
| 7 | Ollama provider | complete | `LLM_PROVIDER=mock\|ollama`; Ollama HTTP adapter tested with mocked HTTP only. |
| 8 | Persona prompt assembly | complete | Central prompt service includes safety boundaries, character profile, recent messages, memories, relationship, content mode. |
| 9 | Memory v1 | complete | `memory_items` table, manual memory API, conservative extraction, cheap text retrieval, prompt injection. pgvector extension and nullable vector column are present; embeddings are deferred. |
| 10 | Relationship state v1 | complete | Bounded deterministic trust/intimacy/warmth/tension/familiarity/attachment service and prompt injection. |
| 11 | Background jobs | complete | `scheduled_jobs` table and service for create/claim/done/failed with PostgreSQL `SKIP LOCKED`. Scheduler loop remains disabled/not started in tests. |
| 12 | Proactive messages | complete | Inactivity/proactive message service with SFW fallback and cooldown duplicate prevention; debug trigger exists. |
| 13 | Auth v1 | complete | Local register/login/me/logout, Argon2 password hashing, JWT bearer auth, protected user data endpoints. |
| 14 | Adult mode gates | complete | User age gate, explicit character age, `adult_mode_allowed`, requested content mode, structural SFW fallback; tests avoid explicit adult samples. |
| 15 | Debug/admin panel | complete | Private debug APIs plus frontend panel for prompt context, relationship, jobs, conversations, memories. |
| 16 | Export/backup | complete | Protected JSON export excludes password/token hashes/secrets/other users. `scripts/backup-db.example.sh` added for `pg_dump` backups. |
| 17 | Deployment templates | complete | Caddy/systemd templates existed; SSH deploy script corrected; GitHub Actions deploy skeleton added using secrets only. |
| 18 | Production hardening | complete | Env CORS, safe generic 500 handler, `/health/db`, `/health/llm`, strict `make verify`, clean frontend production audit. |
| 19 | MVP polish | complete | Mobile dark chat, timestamps, loading/streaming states, readable errors, memory/relationship/debug/export controls. |

## Commands run

- `docker compose up -d postgres` - passed.
- `cd apps/api && pip install -e ".[dev]"` - initial packaging config failed because setuptools discovered both `app` and `alembic`; fixed package discovery to `app*`, rerun passed.
- `cd apps/api && alembic upgrade head` - passed.
- `cd apps/api && pytest` - initial helper import issue and asyncpg pooled event-loop issue found; fixed test helper module and test `NullPool`, rerun passed: 15 tests.
- `cd apps/api && ruff check .` - initial style/line-length issues found; fixed, rerun passed.
- `cd apps/api && ruff format .` - passed.
- `cd apps/api && pytest && ruff check .` - passed after formatting.
- `cd apps/web && npm install` - passed. Initial Next 14 install produced production audit findings; upgraded to Next 16/React 19 and added a PostCSS override. Final install reports 0 vulnerabilities.
- `cd apps/web && npm run lint` - initial ESLint config needed Next 16 flat config and React effect cleanup; fixed, rerun passed.
- `cd apps/web && npm run build` - passed.
- `docker compose up -d postgres` - final run passed; container already running.
- `cd apps/api && pip install -e ".[dev]" && alembic upgrade head && pytest && ruff check . && ruff format .` - final run passed; 15 backend tests.
- `cd apps/web && npm install && npm run lint && npm run build` - final run passed; npm audit during install found 0 vulnerabilities.
- `make verify` - passed.
- `cd apps/api && uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload` - started locally.
- `curl -sS http://localhost:8000/health` - passed with `{"status":"ok","service":"eidolon-api"}`.
- `cd apps/web && npm run dev` - started locally on port 3000.
- `curl -I -sS http://localhost:3000` - passed with HTTP 200.
- `cd apps/api && pytest tests/test_auth_chat.py tests/test_health.py && ruff check .` - passed after removing raw exception text from stream error events.
- `cd apps/api && pytest && ruff check . && ruff format .` - final hardening rerun passed; 15 backend tests.
- `cd apps/web && npm run lint && npm run build` - final hardening rerun passed.
- `cd apps/api && pytest && ruff check . && ruff format .` - rerun passed after making test cleanup clear the local database after each test too.
- `cd apps/api && source .venv/bin/activate && pytest && ruff check . && ruff format .` - passed after registration/Codespaces fix; 16 backend tests.
- `cd apps/web && npm install && npm run lint && npm run build` - passed after registration/Codespaces fix.
- `curl -sS http://localhost:8000/health` - passed.
- `curl -i -sS -X OPTIONS http://localhost:8000/auth/register -H 'Origin: http://localhost:3000' -H 'Access-Control-Request-Method: POST' -H 'Access-Control-Request-Headers: content-type'` - passed with `access-control-allow-origin: http://localhost:3000`.
- `curl -i -sS http://localhost:8000/auth/register -H 'Content-Type: application/json' -H 'Origin: http://localhost:3000' --data '{"email":"debug-register@example.com","password":"good-password","display_name":"Debug"}'` - passed with HTTP 201.
- `cd apps/api && source .venv/bin/activate && pytest && ruff check .` - final rerun passed and cleared the throwaway curl-created user from the test database.
- `git diff --check` - passed.

## Known limitations

- `rg` is not installed in this Codespace, so file discovery is using `find`.
- APScheduler itself is not wired to a running loop yet; the PostgreSQL-backed job foundation is implemented and scheduler remains disabled in tests.
- Memory embeddings are not generated yet. The database has pgvector support and a nullable vector column, while MVP retrieval uses lightweight text matching.
- The frontend is a compact single-page MVP rather than a multi-route settings/debug area.
