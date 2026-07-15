# API Contract

## General conventions

- JSON API
- Auth required for all user data endpoints after auth is implemented
- Error responses should be readable and not leak stack traces
- Use UUID strings in JSON
- Timestamps should be ISO 8601

## Health

GET /health

Response:
```json
{
  "status": "ok",
  "service": "eidolon-api"
}
```

GET /health/db

Response:
```json
{
  "status": "ok"
}
```

GET /health/llm

The provider configuration is validated during startup. The endpoint probes the
configured model and returns `configuration: configured` plus a `readiness` of
`reachable` or `degraded`; provider failures do not fail the whole app and the
payload never includes credentials.

## Auth

POST /auth/register

Request:
```json
{
  "email": "user@example.com",
  "password": "a-secure-passphrase",
  "display_name": "Nadhan"
}
```

Registration trims and lowercases email addresses, validates an ASCII mailbox
and dot-qualified domain without adding an external validator dependency, and
requires a password between 12 and 256 characters with at least one non-space
character. Optional display names collapse surrounding/repeated whitespace;
blank values become `null`, and control/format characters are rejected.

After schema and browser-Origin validation but before Argon2, registration
checks an independent PostgreSQL-backed ASGI-client limit. Each request allowed
to reach password hashing is durably counted before user creation, including a
later duplicate-email conflict. The configured threshold request may complete;
subsequent requests during the block return generic `429` with an integer
`Retry-After`. Validation and rejected-Origin failures do not consume this
costly-attempt quota. Only a secret-keyed client fingerprint is stored.

Response:
```json
{
  "access_token": "jwt",
  "token_type": "bearer",
  "user": {
    "id": "uuid",
    "email": "user@example.com",
    "display_name": "Nadhan"
  }
}
```

The response also sets a host-only `eidolon_refresh` cookie. The cookie is
HttpOnly, scoped to `Path=/auth`, and carries the configured `SameSite`,
`Secure`, and refresh lifetime settings. Refresh-token values are never returned
in JSON.

The access token is an HS256 JWT requiring `iss=eidolon-api`,
`aud=eidolon-web`, `type=access`, `sub` as a user UUID, `jti` as a token UUID,
and `iat`, `nbf`, and `exp` timestamps. Decoding requires every claim, allows
only HS256, and applies five seconds of clock-skew tolerance. Wrong-key,
wrong-algorithm, expired, premature, incomplete, or semantically mismatched
tokens follow the normal unauthenticated `401` path.

POST /auth/login

Response matches register and sets a rotated `eidolon_refresh` cookie.
Login applies the same email canonicalization but preserves compatibility with
existing passwords. Unknown accounts, wrong passwords, and malformed stored
password hashes return the same `401` response; an unknown account still runs a
dummy Argon2 verification to reduce account-existence timing differences.

Before Argon2, login checks the same auth throttle store for both a secret-keyed
canonical-email fingerprint and a secret-keyed ASGI-client fingerprint. The
threshold-triggering failure and requests during the bounded block return the
same `429` response for known and unknown identities with an integer
`Retry-After` header. A successful login clears the matching identity/client
failures. Raw attempted emails and client addresses are never stored in throttle
rows or returned by export/debug endpoints.

POST /auth/refresh

Request:
```json
{}
```

Refresh reads the HttpOnly `eidolon_refresh` cookie, rotates the stored token,
sets a replacement cookie, and returns a new access token response. During
legacy migration only, the endpoint also accepts a bounded body token:
```json
{
  "refresh_token": "opaque-refresh-token"
}
```

Cookie refresh requests and legacy browser-origin requests reject untrusted
`Origin` headers with `403`. Reusing a rotated, revoked, expired, malformed, or
unknown refresh token returns `401` and clears the refresh cookie.

JWT signing-key rotation does not invalidate independently hashed refresh rows.
A valid refresh cookie can therefore obtain a replacement access token after
rotation, while all previously signed access tokens fail closed.

GET /auth/me

POST /auth/logout

Optional legacy migration request:
```json
{
  "refresh_token": "opaque-refresh-token"
}
```

