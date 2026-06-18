# Goal Progress

Codex should update this file during `/goal` runs.

## Current status

Local MVP is implemented and validated. FastAPI and Next.js dev servers start locally, `/health` returns the exact expected payload, and the app supports register/login/refresh/logout/chat/stream with persisted history plus persona, memory, relationship decay/timeline, type-aware PostgreSQL-backed proactive/debug jobs, stricter adult gates, migration-backed tests, export, account erasure, and deploy/backup templates. The frontend is now split into focused app shell, rail, chat, inspector, panel, runtime-status, companion-state, navigation, knowledge, and controller modules.

## World-class continuation - final runtime smoke

Completed in this checkpoint:
- Restarted fresh API and web dev servers from the current working tree.
- Confirmed API, database, mock LLM, and web root health after the latest safety, migration, privacy, docs, and Makefile hardening.

Commands run:
- `cd apps/api && python -m uvicorn app.main:app --host 0.0.0.0 --port 8000` - running on port 8000.
- `cd apps/web && npm run dev` - running on port 3000.
- `curl -sS -i http://localhost:8000/health` - passed with HTTP 200.
- `curl -sS -i http://localhost:8000/health/db` - passed with HTTP 200.
- `curl -sS -i http://localhost:8000/health/llm` - passed with HTTP 200 and mock provider.
- `curl -sS -I http://localhost:3000` - passed with HTTP 200.

Known limitations:
- Browser screenshot tooling is still not installed; UI validation is lint/build plus HTTP runtime smoke.

## World-class continuation - local verify hardening

Completed in this checkpoint:
- Updated `make verify` to run Alembic migrations before backend tests.
- Added backend `ruff format --check` to local verification, matching CI's formatting gate.
- Added `api-migrate` and `api-format-check` Make targets.
- Proved the strengthened local verify chain end to end.

Commands run:
- `make verify` - first run hung at Alembic because the unapproved sandboxed `make` process could not reach local Postgres.
- `make verify` with approval - passed: Alembic upgrade, 45 backend tests, Ruff check, Ruff format check, frontend lint, and frontend build.
- `git diff --check` - passed before this progress-log update.

Known limitations:
- `make verify` needs local Postgres access; in this sandboxed environment that means running it with the approved `make verify` prefix.

## World-class continuation - memory extraction safety parity

Completed in this checkpoint:
- Centralized structural blocked-content detection in `app.services.safety`.
- Kept live chat behavior as a readable 400 while allowing non-HTTP callers to share the same safety predicate.
- Updated Memory v2 extraction so inline and scheduled/backfill extraction silently skip structurally blocked content instead of making it durable.
- Added a scheduled memory-extract regression proving blocked structural content is skipped and no memory row is created.
- Updated safety docs for memory extraction parity.

Commands run:
- `cd apps/api && pytest` - passed; 45 tests.
- `cd apps/api && ruff check .` - passed.
- `cd apps/api && ruff format .` - passed; 50 files unchanged.

Known limitations:
- The structural blocked-content screen remains pattern/term based; it is not a full moderation classifier.

## World-class continuation - export isolation coverage

Completed in this checkpoint:
- Added a cross-user export regression test proving one account export does not include another user's email, conversation id, or message/memory content.
- Kept the existing secret/hash exclusion test intact.
- Verified the migration-backed backend suite with the new privacy coverage.

Commands run:
- `cd apps/api && pytest` - passed; 44 tests.
- `cd apps/api && ruff check .` - passed.
- `cd apps/api && ruff format .` - passed; 50 files unchanged.

Known limitations:
- Export is account-scoped JSON only; richer selective export/import remains future UX polish.

## World-class continuation - docs consistency pass

Completed in this checkpoint:
- Updated memory docs so episodic journals, contradiction metadata, decay/forgetting, and edit/delete/clear controls are described as implemented Level 2 behavior rather than future work.
- Updated relationship docs so absence decay via reads and jobs is described as current behavior.
- Updated roadmap and risk docs for account erasure and memory edit/delete controls.
- Retitled the frontend original nice-to-have list to avoid implying implemented Level 2 controls are still missing.
- Rescanned docs outside the historical progress log for stale “later/not implemented/Level 2 needs” language.

Commands run:
- Stale-doc scan for obsolete “later/not implemented” phrases outside `docs/GOAL_PROGRESS.md` - no matches.
- `git diff --check` - passed before this progress-log update.

Known limitations:
- Historical checkpoint entries in `docs/GOAL_PROGRESS.md` intentionally preserve older known limitations and findings from the time they were written.

## World-class continuation - migration-backed test hardening

