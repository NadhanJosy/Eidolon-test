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
- mock provider

Production:
- Ollama
- target 8B quantized model

No paid inference APIs in MVP.

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

- Oracle Cloud Always Free ARM VM
- Ubuntu
- Caddy
- systemd
- PostgreSQL
- Ollama
- FastAPI

Frontend may be hosted on:
- Vercel Hobby
- Cloudflare Pages
- or served separately later

## Monitoring

MVP:
- health endpoints
- logs
- UptimeRobot free ping later

No Prometheus/Grafana initially.
