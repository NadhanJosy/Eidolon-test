# Data Model

## Design principles

- Use UUID primary keys.
- Use timezone-aware timestamps.
- Use JSON columns for flexible metadata, but not as a replacement for core relational fields.
- Every user-owned row must be scoped to a user directly or through conversation/character ownership.
- Never expose password hashes or tokens in exports/debug endpoints.

## users

Purpose: application users.

Fields:
- id UUID primary key
- email string unique indexed
- password_hash string
- display_name nullable string
- age_gate_confirmed boolean default false
- created_at datetime
- updated_at datetime

## refresh_tokens

Purpose: local session continuity without external auth services.

Fields:
- id UUID primary key
- user_id FK users.id
- token_hash string indexed
- expires_at datetime
- revoked_at nullable datetime
- created_at datetime

Refresh token values are random opaque strings. Only hashes are stored. Refresh
rotates tokens; logout revokes the active refresh token when present. The raw
token is delivered to browsers only as the host-only `eidolon_refresh` HttpOnly
cookie scoped to `/auth`, never in JSON responses, exports, or debug payloads.
The frontend keeps access tokens in memory and deletes legacy localStorage auth
values during session restoration.

## auth_throttles

Purpose: bound costly login and registration work across API processes without
retaining raw attempted identity or network-address text.

Fields:
- fingerprint string primary key (HMAC-SHA256 of scoped canonical identity or client host)
- failed_attempts integer, minimum 1
- window_started_at datetime
- blocked_until nullable datetime
- last_attempt_at datetime indexed

These rows are operational abuse-control state rather than user-owned profile
data. Login identity/client and registration client records use independent
HMAC scopes. A successful login clears only matching login records;
registration records persist across successful account creation and duplicate
conflicts so account creation cannot reset its own resource limit. Rows are
pruned after four configured window/block periods. They are intentionally absent
from account export and do not need a user foreign key or account-deletion
cascade.

## characters

Purpose: character configuration.

Fields:
- id UUID primary key
- owner_user_id FK users.id
- name string
- description nullable text
- personality_core nullable text
- speech_style nullable text
- boundaries_json JSON
- explicit_age nullable integer
- adult_mode_allowed boolean default false
- content_intensity integer default 0
- created_at datetime
- updated_at datetime

Character `boundaries_json` stores the richer authored profile for the MVP,
including relationship type, scenario preset, memory preferences, proactive
preferences, and structured consent guidance such as consent style, soft limits,
hard limits, and aftercare style.

Known `memory_preferences` controls are booleans: `remember_preferences`,
`remember_emotional_notes`, `private_mode_default`, and
`adult_memory_storage`. Character persistence keeps adult-dependent state
canonical: `adult_mode_allowed=false` implies `content_intensity=0` and adult
memory storage off, while private-by-default also forces adult memory storage
off. Unknown authored profile fields remain available for forward-compatible
text-only features.

Known `proactive_preferences` clock fields are:
- `timezone`: IANA timezone name
- `quiet_hours_start` and `quiet_hours_end`: 24-hour local times
- `morning_time` and `goodnight_time`: 24-hour local delivery targets
- `cooldown_hours`: whole-number minimum gap between automatic notes, from 1
  to 168 hours

The API validates these known fields while runtime scheduling retains safe UTC
clock defaults and a 24-hour cooldown for legacy rows that do not contain them.

API schemas bound the top-level profile text and reject `boundaries_json` that
exceeds the allowed serialized size, nesting depth, collection fan-out, key
length, or individual string length. These limits protect the prompt and
database even when the browser client is bypassed.

## conversations

Purpose: thread between user and character.

Fields:
- id UUID primary key
- user_id FK users.id
- character_id FK characters.id
- title nullable string
- metadata_json JSON
- last_read_at datetime
- created_at datetime
- updated_at datetime

Conversation metadata:
- privacy_mode: `normal` or `private`
- scenario_mode: `default` or `custom` when explicitly changed
- scenario_text: normalized custom Shared Scene text only in `custom` mode,
  bounded to 1200 characters

Private conversations persist messages in the thread but do not create new
memory items, episodic journals, relationship changes, or proactive jobs from
chat in that thread.

`last_read_at` is the authenticated user's durable read cursor for assistant
messages in the thread. Conversation API responses derive `last_message_at` and
`unread_count` from message rows; those values are not separately persisted.
Cursor updates use an exact rendered assistant-message boundary and never move
backward.

Shared Scene updates are row-locked and idempotent. Reset removes custom prose
from metadata and restores the character profile setting. Conversation export
retains the owner-visible text; prompt/debug manifests retain only mode and
bounded text length. Generic scene-change system events never copy scene prose.

## messages

Purpose: individual chat messages.

Fields:
- id UUID primary key
- conversation_id FK conversations.id
- role string: user | assistant | system
- content text
- metadata_json JSON
- created_at datetime

Metadata examples:
- proactive: true
- streaming_complete: true
- provider: groq | mock | ollama
- prompt_version: string
- privacy_mode: `normal` or `private`, captured when the turn is accepted
- system_event: true for controlled backend-owned thread events
- event_type: `privacy_mode_changed` or `scenario_changed`
- event_label: bounded user-facing label

User and assistant messages in the same turn share the accepted privacy mode.
A private message remains available in owned history, search, and export, but
is excluded from later standard prompt history, memory extraction, episodic
journals, relationship updates, and proactive context.

