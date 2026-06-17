# Eidolon Agent Instructions

These instructions are mandatory for Codex and any coding agent working in this repository.

## Project summary

Eidolon is a private, text-only, immersive AI companion application. It is not a multimedia avatar app. Its depth comes from backend state, memory, persona continuity, relationship variables, prompt assembly, and scheduled text behaviours.

The target for this repository is an ambitious but buildable MVP that runs on zero recurring-cost infrastructure for personal use and keeps a clean migration path to future scale.

## Hard constraints

- Development machine: low-spec Chromebook, using GitHub Codespaces.
- Production target for personal MVP: Oracle Cloud Always Free ARM VM.
- Production budget for personal MVP: £0 recurring cost.
- Paid APIs are forbidden for runtime features.
- The only paid tooling allowed is the user's coding assistant subscription.
- No local model execution on the Chromebook.
- No heavy client-side rendering.
- No voice, audio, avatar, video, AR, image generation, or Live2D features.
- No commercial API dependency for core inference.
- No Supabase/Firebase/Pinecone/Chroma/Redis/Celery/Kubernetes/LangChain for MVP.
- Do not add dependencies just because they are popular. This is software engineering, not dependency taxidermy.

## Required stack

Frontend:
- Next.js App Router
- TypeScript
- Tailwind CSS
- Lightweight text-first PWA-style interface
- Server-Sent Events for streaming before WebSockets

Backend:
- FastAPI
- Python 3.12+
- Pydantic v2
- pydantic-settings
- SQLAlchemy 2.x async
- Alembic
- APScheduler only with PostgreSQL-backed job state

Database:
- PostgreSQL 16
- pgvector
- pg_trgm where useful
- PostgreSQL is the source of truth for users, characters, messages, memories, relationship state, and jobs.

LLM:
- Development starts with a mock provider.
- Production uses Ollama on Oracle ARM.
- Target model class: Llama 3.1 8B / similar 8B quantized model.
- Use a smaller model or mock for background jobs if useful.
- No fine-tuning in MVP.

Infrastructure:
- GitHub Codespaces for development
- Docker Compose for local dev services only
- Oracle Cloud Always Free ARM for production backend/database/Ollama
- Caddy reverse proxy
- systemd process management
- GitHub Actions SSH deployment later

## Product boundaries

The app may support legal adult fictional text roleplay between adults, but it must enforce hard structural boundaries:

- No minors or ambiguous-age characters in sexual contexts.
- No sexual coercion, exploitation, or abuse.
- No illegal sexual content.
- No real-world instructions for harm, stalking, exploitation, or abuse.
- Adult mode must require user age-gate confirmation and explicit adult character age.
- Never interpret "uncensored" as "no rules."

Do not put explicit sexual sample content in code, tests, fixtures, seed data, or docs.

## Core architecture principle

The backend owns state. The LLM generates text.

The backend owns:
- user account
- character profile
- conversation history
- memory storage and retrieval
- relationship state
- mood state
- prompt assembly
- safety boundaries
- scheduled jobs
- proactive message logic
- debug/admin visibility

The model must not be expected to magically remember durable facts. Durable facts belong in PostgreSQL.

## Build philosophy

Build in thin vertical slices.

Preferred order:
1. FastAPI health endpoint
2. PostgreSQL + models + migrations
3. Mock chat endpoint
4. Next.js chat shell
5. SSE streaming
6. Ollama provider
7. Persona prompt assembly
8. Memory v1
9. Relationship state v1
10. Background jobs v1
11. Proactive messages v1
12. Auth v1
13. Adult mode gates
14. Debug/admin panel
15. Deployment templates
16. Production hardening
17. Backup/export
18. MVP polish

If using `/goal`, implement as much of this order as possible, but stop before unsafe, untested, or overcomplicated changes.

## Coding rules

- Keep files small and explicit.
- Prefer boring code over clever abstractions.
- Use type hints in Python.
- Use Pydantic schemas for API boundaries.
- Use SQLAlchemy models and Alembic migrations for DB changes.
- Add tests for backend services and endpoints.
- Use deterministic tests.
- Do not require Ollama to be installed for tests.
- Mock external/local LLM HTTP calls in tests.
- Avoid global mutable state except explicit app lifecycle objects.
- Keep generated text fixtures SFW.
- Make failures readable.
- Never commit `.env`, secrets, keys, tokens, private IPs, or credentials.

## Done means

A feature is not done until:
- tests pass
- linters pass
- migrations run if database changed
- existing flows still work
- no forbidden dependencies were added
- the implementation matches docs
- Codex has updated a short progress log if the task is long-running

## Validation commands

Backend:
```bash
cd apps/api
pip install -e ".[dev]"
alembic upgrade head || true
pytest
ruff check .
ruff format .
```

Frontend:
```bash
cd apps/web
npm install
npm run lint
npm run build
```

Local services:
```bash
docker compose up -d postgres
```

## If blocked

If Codex is blocked, it should:
1. stop changing files,
2. explain exactly what is blocked,
3. state the smallest user decision needed,
4. preserve all completed working changes.

Do not hallucinate infrastructure, credentials, cloud resources, or API keys.
