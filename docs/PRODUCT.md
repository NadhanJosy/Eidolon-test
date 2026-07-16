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
- Unfinished plans and promises remain visible, grounded in explicit user
  language, and under user control.
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

Eligible completed turns receive a selective, bounded continuity pass after the
reply is safely persisted. Provider-proposed facts and moments are accepted only
when their evidence is present in the source turn; the backend owns claim
identity, confidence thresholds, correction, conflict, scope, and lifecycle.
Chat shows a quiet per-turn continuity receipt while that work settles and only
names changes that were actually committed.

### Living continuity threads

Eidolon carries explicit future intent as first-class living threads rather
than burying it in journal prose. Threads cover plans, promises, rituals,
repair, and requests to follow up. Conservative deterministic extraction
requires explicit language; ordinary conversation is not promoted into an
obligation.

Open threads can influence a relevant later reply and, when all proactive
guards pass, a restrained follow-up subject to a per-thread cooldown. Users can
inspect open and settled threads from chat and the Relationship view, add one
deliberately, return to it, close or reopen it, and permanently delete it.
Resolution is never inferred from companion prose. Source-message edits/deletes
remove stale automatic threads.

Private or adult turns, blocked content, credentials, and preference-disabled
learning never create automatic living threads. Conversation-private threads
also reject conversation-linked manual creation.

### Relationship continuity

Each user-companion pair has one relationship row containing bounded trust,
intimacy, warmth, tension, familiarity, attachment, mood, conflict state, repair
state, and qualitative emotional continuity.

Relationship changes are deterministic and bounded. A grounded post-turn pass
may label supported interaction evidence, but it cannot set scores directly.
Relationship state can influence tone and pacing but must not create
manipulative dependency, jealousy, punishment, or pressure to return.

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

Thinking-of-you notes require an eligible general-scope shared moment; open-thread
and milestone notes require their exact durable anchor. Generic availability is
not enough reason to contact the user.

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
- human continuity receipts that settle independently of reply streaming
- understandable empty, loading, retry, and failure states
- human relationship/privacy language in primary UI
- provider, database, prompt, and scheduler details confined to Debug
- reduced-motion support and no animation-dependent interaction
- no authenticated offline cache or service worker

## Privacy semantics

A private conversation still persists visible messages for its owner, but new
turns do not create memory, living threads, journals, relationship, or proactive
side effects. One-turn privacy applies the same rule to one user/assistant
exchange.

Private messages remain visible in owned history, literal search, and export.
They are excluded from later normal prompt history and must not update recall
timestamps. Returning a thread to normal does not make prior private prose
available to future cognition.

## Adult mode

Adult mode is eligible only when the user has confirmed the age gate, the
companion has an explicit age of at least 18, the companion permits adult mode,
the relationship is not in a blocking repair posture, and all hard content
boundaries pass. A missing, stale, or failed readiness check resolves to SFW.

Adult continuity is off by default. When explicitly enabled, eligible adult
memories and moments use a separate scope that normal chat, normal archives,
relationship progression, living threads, and proactive notes cannot read.
Settings reports the separate item counts and can erase that adult-only
continuity without deleting visible conversation messages. Private turns never
enter either scope.

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
conversation, inspect and control memory/relationship/living-thread data, use
privacy modes, and export or erase owned data without exposing secrets or
another user's state.

Engineering acceptance and release checks are defined in
[OPERATIONS.md](OPERATIONS.md).