Privacy-transition events use role `system`, remain part of visible thread
history, and do not count as unread assistant messages or feed memory,
relationship, journal, or proactive state.

## memory_items

Purpose: durable semantic memories.

Fields:
- id UUID primary key
- user_id FK users.id
- character_id FK characters.id
- source_message_id nullable FK messages.id
- memory_type string
- content text
- importance float default 0.5
- confidence float default 0.5
- emotional_weight float default 0.0
- pinned boolean default false
- embedding vector(384) nullable; new and edited memories receive a normalized
  local feature embedding, while legacy null rows are backfilled during recall
- decay_score float default 0.0
- contradiction_group nullable string
- last_recalled_at nullable datetime
- forgotten_at nullable datetime; non-null rows are retained for owner review and
  export but excluded from active cognition
- metadata_json JSON
- created_at datetime
- updated_at datetime

Message-linked memories use `source_message_id` as the primary source.
`metadata_json.source_message_ids` preserves bounded additional source ids
after dedupe merges. `metadata_json.source=user_saved` plus bounded `capture`
metadata identifies an explicit user selection without changing the source
message.

`metadata_json.forget_history` keeps a bounded record of fade transitions and
their reason. Restoring or re-learning a matching memory clears `forgotten_at`,
records the restore reason, and makes the row eligible for recall again.

The API does not serialize raw embedding vectors. They are backend-owned recall
state and are recomputed whenever memory content changes.

Memory types:
- preference
- interest
- person
- place
- date
- event
- shared_moment
- inside_joke
- boundary
- relationship_milestone

## relationship_states

Purpose: numeric relationship variables between user and character.

Fields:
- id UUID primary key
- user_id FK users.id
- character_id FK characters.id
- trust float default 0
- intimacy float default 0
- warmth float default 0
- tension float default 0
- familiarity float default 0
- attachment float default 0
- mood string default steady
- conflict_state string default clear
- repair_needed boolean default false
- tags_json JSON list
- last_interaction_at nullable datetime
- metadata_json JSON, including timeline entries, milestone ids, recent_changes,
  recent_change_summary, and proactive_milestones_noted
- created_at datetime
- updated_at datetime

Recommended bounds:
- trust: -100 to 100
- intimacy: 0 to 100
- warmth: -100 to 100
- tension: 0 to 100
- familiarity: 0 to 100
- attachment: 0 to 100

Stateful user messages may include `metadata_json.relationship_effect`, a
compact source-linked record of the relationship deltas and milestone ids
created by that accepted turn. Latest-turn edits use this metadata to reverse
and recalculate relationship state without requiring a separate audit table.

## scheduled_jobs

Purpose: background work and proactive messages.

Fields:
- id UUID primary key
- user_id nullable FK users.id
- character_id nullable FK characters.id
- job_type string
- run_at datetime
- status string: pending | running | done | failed | cancelled
- locked_at nullable datetime
- locked_by nullable string
- payload_json JSON
- retry_count integer default 0
- last_error nullable text
- created_at datetime
- updated_at datetime

Job types:
- maintenance_noop
- memory_extract
- relationship_decay
- proactive_inactivity_check
- proactive_message_create
- proactive_morning_check
- proactive_goodnight_check
- proactive_thinking_of_you
- proactive_milestone_check
- proactive_unresolved_thread_nudge
- proactive_delayed_double_text

Time-aware proactive payloads also retain `respect_local_time`,
`delivery_timezone`, and `scheduled_local_time`. Quiet-hour deferral stores a
bounded reason and next instant without incrementing `retry_count`.

## diagnostic_events

Purpose: bounded, privacy-safe visibility into foreground reply failures.

Fields:
- id UUID primary key
- user_id FK users.id
- character_id nullable FK characters.id
- conversation_id nullable FK conversations.id
- source controlled string
- operation controlled string: message | stream | reroll | edit
- code controlled string: authentication | context_overflow | generation_failed |
  malformed_response | model_unavailable | provider_unavailable |
  quota_exhausted | rate_limited | refusal | timeout
- provider allowlisted string: mock | ollama | unknown
- safe_message controlled string
- created_at datetime

Rows cascade with their owning account, character, or conversation and are
retained to the newest 100 per user. The recorder uses an independent
transaction after request rollback and is best-effort, so diagnostics cannot
replace the original API/SSE failure. Raw prompts, user/companion prose,
exception text, provider response bodies, URLs, and stack traces are forbidden.

## episodic_journals

Purpose: durable summaries of shared episodes, callbacks, unresolved threads, and emotional continuity.

Fields:
- id UUID primary key
- user_id FK users.id
- character_id FK characters.id
- conversation_id nullable FK conversations.id
- journal_type string
- title string
- summary text
- emotional_tags_json JSON
- unresolved_threads_json JSON
- callbacks_json JSON
- importance float
- metadata_json JSON
- created_at datetime
- updated_at datetime

Automatic journal metadata can include a bounded `episode_focus`,
`continuity_signals`, and matching `continuity_notes`. Signals distinguish
repair arcs, anniversaries, inside jokes, milestones, shared moments, shared
references, callbacks, open threads, steady exchanges, and adult-redacted
episodes.

Journal ownership is explicit in `metadata_json`. Automatic rows use
`source=deterministic_summarizer` and retain `created_by` for compatibility;
manual rows use `source=manual`. Conversation refresh updates only deterministic
rows. A manual edit records `edited_by_user_at` and never changes generated
continuity metadata.