Completed in this checkpoint:
- Changed backend test setup to apply Alembic `upgrade head` at session startup instead of creating tables directly from SQLAlchemy metadata.
- Added a migration regression test that confirms the test database is at `0002_level2_state`, has Memory v2 columns, has Relationship v2 columns, and includes the `episodic_journals` table.
- Added Alembic `path_separator = os` configuration to remove the migration config deprecation warning from test runs.
- Updated testing docs so future tests keep migrations in the validation path.

Commands run:
- `cd apps/api && pytest` - initially passed with 43 tests and one Alembic config warning.
- `cd apps/api && ruff check . --fix` - fixed test import ordering.
- `cd apps/api && pytest` - passed after Alembic config update; 43 tests and no warnings.
- `cd apps/api && ruff check .` - passed.
- `cd apps/api && ruff format .` - passed; 50 files unchanged after the import fix.
- `git diff --check` - passed.

Known limitations:
- Migration tests assert the current head and critical Level 2 schema shape. They do not perform destructive downgrade/upgrade cycles against the shared local development database.

## World-class continuation - adult gate persistence hardening

Completed in this checkpoint:
- Added backend validation so character create/update requests cannot persist `adult_mode_allowed=true` without an explicit character age of 18 or older.
- Added structural minor-age pattern blocking before chat prompt assembly or memory extraction.
- Updated the adult settings panel so the adult-mode checkbox is disabled until the character has an explicit 18+ age, and lowering the age clears the draft adult-mode flag.
- Added API regression tests for invalid adult-mode character configuration and structural minor-age prompt rejection.
- Updated the safety and API contract docs.

Commands run:
- `docker compose up -d postgres` - initially blocked by Docker socket sandbox permissions; passed after approval, with `eidolon-postgres` running.
- `cd apps/api && pip install -e ".[dev]"` - passed.
- `cd apps/api && alembic upgrade head` - passed.
- `cd apps/api && pytest` - passed; 42 tests.
- `cd apps/api && ruff check .` - passed.
- `cd apps/api && ruff format .` - passed; 49 files unchanged.
- `cd apps/web && npm install` - passed; already up to date.
- `cd apps/web && npm run lint` - passed.
- `cd apps/web && npm run build` - passed after restoring the generated `next-env.d.ts` dev-route reference.
- `curl -sS -i http://localhost:8000/health` - passed with HTTP 200 after starting a fresh API server.
- `curl -sS -i http://localhost:8000/health/db` - passed with HTTP 200.
- `curl -sS -i http://localhost:8000/health/llm` - passed with HTTP 200 and mock provider.
- `curl -sS -I http://localhost:3000` - passed with HTTP 200 after starting a fresh web dev server.
- Forbidden dependency name scan across package/config/docs - no matches.
- `git diff --check` - passed.

Known limitations:
- Safety rejection is a structural term/pattern screen, not a comprehensive classifier. It is intentionally conservative and SFW-testable for the zero-cost MVP.

## World-class continuation - proactive message realism

Completed in this checkpoint:
- Added SFW message variants for inactivity, morning, goodnight, thinking-of-you, milestone, unresolved-thread, and manual proactive jobs.
- Added `proactive_type` and `proactive_label` metadata to proactive assistant messages and job result payloads.
- Updated the chat message metadata display to show the user-facing proactive label instead of a generic proactive marker.
- Preserved per-conversation cooldown across different proactive variants so queued morning/goodnight/thinking nudges cannot stack into spam.
- Updated debug proactive trigger to use the manual proactive variant.
- Added tests proving the scheduler creates the thinking-of-you variant and that cross-variant cooldown skips the second due proactive job.
- Updated proactive requirements and background-job docs.

Commands run:
- `cd apps/api && pytest` - passed; 41 tests.
- `cd apps/api && ruff check .` - passed.
- `cd apps/api && ruff format .` - passed; 49 files unchanged.
- `cd apps/web && npm run lint` - passed.
- `cd apps/web && npm run build` - passed after restoring the generated `next-env.d.ts` dev-route reference.
- `cd apps/api && alembic upgrade head` - passed.
- `curl -sS -i http://localhost:8000/health` - passed with HTTP 200.
- `curl -sS -i http://localhost:8000/health/db` - passed with HTTP 200.
- `curl -sS -i http://localhost:8000/health/llm` - passed with HTTP 200 and mock provider.
- `curl -sS -I http://localhost:3000` - passed with HTTP 200.
- `git diff --check` - passed.

Known limitations:
- Proactive text is deterministic SFW fallback text; it does not call the LLM in background jobs, keeping tests/Ollama optional and avoiding runtime dependency failures.
- Browser-level visual verification is still not installed; no browser binary was available in the workspace.

## World-class continuation - scheduled memory extraction