Logout revokes the cookie refresh token when present, accepts the optional
legacy body token for migration cleanup, and always clears the `eidolon_refresh`
cookie. The frontend keeps access tokens in memory only and removes any legacy
browser-stored auth values when the app opens or clears a session.

## Characters

GET /characters

POST /characters

Creates the full authored profile in one transaction and initializes its
relationship state. Names are whitespace-normalized. Description, personality,
speech, and flexible `boundaries_json` profile content are bounded; excessive
JSON size, depth, fan-out, key length, or string length returns `422`.
Known proactive clock fields inside `boundaries_json.proactive_preferences`
accept an IANA `timezone` and 24-hour `quiet_hours_start`,
`quiet_hours_end`, `morning_time`, and `goodnight_time`. `cooldown_hours`
accepts a whole number from 1 to 168 and controls the minimum gap between
automatic companion notes. Invalid zones, clock values, or cooldown values
return `422`.
Character update fields backed by non-nullable columns must be omitted when
unchanged; explicitly sending `null` for name, profile JSON, adult eligibility,
or intensity also returns `422`.

GET /characters/{character_id}

PATCH /characters/{character_id}

Changing proactive clock or enablement preferences reschedules or cancels that
character's pending proactive rows in the same transaction.

## Conversations

GET /conversations

Conversation responses include:
- `last_read_at`: durable per-thread read cursor
- `last_message_at`: latest message timestamp or `null`
- `unread_count`: assistant messages newer than the read cursor

POST /conversations

Request:
```json
{
  "character_id": "uuid-or-null",
  "title": "Optional title",
  "privacy_mode": "normal"
}
```

`privacy_mode` may be `normal` or `private`. Private conversations still store
messages in the thread, but chat completion skips durable memory extraction,
episodic journal updates, relationship mutation, and proactive job scheduling.
New conversations persist explicit `privacy_mode` and `scenario_mode: default`
metadata and return their owner, character, read cursor, empty message state,
and creation/update timestamps. Titles are whitespace-normalized, bounded to
200 characters, and reject control or format characters; an absent or blank
creation title uses the character-derived default.

PATCH /conversations/{conversation_id}

Request:
```json
{
  "title": "Updated title",
  "privacy_mode": "private",
  "scenario": {
    "mode": "custom",
    "text": "A quiet shared project with practical companionship."
  }
}
```

Changing `privacy_mode` creates one SFW system event in the visible thread.
Writing the already-active mode is idempotent and creates no duplicate event.
Concurrent updates are serialized on the owned conversation row so matching
requests cannot create duplicate transition events.
The event is stored in the same transaction as the mode change and remains
excluded from assistant unread counts and companion cognition.
Conversation PATCH requests must include at least one field. `title: null` or a
blank title intentionally clears the title, while explicit null privacy or
scenario values fail validation.

`scenario.mode` is `default` or `custom`. Custom mode requires normalized,
visible text of at most 1200 characters; default mode rejects custom text and
removes any existing `scenario_text`. Invisible controls, hard-block safety
cues, explicit null, missing custom text, and oversized values fail closed.
Updates are owner-scoped, row-locked, and idempotent. A real change creates a
generic SFW `scenario_changed` event without copying the authored scene. The
effective scene is local to this conversation, reaches response planning and
generation, remains in owner-visible conversation/export data, and is reduced
to mode plus text length in Debug.

GET /conversations/{conversation_id}/messages

GET /conversations/{conversation_id}/search?q=term&limit=20

Search is owner-scoped, case-insensitive, and limited to 1-120 query characters
with 1-50 results. Leading and trailing whitespace is ignored; a whitespace-only
query is rejected. PostgreSQL pattern characters (`%`, `_`, and `\\`) are escaped
and matched literally, so user input cannot broaden a search into an unintended
wildcard query. Results are returned in chronological order within the bounded
most-recent match window.

POST /conversations/{conversation_id}/read

Request:
```json
{
  "through_message_id": "rendered-assistant-message-uuid-or-null"
}
```

