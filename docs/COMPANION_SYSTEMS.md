# Companion Systems

## Rule

The companion pipeline turns backend-owned state into prose. The model is never
the source of truth for identity, memory, relationship progression, privacy,
safety, or scheduled work.

## Turn orchestration

Every completed chat, streamed chat, reroll, and latest-turn edit follows the
same high-level path:

1. validate owner, thread, message, privacy, content mode, and hard boundaries,
2. infer bounded intent, tone, subtext, time gap, and unresolved context,
3. retrieve eligible memory, episodes, relationship state, Shared Scene, and
   recent messages,
4. project qualitative emotional posture,
5. choose a private response strategy, question policy, target length, rhythm,
   opening, callback posture, and optional initiative,
6. compile the modular prompt and call the configured provider,
7. screen streamed and completed output for hard-boundary or hidden-context
   leakage,
8. persist the completed reply exactly once,
9. update deterministic relationship state and queue post-chat work.

The private response plan is concise generation direction, not a chain-of-thought
transcript. It must never be narrated in chat.

## Prompt assembly

`apps/api/app/services/prompt.py` is the central renderer. Its current version is
`modular_companion_intelligence_v7`.

Modules are ordered from durable instructions toward the immediate request:

1. platform and hard safety boundaries,
2. companion identity,
3. companion voice,
4. relating style and authored limits,
5. qualitative relationship/emotional continuity,
6. current-turn perception,
7. concise user facts,
8. selected semantic memory,
9. selected episodes, promises, callbacks, and open threads,
10. private response direction,
11. bounded recent history,
12. current user message.

The current message stays last. Context-budget trimming removes older or
lower-priority context before safety, identity, or the current turn. Prompt
assembly must not include secrets, raw JSON dumps, embeddings, relationship
meters, diagnostics, or private messages in a later normal turn.

Recognized system events are converted from trusted metadata into fixed
conversation-event summaries. Stored system prose is never accepted as a prompt
instruction.

## Character soul

`soul_json` contains the typed authored identity and relating style. Legacy
description/personality/speech fields remain migration fallbacks.

The renderer compiles soul fields into natural language rather than exposing the
JSON structure. A companion may develop familiarity or a configured relationship
path, but it must not force romance, assume unearned intimacy, or contradict
authored limits.

## Context manifests

Each real generation can attach a private manifest to its triggering user turn.
The allowlisted manifest records IDs, types, privacy labels, categorical
relationship/safety posture, provider, generation kind, prompt version/size, and
bounded response-plan categories.

It does not record prompt text, message prose, memory content, journal summaries,
profile prose, credentials, or provider response bodies. Normal message schemas
strip the private metadata; the owner-scoped conversation Debug endpoint validates
it before display.

## Memory layers

### Recent context

A bounded window of eligible messages provides immediate conversational
coherence. Private rows are excluded when a later turn is normal.

### Semantic memory

`memory_items` stores selective facts, preferences, people, events, promises,
themes, shared lore/moments, boundaries, inside jokes, and milestones.

Automatic extraction is deterministic and conservative. It accepts useful
stable statements and emits bounded decision labels. It skips short/no-trigger,
unsafe, blocked, private, or preference-disabled candidates without copying
rejected prose into job/debug metadata.

Users can manually add a memory or remember an eligible user/assistant message.
Message capture preserves source linkage, is idempotent where appropriate, and
does not bypass privacy or adult-memory settings.

### Episodic memory

`episodic_journals` records generated episode summaries and user-authored notes.
Generated episodes can carry bounded signals for repair, anniversaries, inside
jokes, milestones, shared moments/references, callbacks, or intentional open
threads. Adult detail is redacted from durable episode prose.

Manual notes have separate ownership metadata and are not overwritten by
automatic conversation refresh.

## Memory retrieval

Active retrieval combines:

- user and companion ownership
- forgotten-state exclusion
- deterministic keyword overlap
- local normalized 384-dimensional feature embeddings stored in pgvector
- vector-nearest and pinned/recent candidate cohorts
- recency, importance, confidence, emotional weight, pinning, type value,
  contradiction state, and decay

The feature encoder is deterministic and dependency-free; it is not presented as
a neural semantic model. Missing/invalid legacy vectors are recomputed or fall
back to keyword/state scoring.

Forgotten memory remains visible but cannot enter retrieval, prompts, recall
timestamps, or active conflicts. Restore/relearning revives the row. Permanent
deletion is a separate action.

Conflicting active memories retain uncertainty. Resolution keeps the selected
side and removes opposing rows in the group. Generated callbacks or shared
history claims must be supported by selected memory, episodes, or recent
conversation.

## Relationship and emotional continuity

One relationship row per user-companion pair contains bounded metrics, mood,
conflict/repair state, emotional posture, evidence counts, timeline entries, and
one-time milestones.

Updates are deterministic. Familiarity usually grows with interaction; warmth,
trust, tension, and repair respond gradually to supported signals. Elapsed time
decays volatile state toward safe baselines.

Prompt assembly sees behavioural qualitative wording, never raw meters. A single
apology can begin repair but cannot erase accumulated tension in one turn.
Relationship state must never produce guilt, punishment, jealousy, threats,
fabricated crisis, or pressure to return.

Source turns may carry exact bounded relationship effects. Latest-turn edit or
deletion reverses those recorded effects and recalculates from the replacement
turn. Legacy effects are not guessed.

## Scheduled jobs

APScheduler periodically calls the PostgreSQL worker. Supported work includes:

- `maintenance_noop`
- `memory_extract`
- `chat_postprocess`
- `relationship_decay`
- `proactive_inactivity_check`
- `proactive_morning_check`
- `proactive_goodnight_check`
- `proactive_thinking_of_you`
- `proactive_milestone_check`
- `proactive_unresolved_thread_nudge`
- `proactive_delayed_double_text`
- `proactive_message_create`

Workers claim due rows with database locking. A transaction advisory lock also
prevents overlapping batches. Transient failures return to pending with capped
backoff; invalid/unsupported jobs fail terminally. Every transition releases
worker lock fields, and stored errors use safe bounded text.

## Proactive notes

Before queueing and delivery, proactive work checks:

- companion and per-type preferences
- snooze state
- thread/message privacy
- whether the user has returned since the job was queued
- per-conversation cooldown
- configured IANA timezone, target local time, and quiet hours
- current relationship posture
- whether the referenced milestone/open thread is still valid

Careful/repair posture suppresses pressure-prone milestone and delayed follow-up
notes. Ordinary check-ins become more spacious. A note must not claim awareness
or activity while offline.

After all guards pass, the provider receives a minimal SFW prompt containing
screened authored fragments and qualitative posture, not raw history, private
turns, relationship scores, adult detail, or debug state. Malformed, oversized,
blocked, hidden-context, or unavailable provider output falls back to deterministic
SFW copy. Only safe provenance labels are stored.

## Testing invariants

Automated coverage should preserve:

- the same orchestration across complete, SSE, reroll, retry, and edit paths
- exactly-once assistant persistence and no partial assistant on failure
- prompt order, budgets, privacy exclusion, and hidden-state non-disclosure
- natural mock text without provider/prompt/score narration
- selective memory, vector fallback, contradiction uncertainty, and forgetting
- gradual relationship progression and reversible source effects
- job locking, retry caps, local-time deferral, cooldown, privacy, and anti-spam
- safe proactive fallback and relationship-sensitive suppression
- owner-scoped, bounded Debug context without raw prompt/state prose
