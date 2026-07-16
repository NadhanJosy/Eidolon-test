# API

## Authority and conventions

FastAPI's generated `/docs` and `/openapi.json`, Pydantic schemas in
`apps/api/app/schemas.py`, and route implementations in `apps/api/app/api` are
the executable contract. This document is the maintained route inventory and
behavioural overview.

- JSON request/response bodies unless noted
- UUID strings and ISO 8601 timestamps
- readable bounded errors with no stack traces or secret details
- bearer access token required for private routes
- credentialed requests include the refresh cookie where applicable
- owner-scoped missing resources normally return `404`
- validation errors return `422`; conflicts use `409`; provider availability
  failures use a bounded `4xx/5xx` response or terminal SSE error event

## Health

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/health` | Process liveness; does not probe dependencies |
| GET | `/ready` | Bounded PostgreSQL readiness check |
| GET | `/health/db` | Explicit database diagnostic |
| GET | `/health/llm` | Configured-provider readiness diagnostic |

Health payloads never include connection strings, credentials, provider bodies,
or exception text.

## Authentication

| Method | Path | Purpose |
| --- | --- | --- |
| POST | `/auth/register` | Create account, default companion, access token, refresh cookie |
| POST | `/auth/login` | Authenticate and issue/rotate session |
| POST | `/auth/refresh` | Rotate refresh token and return new access token |
| GET | `/auth/me` | Return current user |
| PATCH | `/auth/me` | Update display name and/or age-gate confirmation |
| POST | `/auth/logout` | Revoke active refresh token and clear cookie |

Registration requires a normalized email and a 12-256 character passphrase.
Login and registration apply PostgreSQL-backed throttles before expensive
password work. Unknown account and wrong-password failures share generic copy.

Register/login/refresh return an access token plus a user object. Refresh-token
values are never returned in JSON. A bounded body refresh token remains accepted
only for legacy browser migration.

## Companions

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/characters` | List owned companions |
| POST | `/characters` | Create validated companion and relationship row |
| GET | `/characters/{character_id}` | Get owned companion |
| PATCH | `/characters/{character_id}` | Update and recanonicalize companion |
| GET | `/characters/{character_id}/relationship` | Get current decayed relationship |
| GET | `/characters/{character_id}/adult-status` | Get character-bound gate result |

Profile writes validate text/JSON bounds, proactive clock settings, adult
eligibility, and hard safety constraints. Changes to proactive preferences
reschedule or cancel pending work in the same transaction.

## Conversations and messages

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/conversations` | List owned thread summaries and unread state |
| POST | `/conversations` | Create normal/private thread |
| PATCH | `/conversations/{conversation_id}` | Update title, privacy, or Shared Scene |
| POST | `/conversations/{conversation_id}/read` | Advance read cursor through exact assistant message |
| GET | `/conversations/{conversation_id}/messages` | List ordered messages |
| GET | `/conversations/{conversation_id}/search` | Literal case-insensitive text search |
| POST | `/conversations/{conversation_id}/messages/{message_id}/remember` | Capture eligible message as memory |
| PATCH | `/conversations/{conversation_id}/messages/{message_id}` | Edit latest user turn and regenerate |
| DELETE | `/conversations/{conversation_id}/messages/{message_id}` | Delete supported message/turn and dependent state |
| DELETE | `/conversations/{conversation_id}/messages` | Clear thread transcript and local derived state |
| DELETE | `/conversations/{conversation_id}` | Delete whole thread |

Search uses `q` with a maximum of 120 characters and `limit` from 1 to 50.
`%`, `_`, and backslash are treated literally.

Conversation updates create controlled system events for real privacy/scenario
changes. Private turns remain visible but are ineligible for later cognition.
Latest-turn edit/delete and assistant deletion clean or rebuild source-linked
memory, journal, relationship, and queued-job state as applicable.

## Chat

| Method | Path | Purpose |
| --- | --- | --- |
| POST | `/chat/messages` | Completed non-streamed user + assistant turn |
| POST | `/chat/stream` | Fetch-based SSE turn or retry |
| POST | `/chat/reroll` | Generate alternate reply to an owned turn |

The normal frontend uses `/chat/stream`. Chat requests include a conversation
ID, content, requested content mode, and optional one-turn privacy/retry state.

SSE event order:

1. `message_start` with the canonical persisted user message
2. zero or more `token` events
3. `message_done` with the canonical completed assistant message

A terminal `error` event may replace completion. Disconnect/cancellation or
generation failure stores no partial assistant line; an accepted source user
message remains retryable.

## Memory

All memory routes are scoped below
`/characters/{character_id}/memories`.

| Method | Suffix | Purpose |
| --- | --- | --- |
| GET | `/` | List `active`, `forgotten`, or `all` via `state` |
| POST | `/` | Create manual memory |
| GET | `/search?q=...` | Retrieve up to ten active relevant memories |
| POST | `/forget` | Automatically forget eligible low-value memories |
| DELETE | `/` | Permanently clear all companion memories |
| PATCH | `/{memory_id}` | Edit content/scoring/pin fields |
| POST | `/{memory_id}/forget` | Reversibly forget one memory |
| POST | `/{memory_id}/restore` | Restore forgotten memory |
| POST | `/{memory_id}/resolve` | Keep selected side of active conflict |
| DELETE | `/{memory_id}` | Permanently delete one memory |

Raw embedding vectors are never returned.

## Journals

All routes are scoped below `/characters/{character_id}/journals`.

| Method | Suffix | Purpose |
| --- | --- | --- |
| GET | `/` | List owned manual and generated episodes |
| POST | `/` | Create manual note |
| PATCH | `/{journal_id}` | Edit manual note |
| DELETE | `/{journal_id}` | Delete manual note |

Generated summaries cannot be mutated through manual-note endpoints.

## Debug

Debug routes exist only when enabled by environment or in development/testing:

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/debug/character/{character_id}` | Bounded runtime, relationship, memory, journal, error, and prompt-context summary |
| GET | `/debug/conversation/{conversation_id}` | Recent messages, memory decisions, and latest validated context manifest |
| GET | `/debug/jobs` | Recent owned scheduled jobs |
| POST | `/debug/conversation/{conversation_id}/proactive` | Force one guarded check-in attempt |

Debug remains authenticated and owner-scoped. Production defaults to disabled.

## Account data

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/account/export` | Export owned product state without secrets/hashes |
| DELETE | `/account` | Verify password, erase account, clear refresh cookie |

The export contains the user profile, companions, conversations, messages,
memories, journals, relationships, and scheduled jobs. It excludes password and
refresh-token hashes, auth throttles, raw embeddings, provider keys, and JWT
secrets.