Advances the cursor atomically through that exact owned assistant message and
returns the refreshed conversation summary. A null boundary is a no-op for an
empty thread. A missing, user-authored, or cross-thread boundary returns `404`;
concurrent assistant messages newer than the supplied boundary remain unread.

PATCH /conversations/{conversation_id}/messages/{message_id}

Request:
```json
{
  "content": "Revised user text"
}
```

Edits only the latest user-authored turn in the owned thread. The endpoint
validates the revised text, removes later companion replies for that turn,
clears queued conversation jobs, clears the conversation-local episodic
journal before regeneration, removes source-linked memories for the edited
line, reverses and reapplies source-linked relationship effects when available,
and returns a fresh `ChatResponse` with the edited user message plus a new
companion reply. The original turn privacy is preserved. Cross-account requests
return `404`; attempts to edit older user turns or turns followed by system/user
events return `409`; unavailable inference returns `503` without committing the
edit.

POST /conversations/{conversation_id}/messages/{message_id}/remember

Pins a user-selected user or companion message as durable memory and returns
the resulting memory. Repeated requests are idempotent, and an existing
automatic memory for the same source is promoted rather than duplicated.
Returns `404` outside the authenticated account scope, `409` when current or
original thread privacy or adult-memory preferences block storage, and `422`
for unsupported roles or content that must not enter durable memory.

DELETE /conversations/{conversation_id}/messages/{message_id}

Deletes one message from an owned thread. Companion and proactive messages are
removed as single rows while also removing memory links sourced only from that
reply, clearing stale conversation-local journals and queued jobs, rebuilding
the journal from remaining safe messages, and rebuilding fresh proactive jobs
only when the remaining latest state is a normal non-private companion reply.
System events are presentation-only and are removed as single rows without a
cognition rebuild. User-authored messages are deleted only when they are the
latest safe user turn: every later row in the conversation must be a companion
reply from that turn. A latest user-turn delete removes the user line and
dependent companion replies, reverses source-linked relationship effects when
available, removes memory links sourced from the user line or any dependent
reply, clears stale conversation-local journal rows, rebuilds the journal from
remaining safe messages when older continuity still exists, removes stale
queued conversation jobs, and applies the same guarded proactive rebuild.
Cross-account or cross-thread requests return `404`; older user turns or turns
followed by new user/system events return `409`.

DELETE /conversations/{conversation_id}/messages

Deletes visible message rows, conversation-local episodic journals, and queued
jobs from the owned thread in one transaction. The conversation remains
available as an empty room and receives a fresh update timestamp. Durable
memories and character-level relationship history remain unless the user clears
those separately. Sibling threads and their journals/jobs are not affected.
Assistant completion locks the conversation and verifies its source user row,
so an inference that finishes after a successful clear is discarded with a
controlled conflict instead of repopulating the empty thread.

DELETE /conversations/{conversation_id}

Deletes the owned conversation and removes queued jobs tied to it. Message rows
and conversation-scoped episodic journal rows are removed through the same
operation. Cross-account requests return `404`.

## Chat

POST /chat/messages

Request:
```json
{
  "conversation_id": "uuid",
  "content": "Hello",
  "content_mode": "sfw",
  "privacy_mode": "normal"
}
```

`privacy_mode` defaults to `normal`. Sending `private` makes this accepted user
turn and its assistant reply private without changing conversation metadata.
It may tighten a normal thread but cannot weaken a thread whose mode is already
private. Unsupported values return `422` before a message is stored.

Response:
```json
{
  "user_message": {
    "id": "uuid",
    "role": "user",
    "content": "Hello",
    "created_at": "timestamp"
  },
  "assistant_message": {
    "id": "uuid",
    "role": "assistant",
    "content": "A completed provider response",
    "created_at": "timestamp"
  }
}
```

POST /chat/stream

Use SSE or streaming response.

Events:
- message_start
- token
- message_done
- error

Request bodies may include `retry_user_message_id` for the final persisted user
turn after a stopped or failed response. The supplied content must exactly match
that owned message. A retry never inserts a second user row and is rejected once
the turn already has a completed assistant reply.

