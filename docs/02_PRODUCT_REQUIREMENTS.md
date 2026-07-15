# Product Requirements

## MVP user stories

### Chat

As a user, I can open the app and chat with a character.

Acceptance criteria:
- messages persist after refresh
- the default Groq conversation path streams real provider tokens through the
  backend without exposing its key to the browser
- assistant replies are streamed incrementally with a subtle pre-token state
- a stopped or failed reply preserves the accepted user line, stores no partial
  companion line, and offers an exact-turn retry
- completed replies store provider/model/timing/usage telemetry and persist once
- mock streaming has a short composing pause and natural chunk cadence
- switching threads cancels the old visible stream without cross-thread message bleed
- user lines show sent/read posture from actual reply order
- companion replies and presence notes remain unread per thread until visibly opened
- meaningful backend-owned state transitions appear as subtle system event cards
- mobile opens directly into the active conversation with explicit thread and
  companion-state workspace tabs
- primary chrome uses human relationship/privacy summaries and keeps provider,
  database, prompt, and job status inside authenticated debug
- errors are readable, and recent generation failures remain inspectable in
  authenticated Debug without storing prompt, message, exception, URL, or stack
  trace content
- no heavy UI dependencies
- development mock replies use persona, recent-thread, memory, relationship, and
  current-message cues as natural dialogue without echoing the full message,
  narrating a response strategy, or exposing provider and prompt internals
- each thread can use a bounded custom shared scene or return to the character's
  default setting without changing sibling threads or rewriting the persona

### Character persona

As a user, I can chat with a character that has a stable name, style, and boundaries.

Acceptance criteria:
- character profile is stored in the database
- prompt assembly includes character profile
- a staged companion builder captures identity, relationship type, inner life,
  voice, world, greeting, boundaries, adult eligibility, intensity, memory,
  privacy, and proactive presence preferences before creation
- invalid stages retain their draft and focus the first rejected field
- a complete authored SFW default character exists for development and first use
- character stays SFW unless adult mode gates pass

### Memory

As a user, I want the character to remember important facts.

Acceptance criteria:
- memory_items can be created
- relevant memories can be retrieved
- prompt assembly includes selected memories
- memory viewer/debug panel shows stored memories
- system does not store every message as memory
- forgetting is reversible and distinct from permanent deletion; forgotten
  memories remain owner-visible but cannot enter retrieval, prompts, or active
  contradiction state until restored
- user can explicitly keep an owned user or companion line without bypassing
  private-thread or adult-memory rules
- episodic continuity distinguishes anniversaries, inside jokes, shared
  moments, milestones, callbacks, repair arcs, and open threads
- personal journal notes remain user-owned, survive later automatic episode
  refreshes, and can be corrected or deleted without mutating transcript-owned
  summaries

### Relationship state

As a user, I want the relationship to evolve over time.

Acceptance criteria:
- relationship state exists per user-character pair
- chat updates familiarity at minimum
- state variables are bounded
- prompt assembly includes relationship state
- debug panel shows state values

### Proactive text

As a user, I want the character to be able to send occasional queued text messages.

Acceptance criteria:
- scheduled_jobs table exists
- inactive conversation can create one queued proactive message
- duplicate spam is prevented
- proactive messages appear in normal chat history
- unread proactive notes surface in the thread rail while the app is open
- proactive jobs can represent inactivity, morning, goodnight, thinking-of-you,
  milestone, unresolved-thread nudges, and delayed double-texts with SFW text
- morning and goodnight notes target user-configured local times, while all
  automatic notes respect a configurable quiet period
- the personal runtime processes due jobs without a hidden manual enablement step
- unexpected worker failures retry with bounded backoff and cannot loop forever
- no push notifications required for MVP

### Auth

As a user, I can protect my app with login.

Acceptance criteria:
- user can register/login
- protected endpoints require auth
- users cannot access other users' data
- password is hashed
- no external auth vendor
- the entry experience is brand-first and responsive, with sign-in and register
  controls that remain usable without a generic dashboard card
- changing auth mode clears password and stale status state; successful auth and
  logout remove the password from client state
- registration canonicalizes and validates email identity, normalizes optional
  display names, and requires a bounded passphrase of at least 12 characters
- unknown accounts, incorrect passwords, and malformed stored hashes share the
  same generic login failure without skipping password verification work

### Adult mode structure

As an adult user, I can enable adult mode only when structural safety gates pass.

Acceptance criteria:
- age gate required
- character explicit age required and must be >= 18
- adult mode unavailable if age missing or ambiguous
- mode injected into prompt structurally
- primary-shell mode reflects only the effective, character-bound gate result;
  stale, missing, failed, or newly blocked readiness always displays and sends SFW
- character switches reset requested mode, while same-character thread switches
  may retain Adult only while the current gates remain open
- no explicit examples in code/tests

### Data control

As a user, I can inspect/export/wipe data.

Acceptance criteria:
- export endpoint excludes secrets/password hashes
- user only exports own data
- export preserves owned memory, journal, relationship, privacy, and proactive
  continuity metadata with lifecycle timestamps
- wipe/export APIs are protected
- private conversations can pause memory, journal, relationship, and proactive side effects
  while preserving the visible thread
- a standard thread can make one exchange private without changing the thread-wide mode;
  that exchange remains visible and searchable but cannot shape later standard continuity

## MVP non-goals

Do not implement:

- voice/audio
- images/video
- avatars
- native mobile
- paid APIs
- multi-user scale optimizations
- complex recommender systems
- full moderation pipeline
- model fine-tuning
- distributed queues

## UX requirements

- dark simple chat UI
- responsive mobile-friendly layout
- text-first interface
- message timestamps
- typing/streaming indicator
- basic character panel
- memory/debug pages hidden behind auth
- non-corporate error messages

## Performance requirements

- frontend must be lightweight
- no heavy animation libraries
- no local model execution in browser
- backend must work on a small VM
- memory retrieval must be cheap
- live chat prompt must be compact
- background tasks should be optional and safe
