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
- Operational and prompt internals stay out of the consumer experience and are
  available only through authenticated, owner-scoped diagnostic routes.
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
- proactive frequency/category controls, local time, quiet hours, pause, caps,
  cooldown, and muted feedback categories
- explicit age, adult eligibility, and bounded intensity settings

The API validates and canonicalizes the complete profile. The frontend is not a
security boundary.

First-run companion creation is a progressive meeting flow: presence,
personality, relationship expectations, and an opening line appear before the
deeper optional profile fields. An unfinished draft may be restored only within
the same browser tab; the persisted companion remains the backend's source of
truth.

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

Chat safely renders a restrained subset of Markdown, including headings, lists,
quotes, tables, links, and copyable fenced code. It restores a numeric scroll
position per thread, opens unread replies at a visible boundary, and follows a
stream only while the reader remains near the latest message. Browser offline
status keeps the unsent draft editable but prevents a misleading send attempt.

Thread and companion navigation must reject stale asynchronous results so a late
request cannot overwrite a newer selection or session.

Replies should read as specific dialogue from the authored companion: concise
when the moment is light, emotionally precise without therapy clichés, capable
of mixed feelings, humour, disagreement, and relevant initiative, and willing
to state uncertainty instead of inventing facts or shared history. The product
does not require every turn to contain reassurance, advice, a memory callback,
or a follow-up question.

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

Semantic memory has explicit lifecycle state. Repeated evidence reinforces a
claim; direct corrections supersede the older version without erasing its
private history; uncertain disagreement stays unresolved. Retention tiers
protect pinned memories, boundaries, milestones, and well-reinforced patterns
while allowing low-value transient detail to soften through scheduled review.
Ordinary retention can be minimal, balanced, or long-lived per companion.

People, places, dates, routines, projects, and topics can be linked to memory
items for entity-focused search and chronological recall. The archive supports
text search, lifecycle/provenance cues, reversible forgetting, permanent item
and category erasure, and separately exported evidence/entity history. Explicit
“do not remember” language prevents automatic capture. Contact/address and
similarly sensitive identifiers require deliberate manual storage and receive a
sensitive marker; they can enter a reply only when the user explicitly asks
about their matching identifier category or repeats an exact email/phone value.

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

Each user-companion pair has one bounded relationship read model covering trust,
emotional safety, warmth, reliability, reciprocity, tension, repair, boundary
respect, familiarity, and shared-history depth. A first-class private event
ledger records only meaningful evidence such as support, vulnerability,
follow-through, conflict, apology, repair, boundaries, humour, rituals, returns,
and linked milestones. Routine message volume does not earn closeness.

The backend assigns confidence, significance, and gradual reversible effects;
structured cognition may propose exact-quote evidence but cannot set state.
Elapsed time softens volatile tension without erasing earned trust or reliability.
One apology begins repair rather than instantly restoring it.

Before generation, the backend builds a compact qualitative plan containing
current posture, recent supported change, unresolved tension, active boundaries,
earned familiarity, and safe initiative. This can adjust tone, pacing, humour,
callbacks, disagreement, reassurance, vulnerability, and proactive presence.
Explicit limits always override those behaviours. Adult boundary events use an
isolated adult scope and never advance the normal relationship.

The Relationship view explains facets, meaningful moments, and bounded
owner-only evidence excerpts in human language, without a bond score or meter
dashboard. Owners can correct classifications or remove events,
reset one or every dimension of the current interpretation while keeping
history, or restart relationship history while preserving active boundaries.

Relationship behaviour must never create dependency, jealousy, exclusivity,
punishment, scarcity, engagement rewards, fabricated crisis, obligation, or
pressure to return.

### Scheduled presence

PostgreSQL-backed jobs can extract and maintain memory, decay relationship
state, refresh continuity, and deliver optional proactive notes. Memory
maintenance consolidates exact duplicate claims and applies tier-aware decay;
its payload records counts rather than private prose.

Proactive presence begins with one durable, evidence-backed candidate model for
explicit follow-ups, user reminders, callbacks, milestones, routines,
contextual suggestions, queued thoughts, and returns after an absence. Each
candidate records its categorical source and rationale, confidence, urgency,
expiry, sensitivity, delivery constraints, score factors, and lifecycle. A
timer can make a supported candidate eligible, but elapsed time by itself never
creates a note.

The send decision runs before prose generation. It combines recency,
importance, emotional weight, unresolved intent, explicit preferences, routine
fit, local time, relationship posture, and recent delivery frequency. Quiet
hours, pause, cooldown, daily caps, expiry, stale/deleted sources, a newer user
turn, privacy, sensitive automatic anchors, and safety may defer or suppress
the candidate. A sensitive explicit reminder remains eligible only for the
authenticated in-app inbox.

Delivered notes appear in a dedicated in-app inbox with unread/opened state,
human origin labels, return-to-chat, dismiss, “not relevant,” and “mute similar”
actions. Reminders requested by the user are distinct from companion-initiated
notes. External/browser notification delivery is not implemented; the stored
notification preview is separately generated and contains only “New companion
note,” never profile, conversation, memory, adult, or private detail.

Delivery is best-effort on a scale-to-zero Cloud Run deployment and is not
guaranteed at an exact wall-clock instant. The product never claims the
companion was awake, watching, waiting, thinking, or taking actions outside an
active application process.

### Diagnostics and data control

Authenticated diagnostic routes expose bounded operational state for the
current owner, including provider readiness, scheduler status, selected context
IDs and types, recent safe diagnostic events, memory decisions, relationship
state, and jobs. The normal consumer client does not fetch or present these
diagnostic payloads. Export includes proactive candidates and lifecycle events;
erasure controls remain in Settings.

They must not expose raw prompts, secrets, provider response bodies, stack
traces, or another user's data.

## Experience requirements

- lightweight, responsive, mobile-first, and keyboard usable
- readable at narrow phone and desktop widths without document-level overflow
- text-first, intimate, calm, and non-corporate, with a reusable dark
  paper-and-ember visual language rather than a generic dashboard treatment
- progressive onboarding that asks for essential choices first and keeps an
  unfinished draft in the current tab
- chat-centred navigation with stable per-view and per-thread scroll behaviour
- visible but restrained composing and streaming states
- safe rich-text replies, copyable code, and touch targets sized for mobile use
- human continuity receipts that settle independently of reply streaming
- a companion-note inbox with unread/origin state, return-to-chat, and immediate
  dismiss, relevance, mute, pause, and opt-out controls
- understandable empty, switching, offline, loading, retry, and failure states
- deliberate confirmation for irreversible actions and explicit typed phrases
  for bulk or account erasure
- human relationship/privacy language in primary UI
- provider, database, prompt, and scheduler details confined to authenticated
  diagnostics rather than the normal client
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
Explicit boundaries stated in an adult turn use the same isolated scope even
when optional adult memory storage is off, because privacy preferences cannot
disable safety handling.
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