`message_start` is the server-accepted boundary for the user turn and moves the
client from connecting to composing. One or more `token` events move it to
streaming, and `message_done` supplies the single persisted final assistant
message. Events must arrive in that order. A client should treat a clean EOF
without `message_done` or `error` as an incomplete reply, and should cancel and
ignore the stream if its conversation is no longer active. One-turn composer
privacy and draft clearing should reset at `message_start`, not merely when an
HTTP response opens, so pre-acceptance failures remain retryable.

`error` includes a bounded safe detail, failure type, retryable flag, and the
persisted user-message ID when one exists. Provider exception bodies, keys,
prompts, and private message text are never copied into the event. Cancellation
or disconnect marks the user turn retryable/cancelled and persists no partial
assistant output.

POST /chat/reroll

Creates an alternate assistant message for the previous user turn, records
`reroll_of` metadata, and preserves or tightens the original turn privacy.

## Memory

GET /characters/{character_id}/memories

Returns active memories by default. `state=forgotten` returns only forgotten
rows and `state=all` returns both states. All variants remain owner-scoped.

POST /characters/{character_id}/memories

GET /characters/{character_id}/memories/search?q=term

PATCH /characters/{character_id}/memories/{memory_id}

POST /characters/{character_id}/memories/{memory_id}/resolve

Keeps the selected conflicting memory, removes opposing memories in the same
contradiction group, clears stale contradiction links, and returns the kept
memory plus removed ids. Returns `409` when the memory has no active opposing
conflict.

POST /characters/{character_id}/memories/{memory_id}/forget

Idempotently removes one memory from active recall without deleting it. Pinned
memories may be explicitly forgotten by their owner, but automatic decay never
forgets a pinned row.

POST /characters/{character_id}/memories/{memory_id}/restore

Idempotently restores a forgotten memory, lowers accumulated decay, and
recomputes active contradiction links.

DELETE /characters/{character_id}/memories/{memory_id}

DELETE /characters/{character_id}/memories

POST /characters/{character_id}/memories/forget

Moves eligible low-confidence, high-decay, unpinned memories into forgotten
state and returns the number transitioned. Repeated calls do not recount rows.

## Episodic Journals

GET /characters/{character_id}/journals

POST /characters/{character_id}/journals

Creates an owner-authored personal note. Title and summary are normalized and
must contain visible text. A conversation link does not transfer ownership to
the deterministic summarizer.

PATCH /characters/{character_id}/journals/{journal_id}

Updates title, summary, and/or importance for an owner-scoped personal note.
Empty bodies, explicit nulls, and whitespace-only text return `422`. Generated
episodes return `409` because they are rebuilt from their transcript.

DELETE /characters/{character_id}/journals/{journal_id}

Deletes an owner-scoped personal note. Generated episodes return `409`; their
lifecycle remains attached to conversation edit, clear, and delete operations.

## Relationship

GET /characters/{character_id}/relationship

Relationship response includes numeric state, mood, conflict state, repair-needed flag, tags, and timeline metadata.

## Adult Gate Status

GET /characters/{character_id}/adult-status

Returns requested/effective mode, gate allowance, blocked reasons, and content intensity.

`POST /characters` and `PATCH /characters/{character_id}` reject
`adult_mode_allowed=true` unless `explicit_age` is 18 or older. Adult-enabled
create/update requests also reject hard-block cues in merged character profile
text, including identity, backstory, scenario, greeting, consent, limits, and
profile JSON strings. Refusal/limit language such as "no minors" remains valid;
scenario or identity text that implies minors, ambiguous age, coercion,
exploitation, stalking, privacy abuse, real-world harm, illegal sexual content,
or safety bypassing returns `400`.
Clients must not treat profile eligibility as permission to use adult mode;
user age, relationship repair, consent, and content safety gates still apply.

