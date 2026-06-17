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

Purpose: optional refresh token/session storage.

Fields:
- id UUID primary key
- user_id FK users.id
- token_hash string indexed
- expires_at datetime
- revoked_at nullable datetime
- created_at datetime

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

## conversations

Purpose: thread between user and character.

Fields:
- id UUID primary key
- user_id FK users.id
- character_id FK characters.id
- title nullable string
- created_at datetime
- updated_at datetime

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
- provider: mock | ollama
- prompt_version: string

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
- embedding vector nullable
- decay_score float default 0.0
- contradiction_group nullable string
- last_recalled_at nullable datetime
- metadata_json JSON
- created_at datetime
- updated_at datetime

Memory types:
- preference
- interest
- person
- place
- date
- event
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
- metadata_json JSON
- created_at datetime
- updated_at datetime

Recommended bounds:
- trust: -100 to 100
- intimacy: 0 to 100
- warmth: -100 to 100
- tension: 0 to 100
- familiarity: 0 to 100
- attachment: 0 to 100

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
