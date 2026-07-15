# Memory System

## Purpose

Memory allows characters to recall durable facts and shared history across sessions.

Memory should be useful, selective, and inspectable.

## Memory layers

### Active context

Recent messages used in live prompt assembly.

Stored in:
- messages table

### Semantic memory

Durable facts, preferences, named entities, interests, and boundaries.

Stored in:
- memory_items table

### Episodic memory

Summaries of meaningful events and emotional arcs.

Stored in:
- episodic_journals table

## MVP memory behaviour

MVP should support:

- create memory item
- retrieve relevant memories
- inject memories into prompt
- view memories in debug panel
- conservative extraction from messages

Level 2 additionally supports:

- active context from recent messages
- semantic memories with importance, confidence, emotional weight, pinning,
  decay, contradiction metadata, and normalized local feature embeddings
- episodic journals for summaries, callbacks, unresolved threads, emotional
  tags, milestones, anniversaries, repair arcs, inside jokes, shared moments,
  shared references, and redacted adult-mode episodes
- relationship milestone memory anchors created from one-time relationship threshold events
- adult-mode detail redaction for journal summaries, callbacks, unresolved threads, and proactive follow-up snippets
- user-selected message capture with source linkage, pinning, and dedupe promotion
- manual edit/delete/clear controls
- deterministic dedupe/merge and low-value forgetting
- bounded prompt injection through the reasoning context builder

## Episodic journal continuity

Automatic conversation journals now store bounded continuity metadata in
`metadata_json` without requiring a migration:

- `episode_focus` names the strongest deterministic signal for the episode.
- `continuity_signals` can include `repair_arc`, `anniversary`, `inside_joke`,
  `milestone`, `shared_moment`, `shared_reference`, `callback_request`,
  `open_thread`, `adult_redacted`, or `steady_exchange`.
- `continuity_notes` stores compact SFW notes for prompt assembly and private
  response planning.
- `redacted_adult=true` marks an adult-mode episode whose durable details were
  intentionally omitted.

Continuity snippets are only built from messages allowed for durable detail.
Adult-mode messages may create a redaction cue, but their scene details are not
copied into journal callbacks, open threads, summaries, or continuity notes.
Open-thread notes are intentional follow-ups, not every user question. A normal
question answered in the same turn does not create an unresolved-thread cue or a
future nudge; explicit future/reminder language such as "come back to this
later" or "remind me" can.

Anniversaries, inside jokes, and shared moments require explicit deterministic
markers and remain distinct from generic milestones or shared references. The
response planner uses their matching bounded note and must not invent an exact
date, duration, or shared detail that is absent from stored context.

Personal notes and generated episodes have separate ownership. The deterministic
summarizer selects only rows marked `source=deterministic_summarizer` or legacy
rows with the same `created_by` marker. It never chooses the newest manual note
as its update target. Personal notes can be edited or deleted through their
owner-scoped API; generated rows follow transcript edit/clear/delete behavior so
their summary and continuity signals cannot drift apart.

## Memory extraction rules

Extract only stable/useful facts:

- names, pronouns, and other explicit user facts
- preferences
- recurring interests
- important people
- important places
- important dates
- meaningful events
- explicit promises
- inside jokes
- explicit boundaries

Do not extract:

- every message
- random temporary moods
- secrets/passwords/tokens
- explicit adult details in MVP
- unsafe content
- information about minors in sexual/adult contexts
- messages whose accepted `privacy_mode` is `private`

Character memory preferences in `boundaries_json.memory_preferences` control
automatic extraction:

- `remember_preferences=false` skips preference memories learned from chat.
- `remember_emotional_notes=false` skips emotional event and inside-joke memories
  learned from chat.
- boundary memories remain allowed because they represent safety, consent, and
  interaction limits.

Manual memory creation is still allowed through the memory API so the user can
save an explicit note by hand even when automatic learning is reduced.

## User-selected message memory

The chat surface lets the user explicitly keep a user or companion line. The
backend remains authoritative:

- current private threads and lines originally written in private mode cannot
  be captured, even if the thread is later switched back to standard
- character-wide memory pause and adult-memory opt-in rules still apply
- system messages, blocked content, and credential-like content are rejected
- selected memories are pinned and marked `source=user_saved`
- `source_message_id` keeps the primary source and
  `metadata_json.source_message_ids` preserves source provenance
- explicit saves from distinct messages remain independently source-linked;
  similarity merging remains available to automatic extraction

Scheduled batch extraction applies the same message-level privacy filter even
when the containing thread is currently standard. Selecting memories for a
private turn must not update `last_recalled_at`.
- an existing automatic memory is promoted in place, and repeat capture is
  idempotent

The UI derives `Remembered` from returned user-selected memory metadata rather
than mutating message records or assuming that a request succeeded.

## Memory candidate pipeline

Automatic extraction now runs through a deterministic candidate analyzer before
anything is stored. The analyzer returns a bounded decision object instead of
letting extraction fail silently.

