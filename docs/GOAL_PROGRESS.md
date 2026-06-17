# Goal Progress

Codex should update this file during `/goal` runs.

## Current status

Local MVP is implemented and validated. FastAPI and Next.js dev servers start locally, `/health` returns the exact expected payload, and the app supports register/login/chat/stream/refresh with persisted history plus persona, memory, relationship, proactive/debug, adult gates, export, and deploy/backup templates.

## Level 2 goal run - audit checkpoint

Started on 2026-06-17.

Files/docs read:
- `AGENTS.md`, `README.md`, all `docs/*.md`, env examples, backend app code, Alembic migration, tests, CI, and the current single-component web UI.

Findings:
- Register/login/chat/stream/persistence are already implemented with local auth, owner-scoped endpoints, mock default LLM, optional Ollama provider, safe generic errors, CORS normalization, and backend/frontend validation history.
- No forbidden runtime dependency was found in project manifests. The app remains text/state only.
- Memory v1 exists but needs Level 2 schema fields, edit/delete, dedupe/merge, contradiction metadata, forgetting/decay, richer retrieval scoring, and episodic journals.
- Relationship v1 is bounded and deterministic, but Level 2 needs mood/conflict/repair metadata, tags, decay, and a visible timeline.
- Proactive v1 can queue a cooldown-protected fallback message, but Level 2 needs scheduled-job helper coverage for inactivity, morning/goodnight, thinking-of-you, milestone, and unresolved-thread nudges.
- Adult gates are structural and SFW by default, but Level 2 needs clearer settings state and blocked-state explanations in API/UI.
- Debug APIs are authenticated and owner-scoped, but the frontend currently renders the full prompt in the debug panel; Level 2 should keep debug private, compact, and separate from chat.
- The frontend is a compact single-page MVP. Level 2 needs panels for conversations/search, memory edit/delete, journal, relationship timeline, adult settings, app settings, and data wipe controls without adding heavy UI dependencies.

Next checkpoint:
- Implement backend Level 2 state, services, APIs, migration, and tests while preserving existing auth/chat/persistence flows.

## Level 2 goal run - backend checkpoint

Completed in this checkpoint:
- Added Alembic migration `0002_level2_state` for Memory v2 fields, Relationship v2 fields, and `episodic_journals`.
- Upgraded `memory_items` support with `importance`, `pinned`, `contradiction_group`, dedupe/merge, contradiction metadata, recall scoring, decay/forgetting, edit/delete, and clear APIs.
- Added deterministic episodic journals with summaries, emotional tags, unresolved threads, callbacks, and adult-mode detail redaction for durable journal text.
- Added `reasoning_context_builder` to assemble active context, semantic memories, episodic journals, relationship state, adult gate status, and time/day context without exposing chain-of-thought.
- Upgraded prompt assembly to `persona_memory_relationship_episode_v2` with compact persona, relationship mood/repair, memories, journals, callbacks, safety gates, and private-context instructions.
- Upgraded relationship state with mood, conflict state, repair-needed flag, tags, deterministic decay, and timeline entries in metadata.
- Added proactive scheduled-job hooks for inactivity, morning, goodnight, thinking-of-you, milestone, and unresolved-thread nudges.
- Added adult gate status API, reroll endpoint, edit-message endpoint, clear/delete conversation endpoints, journal APIs, memory hygiene APIs, and export coverage for journals/new fields.
- Sanitized debug output from full raw prompt to bounded `prompt_preview` plus structured state.
- Added production env validation for placeholder JWT secret and invalid LLM providers.

Commands run:
- `docker compose up -d postgres` - passed after pulling `pgvector/pgvector:pg16`.
- `cd apps/api && python -m pip install -e ".[dev]"` - passed using user site packages because the existing `.venv` entrypoints were stale.
- `cd apps/api && alembic upgrade head && pytest -q` - passed; migration upgraded through `0002_level2_state`; 28 tests passed.
- `cd apps/api && ruff check . --fix` - fixed import ordering; remaining line-length issues were patched.
- `cd apps/api && ruff check . && pytest -q` - passed; 28 tests passed.

Known limitations:
- Embedding generation remains intentionally deferred; pgvector storage is available, retrieval is deterministic keyword/recency/importance scoring.
- APScheduler is still not started in tests; proactive Level 2 creates PostgreSQL scheduled jobs safely, but no live worker loop is enabled by default.
- Reroll creates an alternate assistant message with metadata rather than replacing history.

Next checkpoint:
- Expand the lightweight Next.js UI for Level 2 panels and controls without adding forbidden/heavy dependencies.

## Level 2 goal run - frontend checkpoint

Completed in this checkpoint:
- Reworked the single-page Next.js shell into a responsive Level 2 app layout with conversation rail, central streaming chat, and multi-panel state inspector/editor.
- Added UI coverage for conversations, chat search, reroll, edit-message, proactive check-in trigger, character editor, memory editor, journal view/create, relationship metrics/timeline, adult gate settings/status, app settings, debug preview, export, clear chat, clear memories, and delete conversation.
- Kept the frontend dependency set unchanged: Next.js, React, TypeScript, Tailwind only.
- Removed full raw prompt rendering from the UI; debug shows bounded `prompt_preview`, prompt version/provider, jobs, and scoped conversation state.
- Improved empty/error/notice states, timestamps, streaming display, mobile stacking, and relationship/adult blocked-state visibility.

