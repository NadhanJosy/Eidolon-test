# Product Requirements

## MVP user stories

### Chat

As a user, I can open the app and chat with a character.

Acceptance criteria:
- messages persist after refresh
- assistant replies are streamed or visibly loading
- errors are readable
- no heavy UI dependencies

### Character persona

As a user, I can chat with a character that has a stable name, style, and boundaries.

Acceptance criteria:
- character profile is stored in the database
- prompt assembly includes character profile
- default character exists for development
- character stays SFW unless adult mode gates pass

### Memory

As a user, I want the character to remember important facts.

Acceptance criteria:
- memory_items can be created
- relevant memories can be retrieved
- prompt assembly includes selected memories
- memory viewer/debug panel shows stored memories
- system does not store every message as memory

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
- no push notifications required for MVP

### Auth

As a user, I can protect my app with login.

Acceptance criteria:
- user can register/login
- protected endpoints require auth
- users cannot access other users' data
- password is hashed
- no external auth vendor

### Adult mode structure

As an adult user, I can enable adult mode only when structural safety gates pass.

Acceptance criteria:
- age gate required
- character explicit age required and must be >= 18
- adult mode unavailable if age missing or ambiguous
- mode injected into prompt structurally
- no explicit examples in code/tests

### Data control

As a user, I can inspect/export/wipe data.

Acceptance criteria:
- export endpoint excludes secrets/password hashes
- user only exports own data
- wipe/export APIs are protected

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