Completed in this checkpoint:
- Implemented `memory_extract` scheduled-job processing in the PostgreSQL-backed scheduler.
- Supports conversation-level recent user-message scans and single-message extraction through `conversation_id` plus `message_id` payloads.
- Reuses the existing Memory v2 extractor, including unsafe-term filtering, dedupe/merge, contradiction metadata, confidence, and scoring behavior.
- Adds safe failure handling when a memory-extract job references a missing, non-user, or cross-scope message.
- Added tests proving successful job extraction persists one memory and invalid message jobs fail with safe error text.
- Updated memory and background-job docs.

Commands run:
- `cd apps/api && pytest` - passed; 40 tests.
- `cd apps/api && ruff check .` - passed.
- `cd apps/api && ruff format .` - passed; 49 files unchanged.
- `cd apps/web && npm run lint` - passed.
- `cd apps/web && npm run build` - passed after restoring the generated `next-env.d.ts` dev-route reference.
- `cd apps/api && alembic upgrade head` - passed.
- `curl -sS -i http://localhost:8000/health` - passed with HTTP 200.
- `curl -sS -i http://localhost:8000/health/db` - passed with HTTP 200.
- `curl -sS -i http://localhost:8000/health/llm` - passed with HTTP 200 and mock provider.
- `curl -sS -I http://localhost:3000` - passed with HTTP 200.
- `git diff --check` - passed.

Known limitations:
- Chat still extracts obvious memories inline; scheduled extraction is now available for backlog or future async paths.
- Browser-level visual verification is still not installed; no browser binary was available in the workspace.

## World-class continuation - relationship decay persistence

Completed in this checkpoint:
- Added `get_current_relationship()` so relationship reads, debug prompt previews, and prompt reasoning context apply and persist absence decay before returning state.
- Queued one pending `relationship_decay` job per user-character pair after relationship updates.
- Added scheduler support for due `relationship_decay` jobs, with safe result metadata and automatic scheduling of the next future decay check.
- Preserved conversation cleanup semantics by deleting conversation-scoped jobs while leaving character-scoped relationship maintenance jobs intact.
- Added tests proving chat queues relationship decay, relationship reads persist absence drift, scheduler jobs apply decay, and recurring future decay is queued.
- Updated relationship, background-job, and acceptance docs.

Commands run:
- `cd apps/api && pytest` - first rerun exposed stale assumptions in conversation-job cleanup tests; fixed to check only conversation-scoped jobs.
- `cd apps/api && pytest` - passed after recurring relationship-decay scheduling; 38 tests.
- `cd apps/api && ruff check .` - passed.
- `cd apps/api && ruff format .` - passed; 49 files unchanged.
- `cd apps/web && npm run lint` - passed.
- `cd apps/web && npm run build` - passed after restoring the generated `next-env.d.ts` dev-route reference.
- `cd apps/api && alembic upgrade head` - passed.
- `curl -sS -i http://localhost:8000/health` - passed with HTTP 200 after starting a fresh API server.
- `curl -sS -i http://localhost:8000/health/db` - passed with HTTP 200.
- `curl -sS -i http://localhost:8000/health/llm` - passed with HTTP 200 and mock provider.
- `curl -sS -I http://localhost:3000` - initially found no web dev server; passed with HTTP 200 after starting `npm run dev`.
- `git diff --check` - passed.

Known limitations:
- Browser-level visual verification is still not installed; no browser binary was available in the workspace.

## World-class continuation - privacy action UX hardening

Completed in this checkpoint:
- Kept account-deleted, session-expired, and logged-out notices visible on the auth screen after app state is cleared.
- Converted privacy actions for proactive check-ins, chat clearing, export, and account deletion to report readable UI errors instead of allowing unhandled promise failures.
- Added a zero-argument public logout wrapper so React click events cannot be mistaken for internal reset options.
- Preserved real non-auth bootstrap errors as errors while using a session-expired notice only for 401 session failures.
- Added an export-ready notice after JSON export is prepared.

Commands run:
- `cd apps/web && npm run lint` - passed.
- `cd apps/web && npm run build` - passed after restoring the generated `next-env.d.ts` dev-route reference.
- `cd apps/api && pytest` - passed; 36 tests.
- `cd apps/api && ruff check .` - passed.
- `cd apps/api && ruff format .` - passed; 49 files unchanged.
- `curl -sS -i http://localhost:8000/health` - passed with HTTP 200.
- `curl -sS -i http://localhost:8000/health/db` - passed with HTTP 200.
- `curl -sS -i http://localhost:8000/health/llm` - passed with HTTP 200 and mock provider.
- `curl -sS -I http://localhost:3000` - passed with HTTP 200.
- `git diff --check` - passed.

Known limitations:
- Browser-level visual verification is still not installed.