Commands run:
- `cd apps/web && npm run lint` - passed.
- `cd apps/web && npm run build` - passed.

Known limitations:
- The UI remains a single App Router page rather than separate routes; this keeps the MVP light but makes the component large.
- Message editing updates the stored user message but does not automatically regenerate subsequent assistant messages.

Next checkpoint:
- Run full backend and frontend validation commands, apply formatting, and record final results.

## Level 2 goal run - final validation

Completed in this checkpoint:
- Updated docs for Level 2 data model, API contract, memory, relationship, proactive jobs, frontend UX, testing, and progress tracking.
- Confirmed no forbidden runtime dependency additions. No package manifests added Redis, Celery, Supabase, Firebase, LangChain, Pinecone, Chroma, Clerk, Auth0, NextAuth, Stripe, Socket.io, Three.js, Framer Motion, WebRTC, native mobile, Kubernetes, multimedia, paid APIs, or external vector DB.
- Preserved register/login/chat/SSE/persistence flows while adding Level 2 memory, journals, relationship timeline, adult-gate status, proactive hooks, privacy controls, and UI panels.

Commands run:
- `docker compose up -d postgres` - passed; `eidolon-postgres` running.
- `cd apps/api && python -m pip install -e ".[dev]"` - passed using user site packages because the checked-in `.venv` entrypoints were stale in this environment.
- `cd apps/api && alembic upgrade head && pytest && ruff check . && ruff format .` - passed; 28 tests passed; Ruff passed; 2 files formatted.
- `cd apps/api && pytest -q && ruff check .` - passed after formatting; 28 tests passed.
- `cd apps/web && npm install` - passed; 0 vulnerabilities.
- `cd apps/web && npm run lint && npm run build` - passed.
- `git diff --check` - passed.
- Forbidden-dependency text scan - no runtime/package-manifest forbidden additions found; hits were docs or ordinary export-related symbols.
- `cd apps/api && python -m uvicorn app.main:app --host 0.0.0.0 --port 8000` - started locally.
- `curl -sS http://localhost:8000/health` - passed with `{"status":"ok","service":"eidolon-api"}`.
- `cd apps/web && npm run dev -- --port 3000` - started locally.
- `curl -I -sS http://localhost:3000` - passed with HTTP 200.

Known limitations:
- Embeddings are still storage-ready but not generated; retrieval is deterministic keyword/recency/importance scoring.
- The scheduler worker loop remains disabled by default; proactive Level 2 creates PostgreSQL-backed jobs safely but does not run APScheduler in tests.
- The Level 2 web UI is still a single lightweight component/page. It is buildable and responsive, but a future pass could split panels into smaller components.
- `apps/web/next-env.d.ts` was updated by the production Next build from dev route types to build route types.

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

## Debug update - mock LLM response behaviour

Root cause inspected on 2026-06-17:
- `Settings.llm_provider` defaults to `mock`, and `get_llm_provider()` routes to Ollama only when `LLM_PROVIDER=ollama`.
- The chat flow already passed the assembled prompt into the provider, including character, speech style, memories, recent messages, and relationship state.
- `MockLLMProvider` ignored almost all of that prompt and returned the shallow echo response `I'm here with you. I heard: ...`.

Fixes:
- `MockLLMProvider` now parses the assembled prompt for character name, speech style, first relevant memory, recent-message presence, and relationship summary.
- Mock responses are deterministic, short, SFW, explicitly marked with `[mock:<character>]`, and no longer echo the current user message.
- Mock streaming now emits natural phrase-like chunks that join back to the exact generated response.
- Ollama provider remains available for `LLM_PROVIDER=ollama`; HTTP failures or invalid responses now raise a controlled provider-unavailable error that the chat API returns cleanly.
- Debug prompt context now includes `llm_provider`, and persisted assistant message metadata already stores `provider: mock`.
- README now documents switching between mock and Ollama mode.

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
- `cd apps/api && source .venv/bin/activate && pytest && ruff check . && ruff format .` - initial LLM-provider rerun found a mock streaming trailing-space assertion and Ruff import ordering; both fixed.
- `cd apps/api && source .venv/bin/activate && ruff check . --fix && ruff format . && pytest && ruff check .` - passed after formatting provider tests.
- `cd apps/api && source .venv/bin/activate && pytest && ruff check . && ruff format .` - final LLM-provider validation passed; 22 backend tests.

## Known limitations

- `rg` is not installed in this Codespace, so file discovery is using `find`.
- APScheduler itself is not wired to a running loop yet; the PostgreSQL-backed job foundation is implemented and scheduler remains disabled in tests.
- Memory embeddings are not generated yet. The database has pgvector support and a nullable vector column, while MVP retrieval uses lightweight text matching.
- The frontend is a compact single-page MVP rather than a multi-route settings/debug area.
