# Product

## Vision

Eidolon is a private, text-only AI companion that feels continuous through
durable memory, a stable authored persona, evolving relationship state, and
occasional scheduled text presence.

Text-only is a product choice. The experience should gain depth from writing and
state rather than avatars, voice, video, or heavy visual effects.

## Product principles

- The companion has a stable identity, voice, boundaries, and relationship path.
- The backend owns facts and decisions; the model supplies the next piece of
  prose.
- Memory is selective, inspectable, correctable, and removable.
- Relationship changes are gradual, bounded, and supported by real interaction
  evidence.
- Privacy controls affect future cognition, not merely the appearance of a
  message.
- Proactive notes are optional, restrained, and never pretend the companion was
  observing the user offline.
- Operational and prompt internals stay in authenticated Debug surfaces rather
  than leaking into the conversation.
- Safety gates remain structural even when adult mode is requested.

## Current product scope

### Accounts and sessions

Users can register, sign in, refresh a session, edit their profile and age-gate
state, sign out, export their data, and permanently erase their account.

Authentication uses short-lived JWT access tokens held in browser memory and
rotating opaque refresh tokens stored as hashes in PostgreSQL. The browser
receives the refresh token only through an HttpOnly cookie.

### Companions

Users can create and edit multiple companions. An authored profile covers:

- identity, worldview, temperament, values, and flaws
- speech rhythm, humour, affection, conflict style, and terms of address
- greeting, setting, shared scenario, interests, backstory, and relationship path
- consent and hard-limit posture
- memory and privacy preferences
- proactive-message preferences, local times, quiet hours, and cooldown
- explicit age, adult eligibility, and bounded intensity settings

The API validates and canonicalizes the complete profile. The frontend is not a
security boundary.

### Conversations

Each companion can have multiple threads. A thread supports:

- persisted user, assistant, and controlled system messages
- incremental Server-Sent Events streaming
- stop and exact-turn retry after an incomplete response
- reroll of a companion response
- edit or delete of the latest user turn with continuity cleanup
- deletion of companion responses, whole chat history, or the thread
- title editing, literal message search, read state, and unread counts
- a normal or private thread mode
- an optional thread-specific Shared Scene
- one-turn privacy without changing the whole thread

Thread and companion navigation must reject stale asynchronous results so a late
request cannot overwrite a newer selection or session.

### Memory and journals

Memory has three layers:

1. bounded recent conversation context,
2. durable semantic `memory_items`,
3. episodic journals for shared moments, callbacks, promises, milestones, and
   unresolved threads.

Users can add, edit, pin, forget, restore, resolve conflicts, permanently delete,
or clear memories. They can explicitly remember an eligible message. Forgotten
memory remains visible to its owner but is excluded from retrieval and prompts
until restored.

Manual journal notes remain user-owned. Generated journal summaries can be
rebuilt when their source conversation changes.

### Relationship continuity

Each user-companion pair has one relationship row containing bounded trust,
intimacy, warmth, tension, familiarity, attachment, mood, conflict state, repair
state, and qualitative emotional continuity.

The relationship engine is deterministic. It can influence tone and pacing but
must not create manipulative dependency, jealousy, punishment, or pressure to
return.

### Scheduled presence

PostgreSQL-backed jobs can extract memory, decay relationship state, refresh
continuity, and create optional proactive notes. Supported note categories
include quiet check-ins, morning or goodnight notes, a restrained
thinking-of-you note, a milestone note, an intentional open-thread follow-up,
and a delayed follow-up.

Quiet hours, local time, cooldown, privacy, staleness, preferences, and
relationship-repair posture are checked before delivery. These messages are
best-effort on a scale-to-zero Cloud Run deployment; they are not guaranteed at
an exact wall-clock instant.

### Debug and data control

Authenticated Debug views expose bounded operational state for the current
owner, including provider readiness, scheduler status, selected context IDs and
types, recent safe diagnostic events, memory decisions, relationship state, and
jobs.

They must not expose raw prompts, secrets, provider response bodies, stack
traces, or another user's data.

## Experience requirements

- lightweight, responsive, mobile-first, and keyboard usable
- readable at narrow phone and desktop widths without document-level overflow
- text-first, calm, and non-corporate
- visible but restrained composing and streaming states
- understandable empty, loading, retry, and failure states
- human relationship/privacy language in primary UI
- provider, database, prompt, and scheduler details confined to Debug
- reduced-motion support and no animation-dependent interaction
- no authenticated offline cache or service worker

## Privacy semantics

A private conversation still persists visible messages for its owner, but new
turns do not create memory, journal, relationship, or proactive side effects.
One-turn privacy applies the same rule to one user/assistant exchange.

Private messages remain visible in owned history, literal search, and export.
They are excluded from later normal prompt history and must not update recall
timestamps. Returning a thread to normal does not make prior private prose
available to future cognition.

## Adult mode

Adult mode is eligible only when the user has confirmed the age gate, the
companion has an explicit age of at least 18, the companion permits adult mode,
the relationship is not in a blocking repair posture, and all hard content
boundaries pass. A missing, stale, or failed readiness check resolves to SFW.

See [SAFETY.md](SAFETY.md) for the complete non-negotiable boundary contract.

## Non-goals

- voice, audio, images, avatars, video, AR, or Live2D
- native mobile applications
- fine-tuning
- browser-side or Chromebook-local inference
- social feeds, public character marketplaces, or multi-user collaboration
- manipulative dependency mechanics
- distributed queues, Kubernetes, or unnecessary service decomposition
- a full offline-capable PWA containing private cached conversations

## Product acceptance

The deployed MVP is healthy when a user can authenticate, open or create a
companion and thread, receive a streamed response, reload into the persisted
conversation, inspect and control memory/relationship data, use privacy modes,
and export or erase owned data without exposing secrets or another user's state.

Engineering acceptance and release checks are defined in
[OPERATIONS.md](OPERATIONS.md).
