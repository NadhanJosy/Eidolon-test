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
3. retrieve eligible memory, episodes, living threads, relationship state,
   Shared Scene, and recent messages,
4. project qualitative emotional posture,
5. choose a private response strategy, question policy, target length, rhythm,
   opening, callback posture, and optional initiative,
6. compile the modular prompt and call the configured provider,
7. screen streamed and completed output for hard-boundary or hidden-context
   leakage,
8. persist the completed reply exactly once,
9. update the immediate deterministic relationship effect and queue durable
   post-chat work,
10. selectively analyze the completed turn with a strict structured schema,
    ground every proposed fact/moment against exact source evidence, and commit
    only backend-approved continuity,
11. settle a visible receipt with only changes that actually occurred.

The private response plan is concise generation direction, not a chain-of-thought
transcript. It must never be narrated in chat.

## Prompt assembly

`apps/api/app/services/prompt.py` is the central renderer. Its current version is
`modular_companion_intelligence_v8`.

Modules are ordered from durable instructions toward the immediate request:

1. platform and hard safety boundaries,
2. companion identity,
3. companion voice,
4. relating style and authored limits,
5. qualitative relationship/emotional continuity,
6. current-turn perception,
7. concise user facts,
8. selected semantic memory,
9. selected episodes and callbacks,
10. first-class living promises, plans, rituals, repairs, and follow-ups,
11. private response direction,
12. bounded recent history,
13. current user message.

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
profile prose, living-thread text, credentials, or provider response bodies.
Normal message schemas strip the private metadata; the owner-scoped conversation
Debug endpoint validates it before display.

## Memory layers

### Recent context

A bounded window of eligible messages provides immediate conversational
coherence. Private rows are excluded when a later turn is normal.

### Witnessed continuity

Production post-chat cognition is selective by default. Short, unsafe,
credential-like, private, preference-disabled, or otherwise low-signal turns do
not spend a provider call. Eligible turns send bounded recent context, the
completed exchange, and selected memory IDs through `generate_structured`.

The provider may propose at most three memory candidates, one episode,
allowlisted relationship evidence, and selected memory IDs visibly used in the
reply. It cannot write state. Every proposed memory needs an exact contiguous
quote from the current user line; episode evidence must be exact current-turn
text. Backend grounding rejects invented named/numeric anchors, insufficient
lexical support, polarity reversals, unknown types/signals, weak confidence, low
combined value, sensitive automatic capture, and transient claims. Candidates
score importance, confidence, novelty, future usefulness, stability, and
emotional meaning separately. Prefer no memory over an unsupported one.

Claim keys let repeated evidence reinforce a memory, explicit correction
language supersede it with evidence history, and ambiguous disagreement remain
an inspectable conflict. Grounded entity links connect people, places, dates,
projects, routines, and recurring topics. Retrieval facets enrich deterministic
embedding text without appearing as extra facts. A selected memory's recall/decay state changes only
when the grounded report says the completed reply actually used its ID.

The chat receipt is independent of reply streaming. It begins pending and then
quietly reports remembered/reinforced/corrected memory, a shared moment, or an
actual relationship shift. A malformed/unavailable cognition response degrades
to deterministic extraction and never retracts the completed reply.

### Semantic memory

`memory_items` stores selective facts, preferences, people, events, promises,
themes, shared lore/moments, boundaries, inside jokes, and milestones.

Automatic extraction is evidence-grounded and conservative in production, with
the deterministic extractor retained for mock development, disabled cognition,
and structured-provider degradation. Both paths skip unsafe, blocked, private,
or preference-disabled candidates without copying rejected prose into job/debug
metadata. Explicit opt-out language and sensitive identifiers are automatic
hard stops; deliberate manual storage remains owner-controlled and visibly
classified.

Users can manually add a memory or remember an eligible user/assistant message.
Message capture preserves source linkage, is idempotent where appropriate, and
does not bypass privacy or adult-memory settings.

### Episodic memory

`episodic_journals` records source-linked generated moments and user-authored
notes. A grounded episode requires specific lasting shared-history value,
confidence, exact evidence, and exact source message IDs. Deterministic episodes
can carry bounded signals for repair, anniversaries, inside jokes, milestones,
shared moments/references, callbacks, or intentional open threads.

Manual notes have separate ownership metadata and are not overwritten by
automatic conversation refresh.

Semantic and episodic rows are scoped `general` or `adult`. Adult continuity is
off by default, requires every structural gate plus explicit storage opt-in, and
is considered only in an effective adult turn. Normal chat, relationship
progression, living threads, normal archives, and proactive notes read general
scope only. The user can erase all adult continuity without deleting transcript
messages.

### Living threads

`continuity_threads` separates unfinished intent from retrospective journal
summaries. Automatic capture uses deterministic explicit markers for follow-up
requests, promises, rituals, and grounded future plans; repair posture can label
an explicit follow-up as repair. It rejects ordinary conversation, closures,
credentials, blocked text, private turns, adult turns, and disabled learning.