## World-class continuation - refresh-token sessions

Completed in this checkpoint:
- Activated the existing `refresh_tokens` table with random opaque refresh tokens, SHA-256 token hashes, expiry validation, rotation, and revocation.
- Added `JWT_REFRESH_TOKEN_EXPIRE_DAYS` settings validation and a typed refresh lifetime helper.
- Updated register and login to return access plus refresh tokens.
- Added `POST /auth/refresh` rotation and `POST /auth/logout` refresh-token revocation.
- Wired the frontend to persist refresh tokens locally, rotate them after access-token 401s, and revoke them on logout.
- Added tests for refresh-token rotation, old-token reuse rejection, logout revocation, and invalid refresh-token lifetime config.
- Updated auth/data-model/tech-stack docs to reflect PostgreSQL-backed refresh-token sessions.

Commands run:
- `cd apps/api && pytest` - passed; 36 tests.
- `cd apps/api && ruff check .` - passed.
- `cd apps/api && ruff format .` - passed; 49 files unchanged.
- `cd apps/web && npm run lint` - passed.
- `cd apps/web && npm run build` - passed after restoring the generated `next-env.d.ts` dev-route reference.
- Local Node auth smoke for register, refresh rotation, old refresh-token rejection, logout revocation, login, and account deletion - first blocked by sandbox local-socket `EPERM`, rerun with approval passed.
- `cd apps/api && alembic upgrade head` - passed.
- `curl -sS -i http://localhost:8000/health` - passed with HTTP 200.
- `curl -sS -i http://localhost:8000/health/db` - passed with HTTP 200.
- `curl -sS -i http://localhost:8000/health/llm` - passed with HTTP 200 and mock provider.
- `curl -sS -I http://localhost:3000` - passed with HTTP 200.
- `git diff --check` - passed.

Known limitations:
- Refresh tokens are stored in browser localStorage for the lightweight MVP; a future hardened deployment can move them to secure HTTP-only cookies if the frontend/backend deployment shape supports it.
- Browser-level visual verification is still not installed.

## World-class continuation - account erasure

Completed in this checkpoint:
- Added `DELETE /account` with current-password verification and exact `DELETE MY ACCOUNT` confirmation.
- Uses PostgreSQL cascades to remove the current user and dependent characters, conversations, messages, memories, journals, relationship state, refresh tokens, and scheduled jobs.
- Added endpoint tests for bad-password rejection, successful account erasure, stale-token invalidation, survivor-user preservation, and absence of erased user-scoped rows.
- Added the account deletion control to the data panel behind the existing destructive-action confirmation plus password and typed phrase.
- Documented the new endpoint in `docs/06_API_CONTRACT.md`.

Commands run:
- `cd apps/api && pytest` - passed; 34 tests.
- `cd apps/api && ruff check .` - passed.
- `cd apps/api && ruff format .` - passed; 49 files unchanged.
- `cd apps/web && npm run lint` - passed.
- `cd apps/web && npm run build` - passed after restoring the generated `next-env.d.ts` dev-route reference.
- `cd apps/api && alembic upgrade head` - passed.
- `curl -sS -i http://localhost:8000/health` - passed with HTTP 200 after restarting the API server.
- `curl -sS -i http://localhost:8000/health/db` - passed with HTTP 200.
- `curl -sS -i http://localhost:8000/health/llm` - passed with HTTP 200 and mock provider.
- `curl -sS -I http://localhost:3000` - passed with HTTP 200.
- `git diff --check` - passed.

Known limitations:
- Account deletion relies on database cascades rather than a visible deletion audit log.
- Browser-level visual verification is still not installed.

## World-class continuation - conversation wipe and job cleanup

Completed in this checkpoint:
- Updated conversation message clearing to also remove scheduled jobs scoped to that conversation payload.
- Updated conversation deletion to remove messages and scheduled jobs before deleting the conversation row.
- Fixed a SQLAlchemy delete edge case where ORM deletion attempted to null non-null `messages.conversation_id` values.
- Added tests proving clear-chat and delete-thread operations remove queued proactive jobs.

Commands run:
- `cd apps/api && pytest` - first rerun found the ORM nulling issue in conversation deletion.
- `cd apps/api && pytest` - passed after switching deletion to explicit message/job/conversation cleanup; 33 tests.
- `cd apps/api && ruff check .` - passed.
- `cd apps/api && ruff format .` - passed; 49 files unchanged.
- `curl -sS -i http://localhost:8000/health` - passed with HTTP 200 after restarting the API server.
- `curl -sS -i http://localhost:8000/health/db` - passed with HTTP 200 after restarting the API server.
- `curl -sS -I http://localhost:3000` - passed with HTTP 200.
- `git diff --check` - passed.