Accepted candidates include:
- memory type
- trigger phrase
- importance
- confidence
- emotional weight
- accept reason

Skipped candidates are labeled without storing the rejected message text. Skip
reasons include:
- `too_short`
- `unsafe_term`
- `blocked_content`
- `no_trigger`
- `empty_content`
- `disabled_by_preferences`

Accepted automatic memories store this bounded extraction summary in
`metadata_json.extraction` for private inspection and debugging.

The authenticated debug conversation endpoint also recomputes recent user-turn
decisions for the active thread and shows whether a stored memory was linked to
each turn. This debug view is separate from normal chat responses so primary
chat UI does not expose memory internals.

## Confidence

Memory confidence represents how reliable the memory is.

Recommended values:
- 0.9 explicit direct statement
- 0.7 repeated pattern
- 0.5 inferred but plausible
- 0.3 vague or uncertain

## Decay

Level 2 stores `decay_score`, `last_recalled_at`, `importance`, `confidence`,
`emotional_weight`, `pinned`, and nullable `forgotten_at`. Retrieval and
forgetting use these fields to keep durable memory useful without treating every
old note as equally relevant.

Forgetting is a reversible cognition state, not deletion. Automatic decay can
move only eligible unpinned rows out of active recall. Forgotten rows remain in
private export and the dedicated Forgotten view, but SQL retrieval, vector
candidates, prompt rendering, debug learning links, and active contradiction
groups exclude them. A manual restore, matching re-learn, or explicit Remember
action revives the same row instead of creating a duplicate. Permanent Delete
and full-memory clearing remain destructive, separate controls.

Decay considers:
- age
- recall frequency
- emotional weight
- contradiction
- user correction

## Background extraction

The `memory_extract` scheduled job processes recent user messages for a
conversation, or one specific user message when `message_id` is provided. It
uses the same extraction, unsafe-term filtering, dedupe/merge, contradiction,
and scoring logic as inline chat memory extraction. Completed job payloads
record `accepted_types` and `skip_reasons` counts so background memory behavior
can be audited without saving rejected message content.

Every successful non-private chat also queues a durable `chat_postprocess` job.
Its immediate best-effort run extracts explicit facts, preferences, emotional
events, promises, and boundaries from the accepted user turn; refreshes the
episodic journal so promises, callbacks, and deliberate unresolved threads are
available to later context; and maintains proactive jobs. Failure leaves the
completed chat intact and the job pending for bounded scheduler retry.

## Retrieval

Implemented:
- filter by user_id and character_id
- filter out `forgotten_at` rows before both recent and vector candidate ranking
- deterministic keyword overlap
- dependency-free 384-dimensional feature embeddings using stable hashing,
  light stemming, character features, and a small set of emotional/conversation
  concept aliases
- PostgreSQL `<=>` nearest-vector candidates combined with a deterministic
  pinned/recent candidate cohort before final hybrid ranking
- hybrid vector similarity plus keyword, recency, importance, confidence,
  emotional weight, pinning, relationship relevance, contradiction, and decay
  scoring
- embedding generation on create, dedupe/merge, edit, and relationship
  milestone creation
- lazy backfill of legacy null embeddings during retrieval
- pg_trgm/ILIKE-friendly text search endpoints

The local feature encoder is deterministic and cheap enough for Codespaces and
the personal ARM target. It improves related-word recall without claiming the
quality of a neural embedding model. The `vector(384)` contract is intentionally
replaceable later; malformed or missing vectors fall back to recomputation and
keyword/state scoring instead of breaking chat.

## Contradictions

Level 2 stores simple contradiction groups and metadata links so the user can
inspect and correct conflicts.

Current behavior:
- positive and negative preference memories for the same normalized object share
  a `contradiction_group`
- conflicting memories are not merged even when their text overlaps
- both sides of a conflict receive inspectable metadata, including
  `contradiction_status`, `contradicts_memory_id`, and backlink fields such as
  `contradicted_by_memory_id`
- newer opposing memories also receive `supersedes_memory_id` metadata so the
  UI/debug layer can distinguish a likely correction from an older stale note
- editing or deleting a conflicting memory refreshes the affected group and
  clears stale contradiction links
- forgetting a conflicting memory removes it from active conflict calculation;
  restoring it rebuilds both sides from current active rows
- resolving a conflicting memory keeps the selected version, removes opposing
  memories in the same group, stamps bounded resolution metadata, and refreshes
  stale links
- retrieval scoring penalizes unresolved conflicts, with an extra penalty for
  older memories that have been contradicted by a newer item

## Memory viewer

The user should be able to inspect what the system remembers.

Display:
- content
- type
- confidence
- importance
- pinned state
- active/forgotten lifecycle state and last forgotten time
- reversible restore plus separate permanent delete
- contradiction metadata
- created_at
- last_recalled_at
- edit/delete/clear controls
- conflict-resolution action for choosing which remembered version to keep
