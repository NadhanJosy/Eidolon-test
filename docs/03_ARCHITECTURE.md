# Architecture

## High-level diagram

```text
Browser / Cloudflare Pages static app
  ↓
Next.js frontend
  ↓ HTTP/SSE
FastAPI backend on Google Cloud Run
  ↓
Supabase PostgreSQL Session pooler + pgvector
  ↓
Typed LLM provider interface → Groq production, Ollama/dev mock outside production
```

## Main architectural rule

The backend owns state. The LLM produces prose.

This prevents personality drift, memory hallucination, and provider lock-in.

## Frontend responsibilities

The frontend handles:

- chat layout
- input box
- message list
- streaming display
- login/register screens
- character panel
- staged character creation with local, non-durable draft state
- memory/debug views
- settings toggles
- companion-first responsive workspace navigation
- typed standalone manifest, private indexing metadata, and mobile safe areas

Operational API/database/provider health and prompt internals belong inside the
authenticated debug view. The primary shell may show humanized companion,
relationship, privacy, and content-mode posture, but not raw backend state
labels.

Prompt assembly records a compact private manifest on the exact user turn that
triggered generation. It contains selected state identifiers/types, recent
roles/privacy posture, safety state, prompt size/version, provider, generation
kind, and a bounded response-plan summary, never raw prompt or message text.
Normal message schemas strip internal underscore-prefixed metadata. The owned
conversation Debug endpoint validates and exposes only the newest real manifest;
character Debug exposes a current retrieval summary and never synthesizes a
fake user turn.

The web shell sends no-referrer, anti-framing, MIME-sniffing, same-origin opener
and resource, and unused-device-capability headers. These headers preserve the
same-origin Next runtime and cross-origin API fetch model while preventing the
frontend document from enabling camera, microphone, geolocation, payment, USB,
or browsing-topics capabilities that Eidolon does not use.

The frontend must not handle:

- memory selection
- relationship calculations
- model calls directly
- safety gates
- heavy rendering
- local ML

The character builder may keep an unsaved profile in local React state while
its modal is open. PostgreSQL becomes authoritative only after
`POST /characters` succeeds. The backend revalidates name, text bounds, profile
JSON shape, explicit age, adult eligibility, and intensity regardless of
client checks.

Conversation-owned Shared Scene text lives in PostgreSQL `metadata_json`, not in
LLM memory or character-global profile state. The frontend may preserve one
unsaved scene draft for the active thread, but navigation versions prevent a
late save/refresh from overwriting another thread's display state. The backend
normalizes, bounds, safety-checks, and serializes updates on the owned
conversation row.

## Backend responsibilities

The backend handles:

- auth
- database access
- prompt assembly
- LLM provider routing
- message persistence
- memory storage/retrieval
- relationship state updates
- scheduled jobs
- adult mode gates
- debug endpoints
- data export/wipe

## Session security

The browser stores no long-lived bearer token in JavaScript-readable storage.
Register and login return a short-lived access token in JSON and set the
opaque refresh token as the host-only `eidolon_refresh` HttpOnly cookie scoped
to `/auth`. The frontend keeps access tokens in memory, sends API calls with
credentials included, rotates access proactively before JWT expiry, and removes
legacy localStorage auth values during one-time migration.

The JWT signing key is held as a masked secret and must be 32-4096 UTF-8 bytes
in every environment. Production also rejects the repository placeholder,
replacement markers, and obviously low-diversity values. Access tokens accept
only HS256 and require issuer `eidolon-api`, audience `eidolon-web`, type
`access`, issued-at, not-before, expiry, subject UUID, and token UUID claims,
with five seconds of clock-skew tolerance.

Signing-key rotation invalidates outstanding access tokens immediately. Opaque
refresh tokens are independently random and hashed in PostgreSQL, so a valid
refresh cookie may rotate normally and receive an access token signed by the new
key. Auth-throttle fingerprints use the same key; old anonymous fingerprints
become unreachable and are pruned by normal retention cleanup.

The auth schema canonicalizes email identity and optional display names before
database lookup or persistence. Registration enforces a bounded 12-character
minimum passphrase, while login preserves existing-password compatibility and
performs one Argon2 verification against either the stored hash or a fixed dummy
hash so an absent account does not take the previous cheap failure path.

Costly auth attempts are serialized across API processes with sorted PostgreSQL
transaction advisory locks. Login is bounded across both canonical identity and
ASGI client host; registration has a separate client scope. Active blocks are
checked before Argon2. Registration accounting commits before hashing/user
creation so a duplicate conflict or later transaction rollback cannot erase
consumed work, while schema-validation and rejected-Origin requests never reach
the counter. The configured threshold request may complete, then subsequent
requests are blocked until expiry.

PostgreSQL stores only HMAC-SHA256 fingerprints keyed by the JWT secret,
counters, and window times; raw attempted emails and addresses never enter the
auth throttle table, exports, or debug output. Successful login clears only its
matching login records, expired windows reset on the next attempt, and committed
auth traffic prunes stale records. Application code does not trust forwarding
headers directly; the deployment proxy/runtime remains responsible for
providing the correct client address.

