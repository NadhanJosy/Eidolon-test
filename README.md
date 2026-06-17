# Eidolon

Eidolon is a private, text-only AI companion app focused on memory, persona continuity, relationship state, and proactive text behaviour.

It is designed for a zero-recurring-cost personal MVP and a clean migration path toward future scale.

## What makes it different

Eidolon should feel immersive through continuity, not expensive multimedia tricks.

Core product pillars:

1. Persistent memory
2. Believable character persona
3. Relationship state progression
4. Proactive text behaviour
5. Debuggable backend state
6. Low-cost self-hosted inference

## Non-goals

The MVP intentionally excludes:

- voice calls
- TTS/STT
- voice cloning
- avatars
- image generation
- video generation
- native mobile
- AR
- Live2D / 3D rendering
- paid inference APIs
- fine-tuning
- Kubernetes
- Redis/Celery
- external vector databases

## Target stack

Frontend:
- Next.js App Router
- TypeScript
- Tailwind CSS

Backend:
- FastAPI
- SQLAlchemy async
- Alembic
- Pydantic v2

Database:
- PostgreSQL 16
- pgvector
- pg_trgm

LLM:
- Mock provider for development
- Ollama for production

Infrastructure:
- GitHub Codespaces for development
- Oracle Cloud Always Free ARM for backend/database/Ollama
- Caddy + systemd
- Vercel Hobby or Cloudflare Pages for static frontend if needed

## MVP target

A single-user private app where the user can:

- create/login to an account
- chat with one or more text-only characters
- persist conversation history
- stream assistant replies
- inspect memories and relationship state
- run a local/Ollama-backed model in production
- receive queued proactive messages inside the app
- export/wipe personal data

## Development

Start services:

```bash
docker compose up -d postgres
```

Backend:

```bash
cd apps/api
pip install -e ".[dev]"
alembic upgrade head
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

Frontend:

```bash
cd apps/web
npm install
npm run dev
```

## Codespaces registration troubleshooting

If registration shows `Failed to fetch`, the browser probably cannot reach the
backend through `localhost`. Set `NEXT_PUBLIC_API_BASE_URL` for the frontend to
the forwarded port 8000 URL, either in `apps/web/.env.local` or the shell that
starts `npm run dev`. Set backend `WEB_ORIGIN` or `CORS_ORIGINS` to the
forwarded port 3000 URL. Restart both dev servers after changing env vars.

## Important design rule

The backend owns intelligence state. The LLM only writes the next message.