Known limitations:
- Conversation-scoped scheduled jobs are matched by JSON payload because the MVP schema does not give `scheduled_jobs` a first-class `conversation_id` column.
- Browser-level visual verification is still not installed.

## World-class continuation - production debug route hardening

Completed in this checkpoint:
- Added `ENABLE_DEBUG_ROUTES` config with production-default debug route lockout.
- Kept debug endpoints automatically available in development and testing so the local debug panel and test suite remain ergonomic.
- Added a shared debug-route guard returning a generic 404 when production debug routes are not explicitly enabled.
- Added config coverage proving production requires opt-in while testing remains available.
- Documented the production opt-in behavior in `.env.example` and `docs/06_API_CONTRACT.md`.

Commands run:
- `cd apps/api && pytest` - passed; 32 tests.
- `cd apps/api && ruff check . --fix` - fixed import ordering in `app/api/debug.py`.
- `cd apps/api && ruff check .` - passed.
- `cd apps/api && ruff format .` - passed; 49 files unchanged.
- `curl -sS -i http://localhost:8000/health` - passed with HTTP 200 after restarting the API server.
- `curl -sS -i http://localhost:8000/health/db` - passed with HTTP 200 after restarting the API server.
- `curl -sS -i http://localhost:8000/debug/jobs` - returned authenticated-only HTTP 401 in development, confirming the dev route remains reachable but private.
- `git diff --check` - passed.

Known limitations:
- There is still no admin role model; debug remains authenticated, owner-scoped, and environment-gated rather than role-gated.
- Browser-level visual verification is still not installed.

## World-class continuation - PostgreSQL scheduler runner

Completed in this checkpoint:
- Added APScheduler as the lightweight, approved wake-up mechanism for PostgreSQL-owned `scheduled_jobs`.
- Added scheduler settings for enablement, tick interval, job batch limit, proactive inactivity, and proactive cooldown with startup validation.
- Added `app.services.scheduler.process_due_jobs` for deterministic job processing without starting a background loop in tests.
- Wired FastAPI lifespan to start APScheduler only when `ENABLE_SCHEDULER=true`; tests keep `ENABLE_SCHEDULER=false`.
- Implemented safe processing for `maintenance_noop`, Level 2 proactive job types, and `proactive_message_create`; unsupported jobs are marked failed with bounded safe text.
- Fixed the queued proactive path so due jobs trust their `run_at` timing while cooldown rules still prevent repeated check-ins.
- Documented scheduler env vars and the PostgreSQL source-of-truth lifecycle in `docs/10_BACKGROUND_JOBS.md`.

Commands run:
- `cd apps/api && pip install -e ".[dev]"` - passed; installed APScheduler and tzlocal.
- `cd apps/api && alembic upgrade head` - passed.
- `cd apps/api && pytest` - passed; 31 tests.
- `cd apps/api && ruff check .` - passed.
- `cd apps/api && ruff format .` - passed; 49 files unchanged.
- `cd apps/web && npm run lint` - passed.
- `cd apps/web && npm run build` - passed after restoring the generated `next-env.d.ts` dev-route reference.
- `curl -sS -i http://localhost:8000/health` - passed with HTTP 200.
- `curl -sS -i http://localhost:8000/health/db` - passed with HTTP 200.
- `curl -sS -i http://localhost:8000/health/llm` - passed with HTTP 200 and mock provider.
- `curl -sS -i http://localhost:3000` - passed with HTTP 200.
- `git diff --check` - passed.

Known limitations:
- The scheduler is implemented and wired, but remains disabled by default until deployment sets `ENABLE_SCHEDULER=true`.
- Browser-level visual verification is still not installed.

## World-class continuation - privacy controls and operational debug

Completed in this checkpoint:
- Extracted proactive check-in, clear-chat, and account export actions into `components/eidolon/use-privacy-controller.ts`.
- Reduced the main controller hook to 302 lines while preserving export, proactive queueing, chat clearing, and side-state refresh behavior.
- Upgraded the data panel with account-scoped export language, message/memory/thread impact counts, current-thread context, and an explicit confirmation gate before destructive cleanup actions become available.
- Upgraded the debug panel with provider, pending-job, failed-job, prompt-version, prompt-size, job status, and conversation recency summaries while keeping prompt preview bounded and private.
- Upgraded the settings panel with local-account and age-gate context plus clearer logout semantics.

