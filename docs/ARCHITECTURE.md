# Architecture

## Production topology

```text
Browser
  |
  | static HTML, CSS, and JavaScript
  v
Cloudflare Pages (Next.js static export)
  |
  | authenticated JSON and fetch-based SSE over HTTPS
  v
Google Cloud Run (FastAPI container)
  |                         |
  | async PostgreSQL        | HTTPS chat-completions
  v                         v
Supabase Session pooler     Groq
  |
  v
PostgreSQL 16 + pgvector + pg_trgm
```

Cloudflare does not proxy chat. The browser calls the Cloud Run API directly.
The two origins therefore require exact credentialed CORS configuration and
cross-site refresh-cookie settings unless custom same-site subdomains are used.

## Stack

| Layer | Implementation |
| --- | --- |
| Web | Next.js App Router, React, TypeScript, Tailwind CSS, static export |
| API | FastAPI, Python 3.12+, Pydantic v2, Uvicorn |
| Persistence | SQLAlchemy 2 async, asyncpg, Alembic |
| Database | PostgreSQL 16, pgvector, pg_trgm |
| Streaming | fetch-based Server-Sent Events |
| Providers | Groq production, deterministic mock tests/dev, optional Ollama |
| Jobs | APScheduler wake-up loop with PostgreSQL-owned rows and locks |
| Local services | Docker Compose PostgreSQL only |
| Production | Cloudflare Pages, Cloud Run, Supabase, Google Secret Manager |

## Primary rule

The backend owns state. The model generates prose.

Provider conversation storage is not durable product memory. PostgreSQL owns
accounts, sessions, companions, conversations, messages, memories, episodes,
continuity threads, relationships, diagnostic events, and scheduled work.

## Frontend boundary

The frontend is a lightweight authenticated client. It owns:

- responsive navigation and presentation
- unsaved form drafts
- current-tab onboarding draft restoration and non-sensitive numeric scroll
  positions
- the in-memory access token
- streamed partial text while a response is in progress
- request cancellation and stale-result guards
- runtime validation before API data enters visible React state
- safe, code-native rendering of the supported rich-text subset; model prose is
  never injected as HTML

It does not own:

- safety or adult eligibility
- durable memory selection
- living-thread extraction, retrieval, and lifecycle
- relationship calculations
- prompts or provider calls
- long-lived session credentials
- canonical conversation or read state

The production build is static. It has no service worker and does not cache
authenticated application data for offline use. Session storage is limited to
an unfinished authored companion draft and numeric conversation scroll offsets;
the app writes only a non-sensitive onboarding-completion marker to local
storage, while startup compatibility code removes legacy auth keys from earlier
deployments. Access tokens, transcripts, memories, relationship state, and
diagnostic payloads are not newly persisted by the client. The normal consumer
shell does not fetch diagnostic payloads; the explicit guarded “invite a
check-in” action retains its existing owner-scoped proactive POST route.

## Backend boundary

FastAPI owns authentication, origin checks, ownership checks, validation,
database transactions, provider routing, prompt construction, response quality
checks, memory, living-thread, and relationship updates, jobs, export, and safe
diagnostics.

All user-data queries must prove ownership directly or through an owned
companion/conversation. A guessed UUID must not reveal whether another user's
row exists.

## Database boundary

PostgreSQL is authoritative. Flexible JSONB fields hold bounded authored or
derived metadata, while identity, ownership, lifecycle, and frequently queried
state remain relational columns.

Alembic is the only schema evolution path. Cloud Run executes
`alembic upgrade head` before starting Uvicorn. Migration processes share a
PostgreSQL advisory lock so concurrent revision starts do not race.

See [DATA_MODEL.md](DATA_MODEL.md) for the logical model.

## Authentication flow

1. Registration or login validates the browser origin and applies
   PostgreSQL-backed throttles.
2. The API returns a short-lived HS256 access token in JSON.
3. The API sets an opaque refresh token in the host-only `eidolon_refresh`
   HttpOnly cookie scoped to `/auth`.
4. The frontend keeps the access token only in memory and sends API requests
   with credentials included.
5. Refresh rotates the stored token and cookie; logout revokes it.

PostgreSQL stores only refresh-token hashes. Access tokens require issuer,
audience, type, subject, token ID, issued-at, not-before, and expiry claims.

