# Codex Goal Prompt

Copy this into Codex as the initial `/goal` prompt.

```text
/goal Build the Eidolon MVP in this repository according to AGENTS.md and the docs in /docs. Work independently in ordered checkpoints, validate each checkpoint, and stop when the local MVP is working end-to-end or when blocked by a decision that cannot be safely made.

Before writing code:
- Read AGENTS.md.
- Read README.md.
- Read docs/00_GOAL_MODE_OPERATING_BRIEF.md.
- Read docs/01_PROJECT_VISION.md.
- Read docs/02_PRODUCT_REQUIREMENTS.md.
- Read docs/03_ARCHITECTURE.md.
- Read docs/04_TECH_STACK.md.
- Read docs/05_DATA_MODEL.md.
- Read docs/06_API_CONTRACT.md.
- Read docs/07_PROMPT_ASSEMBLY.md.
- Read docs/08_MEMORY_SYSTEM.md.
- Read docs/09_RELATIONSHIP_ENGINE.md.
- Read docs/10_BACKGROUND_JOBS.md.
- Read docs/11_SAFETY_AND_BOUNDARIES.md.
- Read docs/12_FRONTEND_UX.md.
- Read docs/13_DEPLOYMENT_TARGET.md.
- Read docs/14_TESTING_AND_ACCEPTANCE.md.
- Read docs/15_ROADMAP.md.
- Read docs/16_RISK_REGISTER.md.

Goal:
Create a working private, text-only AI companion MVP using the required stack:
- Next.js App Router + TypeScript + Tailwind frontend
- FastAPI + Python 3.12 backend
- PostgreSQL 16 + pgvector + pg_trgm
- SQLAlchemy async + Alembic
- mock LLM provider for development/tests
- Ollama provider adapter for production
- APScheduler with PostgreSQL-backed scheduled_jobs
- local auth
- no paid runtime APIs
- no multimedia features

Required checkpoints, in order:
1. Validate repo scaffolding and create docs/GOAL_PROGRESS.md.
2. Implement FastAPI backend health endpoint and tests.
3. Implement PostgreSQL connection, SQLAlchemy async models, and Alembic migrations for users, characters, conversations, and messages.
4. Implement mock LLM chat endpoint with message persistence.
5. Implement minimal Next.js chat frontend.
6. Implement SSE streaming and frontend streaming display.
7. Implement Ollama provider adapter while keeping mock provider default and tests independent of Ollama.
8. Implement persona prompt assembly using character profile and safety boundaries.
9. Implement memory_items table, memory service, retrieval, and prompt injection.
10. Implement relationship_states table, deterministic update rules, and prompt injection.
11. Implement scheduled_jobs table and background job foundation with scheduler disabled in tests.
12. Implement proactive queued message v1 with duplicate prevention.
13. Implement local auth and protect user data endpoints.
14. Implement adult mode structural gates without explicit adult sample content.
15. Implement private debug/admin panel for character, memory, relationship, jobs, and recent messages.
16. Implement export/backup basics excluding secrets and password hashes.
17. Add deployment templates for Oracle/Caddy/systemd/GitHub Actions without secrets.
18. Add production hardening: CORS config, safe error handling, health checks, lightweight CI.
19. Polish MVP UI without heavy dependencies.

Constraints:
- Do not add Redis, Celery, Supabase, Firebase, LangChain, Pinecone, Chroma, Clerk, Auth0, NextAuth, Stripe, WebRTC, Socket.io, Three.js, Framer Motion, React Native, Expo, Docker production deployment, or Kubernetes.
- Do not add voice, audio, avatar, video, image generation, AR, or heavy animation features.
- Do not add paid APIs or cloud services.
- Do not require Ollama for tests.
- Do not commit secrets or .env.
- Do not store explicit adult sample content in tests, fixtures, docs, or seed data.
- Keep adult mode structural and gated: user age gate, explicit adult character age, adult_mode_allowed, and hard boundaries.
- Keep frontend lightweight.
- Keep backend stateful and model stateless.
- Use PostgreSQL as the source of truth.

Validation loop:
After each major checkpoint:
- update docs/GOAL_PROGRESS.md
- run relevant backend tests/lint
- run relevant frontend lint/build
- run migrations if DB changed
- record commands run and results
- fix failures before moving to the next checkpoint unless the failure is documented and safely deferred

Backend validation:
cd apps/api && pip install -e ".[dev]" && alembic upgrade head && pytest && ruff check . && ruff format .

Frontend validation:
cd apps/web && npm install && npm run lint && npm run build

Local service validation:
docker compose up -d postgres

Done when:
- Docker Compose PostgreSQL starts.
- Backend starts and /health works.
- Frontend starts.
- User can register/login or a documented dev mode exists if auth is deferred temporarily.
- User can create/open a conversation.
- User can send a message.
- Assistant response appears and streams if streaming is implemented.
- Messages persist after refresh.
- Character persona is included in prompt assembly.
- Memories can be stored/retrieved and appear in prompt assembly.
- Relationship state updates after messages and appears in debug/prompt context.
- Proactive message system can create one queued assistant message without spam.
- Debug panel shows current character, memories, relationship state, scheduled jobs, and recent messages for the current user only.
- Export excludes password hashes, token hashes, secrets, and other users' data.
- Backend tests pass.
- Backend ruff check passes.
- Frontend lint/build pass.
- No forbidden dependencies are added.
- docs/GOAL_PROGRESS.md clearly reports what was completed, what commands ran, and remaining known limitations.

If blocked:
Pause and explain the blocker, exact file/state, and smallest decision needed. Do not invent credentials, cloud resources, secrets, or paid services.
```