Retrieval ranks only open owned rows by relevance, conversation locality,
salience, confidence, kind, and recency. Prompt items preserve the user's exact
bounded wording while instructing the model not to invent completion or offline
action. Explicit user closure can resolve a sufficiently matching thread;
companion output cannot. Manual controls always provide resolve, reopen, and
permanent deletion.

## Memory retrieval

Active retrieval combines:

- user and companion ownership
- forgotten-state exclusion
- deterministic keyword overlap
- local normalized 384-dimensional feature embeddings stored in pgvector
- vector-nearest and pinned/recent candidate cohorts
- recency, importance, confidence, future relevance, reinforcement, emotional
  compatibility, entity matches, pinning, retention tier, type value,
  contradiction state, sensitivity, and decay

The feature encoder is deterministic and dependency-free; it is not presented as
a neural semantic model. Missing/invalid legacy vectors are recomputed or fall
back to keyword/state scoring.

Retrieval applies a relevance floor and a five-item reasoning budget so weak
matches do not become a fact dump. Prompt evidence is compact, marks uncertainty
or recurrence, and carries grounded emotional meaning separately from the fact.
The response contract prefers silence over a forced callback and forbids creepy
precision or mentioning memory merely to demonstrate recall.

Forgotten memory remains visible but cannot enter retrieval, prompts, recall
timestamps, or active conflicts. Restore/relearning revives the row. Permanent
deletion is a separate action.

Conflicting active memories retain uncertainty. Resolution keeps the selected
side active and supersedes opposing rows while preserving correction history.
Generated callbacks or shared
history claims must be supported by selected memory, episodes, or recent
conversation.

## Relationship and emotional continuity

One relationship row per user-companion pair contains bounded metrics, mood,
conflict/repair state, emotional posture, evidence counts, timeline entries, and
one-time milestones.

Immediate updates are deterministic. A grounded post-turn report may add small
bounded deltas from allowlisted interaction evidence such as gratitude,
vulnerability, repair, play, support, or a shared ritual; the model never sets a
score. Familiarity usually grows with interaction; warmth, trust, tension, and
repair respond gradually. Elapsed time decays volatile state toward safe
baselines.

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
- `memory_maintenance`
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

Each eligible post-chat run ensures one future memory-maintenance row per
companion. Maintenance consolidates exact non-conflicting claims, reinforces the
keeper, backfills conservative entity links, and applies lifecycle decay.
Boundaries, milestones, pins, and sufficiently repeated high-confidence facts
are protected; transient low-value detail fades faster. No private prose is
copied into job results.

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
- whether a thinking-of-you note has a non-manual, general-scope shared moment
- a per-thread follow-up cooldown for living threads

Careful/repair posture suppresses pressure-prone milestone and delayed follow-up
notes. Ordinary check-ins become more spacious. A note must not claim awareness
or activity while offline.

After all guards pass, the provider receives a minimal SFW prompt containing
screened authored fragments and qualitative posture, not raw history, private
turns, relationship scores, adult detail, or debug state. Malformed, oversized,
blocked, hidden-context, or unavailable provider output falls back to deterministic
SFW copy. Only safe provenance labels are stored.

An unresolved-thread nudge binds to an exact eligible living thread when one is
queued. Delivery records its cooldown timestamp so repeated jobs cannot keep
nudging the same promise. Legacy journal callbacks remain a compatibility
fallback only for jobs without a bound living-thread ID.

Thinking-of-you notes likewise require an exact generated shared-moment anchor;
generic availability is not sufficient. Contextual fallback copy preserves that
anchor while still becoming more spacious under careful/repair posture.

## Testing invariants

Automated coverage should preserve:

- the same orchestration across complete, SSE, reroll, retry, and edit paths
- exactly-once assistant persistence and no partial assistant on failure
- prompt order, budgets, privacy exclusion, and hidden-state non-disclosure
- natural mock text without provider/prompt/score narration
- selective memory, vector/entity fallback, contradiction uncertainty,
  reinforcement, supersession, consolidation, tier-aware decay, and forgetting
- exact-evidence grounding, polarity rejection, claim correction, provider
  degradation, and truthful continuity receipts
- general/adult scope isolation, gated manual adult writes, and scoped erasure
- opt-out/sensitivity rejection, evidence history, entity timelines, category
  erasure, retention modes, and prompt relevance limits
- explicit living-thread extraction, owner isolation, lifecycle, source cleanup,
  prompt selection, privacy exclusion, and proactive cooldown
- gradual relationship progression and reversible source effects
- job locking, retry caps, local-time deferral, cooldown, privacy, and anti-spam
- earned proactive anchors, safe fallback, and relationship-sensitive suppression
- owner-scoped, bounded Debug context without raw prompt/state prose
