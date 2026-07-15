# Deployment Target

## Production topology

Eidolon's active production target is:

```text
Cloudflare Pages (static Next.js)
  -> HTTPS fetch + SSE
Google Cloud Run (FastAPI container)
  -> async PostgreSQL
Supabase Session pooler :5432 (PostgreSQL + vector + pg_trgm)

Google Cloud Run
  -> HTTPS
Groq chat-completions API
```

Eidolon's own JWT access tokens, PostgreSQL refresh sessions, account model, and
origin validation remain authoritative. Supabase Auth is not used.

## Build roots

| Service | Root | Build | Result |
| --- | --- | --- | --- |
| Cloudflare Pages | `apps/web` | `npm run build` | `out` |
| Cloud Run | `apps/api` | `Dockerfile` | Linux container on port `8080` |

Cloud Run injects `PORT`. The image binds Uvicorn to `0.0.0.0:${PORT}`, runs
`alembic upgrade head` before application startup, and serializes concurrent
migration attempts with a PostgreSQL advisory lock.

## Required backend configuration

Production requires:

- `APP_ENV=production`
- `DATABASE_URL` set to the Supabase Session pooler on port `5432`
- `GROQ_API_KEY`
- `GROQ_MODEL=openai/gpt-oss-120b` (or another currently enabled production model)
- `JWT_SECRET`
- `LLM_PROVIDER=groq`
- `WEB_ORIGIN` set to the exact HTTPS frontend origin
- `CORS_ORIGINS` for any additional exact HTTPS origins
- `REFRESH_COOKIE_SECURE=true`
- `REFRESH_COOKIE_SAMESITE=none` when using the default cross-site Pages and
  Cloud Run domains

Secrets must be provided through Cloud Run secret bindings. Production rejects
the local database default, mock/Ollama providers, weak JWT values, insecure
cookies, wildcard origins, and non-HTTPS browser origins.

The recommended SQLAlchemy pool is five persistent connections with no overflow.
Cloud Run maximum instances must be sized so all application pools fit within the
Supabase connection allowance.

## Frontend configuration

Cloudflare Pages requires this public build-time value:

```dotenv
NEXT_PUBLIC_API_BASE_URL=https://<cloud-run-service-url>
```

No backend secret may use a `NEXT_PUBLIC_*` name. Static security headers are
defined in `apps/web/public/_headers`.

## Health and streaming

- `/health` is process liveness and does not touch dependencies.
- `/ready` executes a bounded `SELECT 1` database check and exposes no exception,
  hostname, connection string, or credential.
- `/health/db` and `/health/llm` remain explicit diagnostics.
- `/chat/stream` uses `text/event-stream`, `Cache-Control: no-cache,
  no-transform`, and `X-Accel-Buffering: no`.

Cloud Run's request timeout must exceed `LLM_TIMEOUT_SECONDS`.

## Jobs

Job rows, claims, retries, and locks remain in PostgreSQL. Request-based Cloud Run
CPU and scale-to-zero do not guarantee exact wall-clock APScheduler ticks; jobs
catch up while an instance is active. Always-allocated CPU/minimum instances can
improve timing at additional cost.

## Backups and portability

Supabase backups and a tested logical export/restore procedure must be configured
before important data is stored. Keep provider and database access behind the
existing interfaces so the application remains portable.

The complete deployment commands and variable table are maintained in the root
`README.md`.