With the default `pages.dev` and `run.app` hosts, production uses
`SameSite=None; Secure`. Browsers that prohibit third-party cookies may still
block refresh; same-site custom subdomains are the durable solution.

## Chat flow

1. Authenticate the request and load the owned conversation and companion.
2. Validate content mode, privacy mode, message bounds, and hard safety rules.
3. Persist the accepted user message and its privacy provenance.
4. Infer bounded intent/tone and retrieve eligible relationship, memory,
   episode, living-thread, scenario, and recent-message context.
5. Build a private response plan and compile ordered prompt modules.
6. Call the selected provider.
7. For SSE, emit `message_start`, screened `token` events, then
   `message_done`; a terminal `error` event closes failed streams.
8. Validate and persist the completed assistant message exactly once.
9. Apply the immediate deterministic relationship/emotional effect.
10. Create a durable post-chat job and expose a pending continuity receipt on
    the completed assistant message.
11. For an eligible turn, request a bounded structured cognition report, reject
    claims without exact source evidence, and let backend rules commit scoped
    memory, a source-linked moment, and bounded relationship evidence.
12. Finish living-thread and proactive work, then settle the receipt with only
    changes that actually committed.

A failed or cancelled generation keeps the accepted user message retryable and
stores no partial assistant message. Reroll and latest-turn edit use the same
orchestration and safety path.

## Prompt and cognition boundary

Prompt assembly compiles typed state into bounded natural-language modules. It
does not dump raw JSON, relationship meters, diagnostics, or hidden reasoning.
The current user message remains last.

A private context manifest may record selected IDs, types, categorical posture,
prompt version/size, and generation metadata on the source turn. It never stores
raw prompt text or copied state prose and is exposed only through a validated,
owner-scoped Debug response.

Structured cognition is a proposal boundary, not model-owned state. The provider
must return the strict schema with exact evidence quotes. Backend checks verify
source substrings, named/numeric anchors, lexical support, and polarity before
claim identity, confidence, correction, conflict, scope, or lifecycle can
change. Invalid/unavailable structured output degrades to the existing
deterministic extraction path without failing the already-persisted reply.

Details are in [COMPANION_SYSTEMS.md](COMPANION_SYSTEMS.md).

## Privacy flow

Privacy is captured when a turn is accepted. Conversation-private and one-turn
private messages remain in owned history but are excluded from future normal
prompt history, memory extraction, recall updates, episodic journals,
living-thread creation/reference updates, relationship changes, and proactive
context.

Eligible adult continuity, when explicitly enabled, uses separate semantic and
episodic scopes. Normal prompts, archives, relationship progression, living
threads, and proactive work cannot read that scope.

Controlled privacy/scenario system events can appear in the transcript. Prompt
assembly converts recognized events into fixed summaries and never treats stored
system-event prose as instructions.

## Background work

APScheduler is a wake-up mechanism. `scheduled_jobs` rows, claims, retry counts,
and results live in PostgreSQL. Workers use row locking and a transaction-scoped
advisory lock to avoid overlapping batches.

Cloud Run can scale to zero and may suspend CPU outside requests. Proactive jobs
therefore catch up when an instance becomes active; the current deployment does
not guarantee precise wall-clock delivery.

## Provider abstraction

The typed provider interface supports completed generations, streamed events,
and bounded strict-schema generations without a vendor SDK leaking into chat
services.

- `mock`: deterministic, external-call-free development and test provider
- `groq`: active production provider using backend-only OpenAI-compatible HTTP
- `ollama`: optional HTTP adapter for local/self-hosted experimentation

Automated tests mock live-provider HTTP. A real Groq smoke test is opt-in.

## Deployment boundary

The frontend and backend have independent build roots and external hosting
triggers:

- Cloudflare Pages: `apps/web` -> `npm run build` -> `out`
- Cloud Run: `apps/api` -> `Dockerfile` -> port `8080`

GitHub Actions runs repository validation, but the hosting integrations decide
when deployment happens. A Cloudflare branch preview is not a separate backend
or database and must not be treated as staging.

See [OPERATIONS.md](OPERATIONS.md) for release and deployment controls.

## Portability

The provider interface and standard PostgreSQL schema are intentional migration
seams. Portability does not justify building duplicate infrastructure today.
Any future host/provider change must preserve API, ownership, privacy, migration,
and backup contracts before production is moved.