Commands run:
- `cd apps/web && npm run lint` - passed.
- `cd apps/web && npm run build` - passed after restoring the generated `next-env.d.ts` dev-route reference.
- `cd apps/api && alembic upgrade head` - passed.
- `cd apps/api && pytest` - passed; 29 tests.
- `cd apps/api && ruff check .` - passed.
- `cd apps/api && ruff format .` - passed; 48 files unchanged.
- `curl -sS http://127.0.0.1:8000/health && curl -sS http://127.0.0.1:8000/health/db && curl -sS http://127.0.0.1:8000/health/llm` - passed with API ok, DB ok, LLM mock ok after restarting dev servers.
- `curl -I http://127.0.0.1:3000` - passed with HTTP 200 after restarting dev servers.

Known limitations:
- The main controller still owns auth form state, session bootstrap, content mode, and global busy/error/notice state.
- Browser-level visual verification is still not installed.

## World-class continuation - companion state and inspector cockpit

Completed in this checkpoint:
- Extracted relationship, adult-status, jobs, debug payload, panel selection, timeline derivation, and side-state refresh into `components/eidolon/use-companion-state-controller.ts`.
- Reduced the main controller hook from 376 lines to 341 lines while preserving auth bootstrap, side-state refresh, memory/journal hydration, chat loading, and runtime state reset.
- Upgraded the inspector from a plain tab grid into grouped State/Memory/Control navigation with live badges for mood, warmth, memory count, journal count, content mode, provider, and conversation count.
- Added an active inspector header with concise summaries for the selected panel while keeping prompt/debug details confined to the debug panel.
- Kept the UI dependency-free and text-first.

Commands run:
- `cd apps/web && npm run lint` - passed.
- `cd apps/web && npm run build` - passed after Turbopack port-binding approval.
- `cd apps/api && alembic upgrade head` - passed.
- `cd apps/api && pytest` - passed; 29 tests.
- `cd apps/api && ruff check .` - passed.
- `cd apps/api && ruff format .` - passed; 48 files unchanged.
- `curl -sS http://127.0.0.1:8000/health && curl -sS http://127.0.0.1:8000/health/db && curl -sS http://127.0.0.1:8000/health/llm` - passed with API ok, DB ok, LLM mock ok.
- `curl -I http://127.0.0.1:3000` - passed with HTTP 200.

Known limitations:
- The main controller still owns auth/account, proactive trigger, data export, and clear-message orchestration.
- Browser-level visual verification is still not installed.

## World-class continuation - navigation controller and rail command surface

Completed in this checkpoint:
- Extracted character, conversation, title, and thread-search state plus selection/create/save/delete/search handlers into `components/eidolon/use-navigation-controller.ts`.
- Reduced the main controller hook from 571 lines to 376 lines while preserving auth bootstrap, chat loading, side-state refresh, character editing, thread creation, title saving, and search behavior.
- Upgraded the workspace rail with active-first character ordering, per-character thread counts, profile metadata, thread chronology, clearer current-character thread counts, enter-to-create character flow, and explicit search empty states.
- Kept the rail text-first and dependency-free; no new frontend libraries were added.

Commands run:
- `cd apps/web && npm run lint` - passed.
- `cd apps/web && npm run build` - passed after removing stale bootstrap setters and restoring generated `next-env.d.ts` churn.
- `cd apps/api && alembic upgrade head` - passed.
- `cd apps/api && pytest` - passed; 29 tests.
- `cd apps/api && ruff check .` - passed.
- `cd apps/api && ruff format .` - passed; 48 files unchanged.
- `curl -sS http://127.0.0.1:8000/health && curl -sS http://127.0.0.1:8000/health/db && curl -sS http://127.0.0.1:8000/health/llm` - passed with API ok, DB ok, LLM mock ok.
- `curl -I http://127.0.0.1:3000` - passed with HTTP 200.

Known limitations:
- The main controller still owns auth/account, relationship/debug side state, proactive trigger, data export, and clear-message orchestration.
- Browser-level visual verification is still not installed.

## World-class continuation - knowledge controller and continuity panels

Completed in this checkpoint:
- Extracted memory and journal form state plus add/edit/pin/delete/forget/clear/create handlers into `components/eidolon/use-knowledge-controller.ts`.
- Reduced the main controller hook from 690 lines to 571 lines while preserving auth, chat, persistence, memory, journal, and data-clear behavior.
- Upgraded the memory panel with stored/pinned/confidence stats, contradiction visibility, pinned-first ordering, recalled timestamps, and compact memory-quality metrics.
- Upgraded the journal panel with entry/open-thread/callback stats, emotional marker count, importance-first ordering, and unresolved-thread callouts.
- Kept the UI text-first, dependency-free, and free of prompt/debug internals.