The API canonicalizes dependent persisted settings after validating the merged
profile. When adult eligibility is disabled, `content_intensity` is stored as
`0` and `memory_preferences.adult_memory_storage` is stored as `false` when the
memory-preference object exists. Private-by-default profiles also store adult
memory as disabled. A disable-only partial update therefore cannot leave dormant
adult settings enabled. Known memory controls must be booleans and malformed
objects return `422`; unknown profile fields are preserved.

## Debug

GET /debug/character/{character_id}

Returns current owner-scoped runtime, relationship, selected memory/journal,
provider, and retrieval-summary state. It does not assemble a synthetic prompt
or return prompt text. `prompt_context.current_summary` contains bounded
character/relationship posture, selected memory and journal IDs/types,
continuity signals, pending proactive labels, safety posture, and snapshot time.

The private `relationship` snapshot exposes raw bounded metrics, mood, conflict
state, repair posture, tags, and timeline for authenticated Debug inspection.
The private `memories` snapshot contains up to 10 current active memories with
id, type, content, importance, confidence, and pinned state. It never includes
embeddings, internal ranking features, deleted rows, or forgotten rows. These
fields are diagnostic data and must not be copied into the primary conversation
surface.

`errors` contains at most 20 newest character-scoped foreground generation
failures. Each row has an id, optional conversation id, controlled source,
operation and code, an allowlisted provider label, approved safe message, and
timestamp. The API never returns the originating exception, prompt, message,
provider body, URL, or traceback. Up to 100 rows per account are retained.

GET /debug/conversation/{conversation_id}

Returns recent messages plus a `memory_pipeline` array for recent user turns.
Each pipeline row includes message id, content/privacy mode, bounded memory
candidate decision metadata, and the stored memory id/type when automatic
learning created one. Debug memory decisions are not added to normal chat
response metadata.

`last_assembled_context` is the newest validated manifest actually recorded by
ordinary chat, SSE, reroll, or edited-turn regeneration. It contains provider,
prompt version/size, effective mode, assembly time, generation kind, a bounded
private response-plan summary, and selected context IDs/types/roles. It never
contains raw prompt, user-message, memory, or journal text. Missing or malformed
legacy context returns `null` or is skipped for an older valid manifest.

The private manifest is persisted under internal user-message metadata so a
streamed provider failure can still be diagnosed. Every normal `MessageOut`
surface strips underscore-prefixed internal metadata, including chat, stream,
history, search, edit, reroll, and Debug's recent-message list.

GET /debug/jobs

Proactive job payloads expose safe generation provenance after processing:
`generation_source` is `llm` or `fallback`, and `generation_reason` is a bounded
label when fallback was required. `relationship_posture` is a bounded
qualitative key and never a score dump. Provider exception text and rejected
output are never stored in job payloads.

Ordinary message, stream, reroll, and edited-turn provider failures return fixed
safe client text and record their Debug event only after the failed request
transaction rolls back. Failure to write diagnostics never changes the original
`503` or SSE error outcome.

Debug endpoints must be authenticated and scoped to current user.

In production, debug endpoints are unavailable unless `ENABLE_DEBUG_ROUTES=true`
is set explicitly. Development and testing keep them available for local
inspection.

## Export

GET /account/export

Returns an authenticated, account-scoped JSON backup containing the current
user profile plus owned characters, conversations, messages, memories,
episodic journals, relationship states, and scheduled jobs. The export
preserves continuity metadata and lifecycle timestamps, including conversation
privacy state, memory recall/extraction state, journal continuity signals,
relationship timeline/recent-change state, and proactive job payloads. Nullable
timestamps are returned as `null`.

DELETE /account

Response should exclude:
- password_hash
- token hashes
- secrets
- environment variables

Export queries remain scoped to the authenticated user. An export must not
contain another account's rows, password hashes, refresh-token hashes, runtime
secrets, or environment configuration.

Account deletion requires the current password and exact confirmation phrase
`DELETE MY ACCOUNT`. It deletes the current user row and relies on PostgreSQL
cascades to remove account-owned characters, conversations, messages, memories,
journals, relationship state, refresh tokens, and scheduled jobs. A successful
delete also clears the `eidolon_refresh` cookie.
