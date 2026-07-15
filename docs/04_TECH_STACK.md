# Tech Stack

## Development environment

- GitHub Codespaces
- VS Code browser/editor
- Docker Compose for PostgreSQL only
- No local LLM in Codespaces required

## Frontend

- Next.js App Router
- TypeScript
- Tailwind CSS
- native fetch/EventSource or fetch streaming
- native Next metadata routes for manifest/robots and safe-area viewport support

The MVP uses standalone web-app metadata but no service worker or offline data
cache. This keeps the client light and leaves private durable state on the server.

Avoid:
- Framer Motion
- Three.js
- avatar frameworks
- audio libraries
- large state-management frameworks unless necessary

## Backend

- Python 3.12+
- FastAPI
- Uvicorn
- Pydantic v2
- pydantic-settings
- SQLAlchemy 2.x async
- asyncpg
- Alembic
- pytest
- httpx for tests/HTTP client
- ruff

## Database

- PostgreSQL 16
- pgvector
- pg_trgm

## LLM runtime

Development:
- GroqCloud for real-model testing
- explicit deterministic mock provider for automated tests and UI scaffolding

Production:
- Groq through the replaceable provider interface
- production startup requires the Groq provider and a server-side key
- Ollama remains a development/self-hosting option, not a Cloud Run fallback

No provider key or inference call may enter the browser. The default Groq path
uses the user's configured account; core state and provider history remain in
Eidolon's PostgreSQL, and Ollama remains selectable without changing chat logic.

## Auth

- local auth
- password hashing with Argon2id preferred
- JWT access tokens
- PostgreSQL-backed refresh token rotation and revocation

No Clerk/Auth0/Firebase/NextAuth for MVP.

## Jobs

- APScheduler
- PostgreSQL scheduled_jobs table

No Redis/Celery for MVP.

## Deployment target

- Cloudflare Pages static Next.js export
- Google Cloud Run FastAPI container
- Supabase PostgreSQL through its Session pooler
- Groq inference from the backend only
- Eidolon's existing authentication and PostgreSQL refresh sessions

## Monitoring

MVP:
- health endpoints
- logs
- UptimeRobot free ping later

No Prometheus/Grafana initially.
