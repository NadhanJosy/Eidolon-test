# Data Model

## Authority

SQLAlchemy models in `apps/api/app/models.py` and Alembic revisions in
`apps/api/alembic/versions` are the executable schema. This document explains
the stable ownership and lifecycle contracts.

Design rules:

- UUID primary keys
- timezone-aware timestamps
- PostgreSQL foreign keys with deliberate cascade behaviour
- direct or transitive ownership for every private row
- JSONB for bounded flexible metadata, not core ownership
- no secrets, password hashes, refresh-token hashes, or embeddings in normal
  API/export payloads

## Entity relationships

```text
users
  |-- refresh_tokens
  |-- characters
  |     |-- relationship_states (one per user + character)
  |     |-- memory_items
  |     |-- episodic_journals
  |     |-- continuity_threads
  |     `-- scheduled_jobs
  `-- conversations
        |-- messages
        |-- episodic_journals -- episodic_journal_sources -- messages
        |-- continuity_threads
        `-- scheduled_jobs (conversation ID in bounded payload metadata)

diagnostic_events belong to a user and may reference a character/conversation.
auth_throttles are non-profile operational state keyed by secret fingerprints.
```

## `users`

Account identity and top-level safety posture:

- canonical unique email
- Argon2 password hash
- optional display name
- user age-gate confirmation
- created and updated timestamps

Account deletion cascades owned state. Exports exclude the password hash.

## `refresh_tokens`

Server-side refresh sessions:

- owning user
- hash of an opaque random token
- expiry and optional revocation time
- creation time

The raw token exists only in the HttpOnly browser cookie. Rotation revokes the
old row and issues a new token.

## `auth_throttles`

Cross-process registration/login resource controls:

- HMAC-SHA256 scoped fingerprint
- failed/accepted expensive-attempt count
- window start, last attempt, and optional block expiry

Raw attempted emails and client addresses are not stored. These rows are not
user profile data and are omitted from export.

## `characters`

An owner-scoped authored companion:

- name and legacy description/personality/speech fields
- validated `soul_json` for identity and relating style
- bounded `boundaries_json` for scenario, consent, memory, privacy, and
  proactive preferences
- explicit age, adult eligibility, and content intensity

Canonicalization enforces dependent adult/privacy settings. Flexible profile
JSON is bounded by serialized size, depth, fan-out, key length, and string
length before persistence or prompt use.

## `conversations`

An owned thread tied to one companion:

- optional title
- metadata JSON
- durable `last_read_at` cursor
- created and updated timestamps

Known metadata includes:

- `privacy_mode`: `normal` or `private`
- `scenario_mode`: `default` or `custom`
- bounded custom `scenario_text` only in custom mode

`last_message_at` and unread count are derived from messages rather than stored
as independent counters.

## `messages`

Ordered thread content:

- role: `user`, `assistant`, or controlled `system`
- bounded text content
- bounded metadata JSON
- creation time

Metadata can carry privacy/content provenance, completion/provider telemetry,
proactive labels, reroll/source links, controlled system-event labels, and a
private prompt-context manifest. Assistant metadata can also carry a bounded
`pending|ready|degraded|skipped` continuity receipt containing committed IDs and
categorical change labels. Normal API serialization strips private
underscore-prefixed metadata.

Private provenance is immutable cognition input: later changing the thread mode
does not make a private message eligible for memory or normal prompt history.

## `memory_items`

Durable semantic memory owned by a user and companion:

- optional source message, `general|adult` scope, and normalized claim key
- `active|superseded|forgotten` lifecycle, `transient|normal|core` retention,
  standard/sensitive classification, and optional replacement link
- memory type and text
- importance, confidence, novelty, future relevance, emotional weight/context,
  recurrence count, pin state, and decay score
- nullable `vector(384)` embedding
- contradiction group and metadata links
- last recall/evidence/reinforcement and optional forgotten time
- bounded lifecycle/provenance metadata, including retrieval facets where useful

Embeddings are backend-owned and never serialized. Forgotten rows remain
owner-visible but are excluded from active retrieval, prompt assembly, recall
timestamps, and contradiction resolution until restored.

Claim keys let an explicit grounded correction supersede the prior active claim;
the older row remains private correction history and cannot re-enter retrieval
without a new decision. An unsupported difference remains an inspectable
conflict instead. Adult rows
are retrievable only for an effective adult turn and never enter normal recall.

Current memory types include user facts, preferences, interests, people, places,
dates, events, promises, themes, shared lore/moments, inside jokes, boundaries,
and relationship milestones.

`memory_evidence` stores the owner-exportable lifecycle record for creation,
reinforcement, merge, edit, correction, forgetting, restoration, and conflict
resolution. It links optional exact source messages and a bounded private
snapshot; it is never written to diagnostics or prompt text.

`memory_entities` deduplicates owner/companion-scoped people, places, dates,
projects, routines, and topics. `memory_entity_links` forms the many-to-many
shared-history graph. Entity rows track first/last evidence and mention count;
hard memory deletion cascades links and removes orphan entities.

## `episodic_journals`

Durable episode summaries and manual notes:

- owner, companion, optional source conversation, and `general|adult` scope
- type, title, summary, emotional tags
- unresolved threads, callbacks, importance, and metadata

Generated rows record deterministic ownership/provenance and may be rebuilt from
their conversation. Manual rows remain user-owned and are not overwritten by
automatic journal refresh.

`episodic_journal_sources` is a many-to-many provenance table linking generated
moments to exact user/assistant messages. Adult moments remain outside normal
journal retrieval and proactive anchoring.

## `continuity_threads`

First-class unfinished future intent owned by a user and companion:

- optional source conversation and source user message
- kind: `follow_up`, `plan`, `promise`, `repair`, or `ritual`
- bounded text, salience, confidence, and deterministic dedupe key
- lifecycle status: `open` or `resolved`, with resolution time
- last prompt reference, last proactive delivery, and bounded provenance metadata

Automatic rows require explicit safe SFW user language. Private/adult turns and
credential-like or blocked text are ineligible. Open rows can enter bounded
prompt retrieval; resolved rows remain owner-visible but are excluded. A source
message edit/delete removes the automatic row, conversation deletion cascades
local rows, and account/companion deletion cascades all owned rows.

## `relationship_states`

Exactly one row per user-companion pair:

- trust and warmth in `-100..100`
- intimacy, tension, familiarity, and attachment in `0..100`
- mood, conflict state, and repair flag
- private bounded emotional-state JSON
- tags, last interaction, timeline/milestone/evidence metadata

Source turns may store reversible relationship effects in message metadata so a
latest-turn edit/delete can undo and recompute its contribution without guessing
at older legacy turns. A structured cognition pass may add small bounded deltas
only from allowlisted grounded evidence labels; it cannot set metric values.

## `scheduled_jobs`

Durable asynchronous work:

- optional user and companion ownership
- type and due time
- status: `pending`, `running`, `done`, `failed`, or `cancelled`
- lock owner/time, retry count, safe last error, and bounded payload

Current work includes maintenance, `memory_extract`, `memory_maintenance`,
`chat_postprocess`, `relationship_decay`, and `proactive_*` jobs. Internal exception text and
rejected generated prose do not belong in job metadata.

Post-chat payloads may retain safe cognition source/failure labels, bounded token
counts, and the continuity receipt. They never retain the structured prompt,
evidence prose, provider body, or private reasoning.

## `diagnostic_events`

Bounded safe records for foreground generation failures:

- owner and optional companion/conversation
- controlled source, operation, error code, and provider label
- controlled safe message and timestamp

Rows are capped per user. Raw prompt/message text, exception bodies, provider
responses, URLs, credentials, and stack traces are forbidden.

## Migrations

- Every model/schema change requires an Alembic revision.
- Test upgrades from the real migration chain; do not replace it with
  `Base.metadata.create_all`.
- Cloud Run applies migrations before each new API revision starts.
- The migration advisory lock must remain intact.
- Prefer additive/backward-compatible production migrations because old and new
  Cloud Run revisions can briefly overlap.
- Destructive migrations require a verified backup and a staged compatibility
  plan.
