# Deployment Target

## Personal MVP target

Production target:

- Oracle Cloud Always Free ARM VM
- Ubuntu
- PostgreSQL 16 + pgvector
- FastAPI via systemd
- Caddy reverse proxy
- GroqCloud initially, with Ollama as the self-hosted zero-cost migration path
- optional static frontend on Vercel Hobby or Cloudflare Pages

## Development target

- GitHub Codespaces
- Docker Compose PostgreSQL
- GroqCloud for real-model development; explicit mock provider for tests

## Production services

Expected services:

- postgresql
- eidolon-api.service
- caddy
- ollama when using local inference

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
- LLM_PROVIDER=groq
- GROQ_API_KEY
- GROQ_MODEL

For self-hosted inference, select `LLM_PROVIDER=ollama` and provide
`OLLAMA_BASE_URL` and `OLLAMA_MODEL` instead.

Do not commit production secrets.

Generate `JWT_SECRET` with `openssl rand -hex 32`. Eidolon requires 32-4096
UTF-8 bytes and rejects placeholders, replacement markers, and low-diversity
production values. Rotating it invalidates access tokens and auth-throttle HMAC
fingerprints; PostgreSQL refresh sessions remain independently usable.

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
