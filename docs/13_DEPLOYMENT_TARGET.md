# Deployment Target

## Personal MVP target

Production target:

- Oracle Cloud Always Free ARM VM
- Ubuntu
- PostgreSQL 16 + pgvector
- FastAPI via systemd
- Caddy reverse proxy
- Ollama local runtime
- optional static frontend on Vercel Hobby or Cloudflare Pages

## Development target

- GitHub Codespaces
- Docker Compose PostgreSQL
- mock LLM provider

## Production services

Expected services:

- postgresql
- ollama
- eidolon-api.service
- caddy

## Ports

Local dev:
- frontend 3000
- backend 8000
- PostgreSQL 5432
- Ollama 11434

Production:
- Caddy exposes 80/443
- backend bound to localhost or internal port
- PostgreSQL not public
- Ollama not public

## Environment variables

Production must provide:

- DATABASE_URL
- JWT_SECRET
- WEB_ORIGIN
- LLM_PROVIDER=ollama
- OLLAMA_BASE_URL
- OLLAMA_MODEL

Do not commit production secrets.

## Deployment philosophy

Do not use Kubernetes.
Do not use Docker production unless explicitly needed.
Do not rely on paid managed services for MVP.

Use boring systemd services first.

## Health checks

Endpoints:

- /health
- /health/db
- /health/llm

Health endpoints must not expose secrets.

## Backups

Add pg_dump script before trusting the app with important data.

Generated backup files go into backups/ and must be gitignored.
