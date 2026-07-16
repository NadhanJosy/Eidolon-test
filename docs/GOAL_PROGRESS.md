# Goal Progress

This is the repository's single progress log. Add one concise entry after each
completed user task. Record outcomes and validation, not turn-by-turn activity.

## 2026-07-16 — Deployment-aware documentation cleanup

Outcome:

- Replaced the obsolete Oracle/Ollama agent rules with the active Cloudflare
  Pages, Cloud Run, Supabase PostgreSQL, and Groq production topology.
- Consolidated the documentation into focused product, architecture, data, API,
  companion-system, safety, operations, roadmap, and progress documents.
- Removed stale goal prompts, numbered duplicates, the historical progress dump,
  the old request note, and the duplicate documentation archive.
- Added the feature-branch, validation, completed-task commit/push, and pull
  request workflow while keeping `main` and production protected.

Validation:

- Alembic upgrade passed.
- Backend: 224 tests passed and the opt-in live-provider test was skipped.
- Ruff lint and format checks passed.
- Frontend ESLint, TypeScript, and static production build passed.
- All retained Markdown links resolved and all 50 FastAPI routes were represented
  in the API inventory.

## 2026-07-16 — Living continuity threads

Outcome:

- Added first-class, owner-scoped plans, promises, rituals, repairs, and
  follow-ups with conservative explicit-language capture and full user lifecycle
  controls in chat and Relationship views.
- Connected open threads to prompt planning, safe context manifests, export,
  source-turn cleanup, and exact-thread proactive follow-ups with cooldown.
- Kept private/adult turns, blocked text, and credential-like content outside
  automatic capture, and made pull-request CI deterministic with explicit test
  configuration and frontend type checking.

Validation:

- Alembic upgraded through `0010_living_threads`.
- Backend: 230 tests passed and the opt-in live-provider test was skipped.
- Ruff lint and format checks passed.
- Frontend ESLint, TypeScript, and static production build passed.