The API allows credentialed CORS only from configured origins. Browser requests
with an `Origin` header must match `WEB_ORIGIN` or `CORS_ORIGINS` before they
can register, log in, refresh, or log out with cookie/legacy refresh material.
Development can use an insecure Lax cookie on `localhost`; HTTPS Codespaces and
production should set `REFRESH_COOKIE_SECURE=true`, and truly cross-site
frontend/backend deployments must use `REFRESH_COOKIE_SAMESITE=none` with
Secure enabled.

The PWA-style shell does not register a service worker. Durable authenticated
state belongs to PostgreSQL, and silently caching a private conversation shell or
API response would add stale-session and data-retention risk without making chat
usable while the backend is offline.

## Database responsibilities

PostgreSQL stores all durable state.

Core tables:
- users
- characters
- conversations
- messages
- memory_items
- relationship_states
- scheduled_jobs
- refresh_tokens

PostgreSQL extensions:
- pgvector for dependency-free local feature embeddings, with a replaceable
  `vector(384)` storage contract for a future model-backed encoder
- pg_trgm for fuzzy search

## LLM provider abstraction

Provider interface supports typed completed generations and streamed events.
Events carry text plus privacy-safe model, finish-reason, and token-usage data;
chat logic does not depend on a provider SDK.

Providers:

1. GroqCloud provider
   - default real conversation path
   - OpenAI-compatible chat completions over backend-only HTTP
   - SSE parsing, timeout, cancellation, and bounded pre-token retries
   - provider/model fallback only before live text is emitted

2. Mock provider
   - deterministic
   - used by tests
   - no external dependency
   - explicitly limited to development/testing

3. Ollama provider
   - HTTP client to local Ollama server
   - configurable base URL and model
   - graceful failure when unavailable

Tests mock provider HTTP and require neither GroqCloud nor Ollama. One live Groq
smoke test is opt-in and excluded from CI.

## Chat flow

1. User submits message.
2. Backend authenticates user.
3. Backend validates conversation ownership.
4. Backend stores user message.
5. Backend loads character.
6. Backend infers intent, tone, subtext, time gap, and unresolved context.
7. Backend retrieves relevant typed memories, episodes, and relationship state.
8. Backend projects bounded emotional state and applies safety/content gates.
9. Backend chooses a private response strategy, question policy, length, rhythm,
   and optional initiative hook.
10. Backend compiles character soul and turn context into ordered prompt modules.
11. Backend calls the configured LLM provider and streams its response through
    the existing SSE contract.
12. Backend checks chunks for hard-boundary or private-plan leakage before SSE
    emission, then checks the completed reply for contradictions, invented
    history, repetition, interrogation, and tone drift.
13. Backend stores the completed assistant message exactly once, with bounded
    generation telemetry and no prompt text.
14. Backend updates relationship and emotional state.
15. Backend queues PostgreSQL-backed post-chat memory/journal/proactive work.
16. Failure or cancellation keeps the user message retryable and stores no
    partial assistant text.

Frontend character and conversation selection is versioned. Overlapping stale
loads cannot replace a newer choice, and a failed selection restores the last
fully loaded character/thread pair before surfacing a readable error.

## Prompt assembly

Prompt assembly must be centralized and testable.

The renderer compiles typed backend state into discrete safety, soul identity,
voice, relating, relationship, perception, user-fact, memory, episode, private
response-direction, recent-history, and current-turn modules. It never dumps raw
profile JSON, relationship meters, or a chain-of-thought plan. The current turn
remains last, and configured context budgets trim older or lower-priority context
before any high-priority instruction or current-message content.

## Background jobs

APScheduler may wake the worker, but PostgreSQL is the source of truth.

`scheduled_jobs` table supports:
- job_type
- run_at
- status
- locked_at
- locked_by
- retry_count
- payload_json

Job claiming should use database locking where practical.

The personal development runtime enables the scheduler by default; tests set
`ENABLE_SCHEDULER=false` so no background loop races deterministic fixtures.
Unexpected execution failures return to `pending` with capped exponential
backoff. Validation or unsupported-job failures are terminal. Completed,
retried, and failed jobs release worker lock fields, while authenticated Debug
reports configured versus actually running scheduler state.
Time-aware proactive jobs store their IANA timezone and intended local instant
in job payload metadata. A due job outside its allowed morning, goodnight, or
quiet-hours window returns to `pending` at the next eligible UTC instant,
releases its worker lock, and does not consume failure retry budget. Updating
presence clock preferences reschedules existing pending jobs for that
character.
Each runtime tick also takes one PostgreSQL transaction-scoped advisory lock.
This prevents overlapping batches across API processes and lets the test
session hold the matching lock so a live development server cannot consume
deterministic fixture jobs.

## Scaling path

MVP:
- one VM
- one backend process
- one PostgreSQL
- one Ollama

Later:
- split workers
- split inference host
- managed database
- queue system
- model router
- paid inference if user demand exists

Do not build later-stage infrastructure into MVP.