Commands run:
- `cd apps/web && npm run lint` - passed.
- `cd apps/web && npm run build` - passed after Turbopack port-binding approval.
- `cd apps/api && alembic upgrade head` - passed.
- `cd apps/api && pytest` - passed; 29 tests.
- `cd apps/api && ruff check .` - passed.
- `cd apps/api && ruff format .` - passed; 48 files unchanged.
- `curl -sS http://127.0.0.1:8000/health && curl -sS http://127.0.0.1:8000/health/db && curl -sS http://127.0.0.1:8000/health/llm` - passed with API ok, DB ok, LLM mock ok.
- `curl -I http://127.0.0.1:3000` - passed with HTTP 200.

Known limitations:
- The main controller still owns auth, account, character, conversation, search, debug, relationship, and data export orchestration.
- Browser screenshot/visual regression tooling is still not installed.

## World-class continuation - chat/runtime controller split

Completed in this checkpoint:
- Extracted chat message state, SSE stream parsing, edit-message flow, reroll flow, and chat reset behavior into `components/eidolon/use-chat-controller.ts`.
- Extracted runtime API/DB/LLM health polling into `components/eidolon/use-runtime-status.ts`.
- Extracted the runtime status header UI into `components/eidolon/runtime-status-strip.tsx`.
- Extracted pure controller helpers into `components/eidolon/controller-utils.ts`.
- Reduced `eidolon-app.tsx` to 165 lines and the main controller hook to 690 lines, while preserving register/login/chat/SSE/persistence behavior.
- Restored generated `next-env.d.ts` churn after production builds switched it between dev/build route type references.

Commands run:
- `cd apps/api && pytest` - passed; 29 tests.
- `cd apps/api && ruff check .` - passed.
- `cd apps/web && npm run lint` - passed.
- `cd apps/web && npm run build` - passed after Turbopack port-binding approval.
- `curl -sS http://127.0.0.1:8000/health && curl -sS http://127.0.0.1:8000/health/db && curl -sS http://127.0.0.1:8000/health/llm` - passed with API ok, DB ok, LLM mock ok after restarting the dev server.
- `curl -I http://127.0.0.1:3000` - passed with HTTP 200 after restarting the web dev server.

Known limitations:
- The main controller still owns character, conversation, memory, journal, data, and account state. Further domain hook extraction is still warranted.
- Runtime smoke is HTTP-level; browser screenshot tooling is still not installed.

## World-class continuation - chat presence surface

Completed in this checkpoint:
- Upgraded the central chat surface with a compact context ribbon showing relationship mood/conflict, warmth/trust, memory/journal/message continuity, and effective content mode.
- Added clearer companion delivery metadata in message bubbles, including content mode, read state, typing latency, proactive markers, and away state when present.
- Improved chat header responsiveness, composer mobile layout, and streaming presentation while keeping the interface text-first and dependency-free.
- Kept debug and prompt metadata out of the chat surface; the new context ribbon uses only user-facing state.

Commands run:
- `cd apps/web && npm run lint` - passed.
- `cd apps/web && npm run build` - passed after Turbopack port-binding approval.
- `curl -sS http://127.0.0.1:8000/health && curl -sS http://127.0.0.1:8000/health/db && curl -sS http://127.0.0.1:8000/health/llm` - passed with API ok, DB ok, LLM mock ok.
- `curl -I http://127.0.0.1:3000` - passed with HTTP 200.

Known limitations:
- Visual validation remains HTTP/build-level rather than browser screenshot-based.
- The context ribbon is still compact; future passes can add richer timeline-aware affordances once more controller domains are split.

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

## World-class overhaul goal - product architecture pass

Started on 2026-06-17 after the broader end-product vision replaced the narrower Level 2 target.

Completed in this checkpoint:
- Treated the validated Level 2 app as the baseline rather than the finish line.
- Split the previous 1,804-line `eidolon-app.tsx` into focused frontend modules:
  - `components/eidolon/types.ts`
  - `components/eidolon/ui.tsx`
  - `components/eidolon/auth-screen.tsx`
  - `components/eidolon/workspace-rail.tsx`
  - `components/eidolon/chat-surface.tsx`
  - `components/eidolon/inspector.tsx`
- Reworked the app shell into a more deliberate workspace: character rail, thread rail, search, central chat surface, and inspector.
- Added frontend support for creating/selecting characters, creating/selecting threads per character, editing thread titles, and keeping inspector state in sync.
- Added backend `PATCH /conversations/{conversation_id}` and `ConversationUpdate` schema for conversation title edits.
- Added a backend test for conversation title updates.
- Improved global UI polish: font rendering, dark form controls, selection color, focus consistency, scrollbar color, and reduced-motion behavior.
- Fixed stale TypeScript config by removing invalid `ignoreDeprecations: "6.0"` from `apps/web/tsconfig.json`.

Commands run:
- `cd apps/web && npm run lint && npm run build` - initially failed on invalid TypeScript `ignoreDeprecations` value; fixed config.
- `cd apps/web && npm run lint && npm run build` - passed after config fix.
- `cd apps/api && pytest -q && ruff check .` - passed; 29 tests.
- `cd apps/web && npm run lint && npm run build` - passed after thread rename UI wiring.
- `cd apps/api && python -m uvicorn app.main:app --host 0.0.0.0 --port 8000` - restarted from current code for smoke testing.
- `curl -sS http://localhost:8000/health` - passed.
- `cd apps/web && npm run dev -- --port 3000` - restarted from current code for smoke testing.
- `curl -I -sS http://localhost:3000` - passed with HTTP 200.
- Authenticated API smoke test for conversation rename - passed.

Known limitations:
- The inspector module is still large and should be split further in a future product-quality pass.
- Visual verification is currently through build/runtime HTTP checks; no browser screenshot tooling is installed in this repo yet.

## Level 2 continuation - controller extraction and runtime status

Completed in this checkpoint:
- Extracted the frontend orchestration state/actions from `components/eidolon-app.tsx` into `components/eidolon/use-eidolon-controller.ts`.
- Kept `eidolon-app.tsx` as a small renderer that composes auth, workspace rail, chat surface, and inspector.
- Added typed runtime health state for API, DB, and LLM provider.
- Added a compact private runtime status strip to the authenticated header using only public health endpoints.
- Preserved debug prompt metadata inside the debug panel only; chat messages do not render debug context.
- Fixed the invalid `ignoreDeprecations` value in the web TypeScript config during the frontend build cleanup.
- Kept dependencies unchanged and within the zero-cost/text-only constraints.

Commands run:
- `docker compose up -d postgres` - passed after Docker daemon approval; `eidolon-postgres` was already running and healthy.
- `cd apps/api && pip install -e ".[dev]"` - passed after network approval for build dependencies.
- `cd apps/api && alembic upgrade head && pytest && ruff check . && ruff format .` - passed after localhost/Postgres approval; 29 backend tests passed, Ruff passed, 48 files unchanged by format.
- `cd apps/web && npm install` - passed; dependencies already up to date.
- `cd apps/web && npm run lint` - passed.
- `cd apps/web && npm run build` - passed after Turbopack port-binding approval.
- Forbidden-dependency scan across manifests, Docker Compose, GitHub workflows, and docs - no matches.
- `cd apps/api && python -m uvicorn app.main:app --host 0.0.0.0 --port 8000` - started current backend for smoke testing.
- `curl -sS http://127.0.0.1:8000/health && curl -sS http://127.0.0.1:8000/health/db && curl -sS http://127.0.0.1:8000/health/llm` - passed with API ok, DB ok, LLM mock ok.
- `cd apps/web && npm run dev` - started current frontend on port 3000.
- `curl -I http://127.0.0.1:3000` - passed with HTTP 200.

Known limitations:
- The controller hook is still large and should be split into domain hooks in a future pass.
- Browser visual regression tooling is still not installed; UI validation is lint/build plus HTTP smoke.
- The broader Level 2 goal remains active because the end-to-end product objective is ambitious and should not be marked complete from one checkpoint alone.

## World-class overhaul goal - inspector split and chat ergonomics

Completed in this checkpoint:
- Split the remaining large `components/eidolon/inspector.tsx` into focused panel modules under `components/eidolon/panels/`.
- Reduced `inspector.tsx` from 754 lines to a 227-line panel coordinator.
- Added standalone panel modules for overview, character, memory, journal, relationship, adult settings, account settings, debug, and data controls.
- Added chat auto-scroll to the newest message/streaming output.
- Added Enter-to-send and Shift+Enter-for-newline behavior in the composer without adding visible shortcut clutter.
- Kept frontend dependencies unchanged.

Commands run:
- `cd apps/web && npm run lint` - passed after panel split.
- `cd apps/web && npm run lint && npm run build` - passed after chat ergonomics update.
- `cd apps/api && pytest -q && ruff check .` - passed; 29 tests.
- `git diff --check` - passed.
- `cd apps/api && python -m uvicorn app.main:app --host 0.0.0.0 --port 8000` - started current backend for smoke testing.
- `cd apps/web && npm run dev -- --port 3000` - started current frontend for smoke testing.
- `curl -sS http://localhost:8000/health` - passed.
- `curl -I -sS http://localhost:3000` - passed with HTTP 200.
- Authenticated runtime smoke for register, character creation, conversation creation/rename, SSE chat, memory list, and debug prompt preview - passed.

Known limitations:
- Browser screenshot/visual regression tooling is still not installed; runtime validation is HTTP/API-level plus build/type/lint checks.
- The central app controller remains around 950 lines and could be split into hooks/state modules in a deeper architecture pass.

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
