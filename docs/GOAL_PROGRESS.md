# Goal Progress

Codex should update this file during `/goal` runs.

## Companion intelligence overhaul - 2026-07-15

- Replaced the monolithic turn path with a six-stage backend orchestration:
  deterministic perception, continuity retrieval, safety and qualitative mood,
  private strategy planning, modular prompt generation, and completed-response
  evaluation. Plans remain bounded internal direction and are never chat rows.
- Added migration `0009_companion_intelligence` with validated editable
  `characters.soul_json` and private `relationship_states.emotional_state_json`.
  Existing characters receive safe soul fallbacks; relationship emotion is
  bounded, decays over time, affects wording qualitatively, and recovers from
  conflict gradually rather than resetting after one apology.
- Compiled identity, worldview, temperament, humour, speech rhythm, affection and
  conflict styles, values, insecurities, habits, initiative, boundaries, emoji
  posture, terms of address, and relationship path into separate prompt modules.
  The character builder and editor expose these fields without sending raw JSON
  or emotional/relationship meters to the model.
- Added response strategies for comfort, celebration, teasing, challenge, advice,
  listening, flirtation, reminiscence, apology, repair, disclosure, redirection,
  and sharing the moment. Planning controls question need, response length,
  rhythm, openings, callbacks, and contextual initiative while explicitly
  avoiding interrogation, canned reassurance, instant intimacy, and absence
  guilt.
- Expanded durable memory classification with facts, people, promises, themes,
  shared lore, and boundaries; ranking now includes relationship value alongside
  relevance, recency, importance, confidence, pinning, emotion, contradiction,
  and decay. Ranked results are deduplicated, active conflicts retain uncertainty,
  and the response checker rejects unsupported shared-history inventions.
- Added behavioral evidence for gradual familiarity and trust, character-specific
  initiative hooks compatible with existing proactive scheduling, privacy-safe
  orchestration categories in Debug, and seven-dimension companion evaluation
  covering consistency, memory precision, emotional fit, naturalness, repetition,
  initiative, and safety.
- Preserved the existing Groq provider and exact SSE event contract. Stream chunks
  still pass directly from `provider.stream`; hard-boundary/private-plan checks
  run immediately before emission without buffering the generated response.
- Added 26 focused migration and multi-turn regressions for first meetings,
  banter, support, celebration, advice, conflict, apology, long absence,
  relationship progression, typed soul editing, question variation, repetition,
  contradiction uncertainty, callbacks, invented memories, private-plan
  non-disclosure, and evaluation scoring.

Validation:

- `cd apps/api && pip install -e ".[dev]" && alembic upgrade head` - passed at
  `0009_companion_intelligence`.
- `cd apps/api && pytest -q` - passed: 220 tests; 1 opt-in live test skipped.
- `cd apps/api && ruff format . && ruff check .` - passed; 84 files unchanged.
- `cd apps/web && npm install && npm run lint && npm run build` - passed with no
  audit vulnerabilities and a successful optimized Next.js production build.
- `git diff --check` and the forbidden-dependency manifest scan - passed.

## Real model integration - 2026-07-15

Status: complete and validated. This checkpoint supersedes the older mock-first
provider notes and limitations retained later in this historical log.

Implemented:
- Made GroqCloud the default real provider with backend-only
  `GROQ_API_KEY`, the requested `llama-3.3-70b-versatile` model, validated
  temperature/output/timeout/context/retry settings, typed completed and stream
  events, and explicit development/test-only mock mode.
- Added a replaceable provider interface, Ollama compatibility, configurable
  provider or model fallback, pre-token-only fallback behavior, bounded
  exponential retries for transient rate/server/transport failures, clean
  timeout/auth/model/context/quota/refusal/empty/malformed classifications, and
  configured/reachable/degraded readiness without credential disclosure.
- Connected Groq's chat-completions stream through FastAPI SSE to the existing
  browser flow. The UI now renders an immediate transient user line, composing
  and incremental-token states, Stop, alternate-response, exact-turn retry, and
  provider disclosure while synchronously suppressing duplicate sends.
- Made accepted user turns durable before inference, persist only one completed
  assistant row linked to its source user row, discard every partial reply on
  cancellation/failure, reconstruct retry state after refresh, and reject
  concurrent or repeated completion of the same retryable turn.
- Rebuilt the provider prompt in the required eight-section order with hard
  safety first and current message last. It applies a configurable budget,
  deduplicates memory text, ranks memory and episodes for relevance, recency,
  importance, and emotional weight, uses qualitative relationship guidance,
  and omits raw scores, prompt telemetry, and storage terminology.
- Added privacy-safe generation telemetry for actual provider/model, total and
  first-token latency, input/output/total tokens, finish reason, and bounded
  failure type. Full prompts, messages, provider exception bodies, and keys do
  not enter generation telemetry, diagnostics, browser bundles, or logs.
- Queued successful non-private exchanges into durable `chat_postprocess` jobs.
  Immediate best-effort processing uses the existing candidate/dedupe/scoring
  services for facts, preferences, emotional events, promises, and boundaries,
  refreshes episodic callbacks/promises/open threads, and leaves completed chat
  untouched when memory work fails and retries later.
- Documented setup, variables, fallback rules, readiness, SSE/retry semantics,
  prompt order, post-chat processing, UI behavior, deployment choices, and the
  opt-in live smoke. CI excludes the live marker and requires mocked provider
  tests, Ruff, ESLint, TypeScript, and the production build.

Completion evidence:
- A live, opt-in end-to-end test used the configured server-side Groq key for
  one real Eidolon turn. A persisted preference was retrieved into the bounded
  prompt, Groq streamed the grounded answer through the chat endpoint, SSE
  emitted start/token/done in order, generation usage/timing/finish telemetry
  was captured, and a history reload contained exactly one user and one Groq
  assistant row. The key was neither printed nor persisted.
- `alembic upgrade head` - passed.
- `pytest -m "not live"` - passed: 195 tests; the single live test was
  deselected.
- `RUN_GROQ_LIVE_TEST=1 pytest -q -m live tests/test_groq_live.py` - passed:
  1 test in 1.17 seconds after the final hardening pass.
- `ruff check .` and `ruff format --check .` - passed: all 74 backend files.
- `npm run lint` - passed.
- `npm run build` - passed, including TypeScript and all static routes.
- `git diff --check` - passed.
- Source/bundle audit found no configured Groq key in application or frontend
  output, no frontend Groq credential reference, and no forbidden/heavy runtime
  dependency. The only key-shaped source values are explicitly fake test
  tokens; the README value is a setup placeholder. `.env` and
  `.env.*` remain ignored except `.env.example`.
- Focused failure-path tests verify typed and unexpected provider failures do
  not disclose exception text, preserve the existing turn for reroll/edit,
  roll back attempted edits, retain ordinary 404 behavior, and emit only safe
  bounded diagnostic codes.

## Current status

Local MVP is implemented and validated. FastAPI and Next.js dev servers start locally, `/health` returns the exact expected payload, and the app supports register/login/refresh/logout/chat/stream with persisted history plus persona, preference-aware memory extraction, dependency-free pgvector-backed hybrid recall, user-selected source-linked message memory, reversible forgotten-memory state, an inspectable memory candidate pipeline, debug-only active-thread learning decisions, bidirectional memory contradiction metadata with user-resolvable conflicts, relationship decay/timeline/milestones/recent-shift summaries, type-aware PostgreSQL-backed proactive/debug jobs including context-aware unresolved-thread nudges, relationship-milestone notes, stale-note skipping after user return, delayed follow-ups, user-paced proactive cooldowns, and qualitative relationship-aware note tone and repair suppression, stricter relationship-aware adult gates, private conversation and one-turn privacy modes, migration-backed tests, continuity-complete private export, account erasure, and deploy/backup templates. Session privacy now uses HttpOnly refresh cookies scoped to `/auth`, in-memory access tokens, credentialed fetch, browser-Origin checks, legacy localStorage cleanup, and proactive access rotation. The personal runtime now starts its PostgreSQL scheduler by default, serializes cross-process ticks with an advisory lock, retries unexpected failures with bounded backoff, releases worker locks on every transition, and exposes configured/running state plus safe outcomes only in authenticated Debug. Proactive presence now targets morning and goodnight notes in a validated IANA timezone, shifts automatic jobs out of configurable quiet hours, handles DST, reschedules pending rows after preference changes, defers stale due work without consuming failure retries, and copies a validated 1-168 hour note cooldown into new and rescheduled proactive jobs. Open-thread presence is now intentional: ordinary questions answered in the same turn do not create unresolved-thread notes or nudges, while explicit future/reminder loops still can. The frontend is split into focused app shell, rail, chat, inspector, panel, runtime-status, companion-state, navigation, knowledge, and controller modules. Its mobile-first shell now opens on the active conversation, uses explicit Threads/Conversation/Companion workspaces, retains the efficient three-pane desktop layout, and keeps API/database/provider state inside authenticated Debug while the primary header uses human relationship, privacy, and content-mode posture. Character and thread transitions apply only after successful, current-version loads; stale side-state and history responses are discarded and failed active selections restore the last fully loaded pair. Active thread deletion now reports through normal busy/error/notice state, keeps the user in the same companion context, and opens a fresh room when no sibling thread remains. Latest-turn edits now regenerate the companion reply, remove stale assistant replies, refresh source-linked memory and conversation-local journals, reverse and recalculate source-linked relationship effects for effect-bearing turns, replace queued conversation jobs, reject older turns, and keep the draft intact on failed saves. Latest-turn deletion now removes the user line plus dependent companion replies, reverses source-linked relationship effects when available, clears source-linked memory, rebuilds the conversation journal from remaining safe messages, replaces queued jobs from remaining safe assistant-ending threads, and rejects older user turns. Companion-reply deletion now removes source-linked memory, reconstructs conversation-local journals, replaces stale queued jobs when safe continuity remains, and leaves user-ending remnants quiet. New companions now begin in a four-stage authored builder that captures presence, inner life, shared world, trust, adult eligibility, memory/privacy, and proactive preferences, retains recoverable drafts, and distinguishes request failure from a persisted profile whose room did not open. The API normalizes names and bounds top-level text plus flexible profile JSON by UTF-8 size, depth, fan-out, key length, and value length. The core chat surface now opens genuinely empty threads with the active character's authored greeting, hides provider/debug markers, groups messages, humanizes presence and delivery state, supports assistant/system single-message deletion and latest-user-turn deletion, source-linked Remember controls, thread privacy controls, one-shot composer privacy, renders proactive notes as subtle presence event cards, records actual privacy changes as timestamped system event cards, and uses natural deterministic mock replies that turn bounded persona, recent-thread, mood, memory, relationship-repair, and episode cues into ordinary dialogue while dropping hidden labels, scores, malformed callback metadata, and response-strategy narration. Private turns keep their accepted privacy provenance across streaming and reroll, remain owner-visible in history/search/export, and are excluded from later standard prompt history, recall timestamps, memory extraction, journals, relationship changes, and proactive work. Privacy events are idempotent, assistant-unread neutral, excluded from durable cognition, and canonicalized before prompt assembly so stored event prose cannot become model instructions. Character creation/editing now stores a richer authored profile through `boundaries_json`, including relationship type, flaws, values, humor, interests, backstory, greeting, nicknames, authored SFW scenario presets, custom scenario text, consent profile, memory preferences, private mode, adult-memory storage controls, and proactive presence controls. Memory now has separate Active and Forgotten views with reversible restore, permanent delete, character-scoped stale-response guards, and forgotten rows excluded from retrieval, prompts, debug learning links, and active conflicts. Memory, journal, relationship, and overview panels translate cognition state into human-readable recall, episode, bond, temperature, momentum, recent shifts, callback, active conflict review, continuity labels, safe episode notes, and privacy summaries instead of raw score displays. Adult settings now present a readiness checklist, relationship-repair guidance, intensity labels, and memory posture copy instead of raw gate state alone. Data cleanup now requires typed scoped confirmations for chat, memory, and thread deletion actions while account erasure remains password and phrase protected. Thread deletion removes conversation-local messages, journals, and queued jobs in the owned account scope. Episodic journals now classify bounded continuity signals for repair arcs, anniversaries, inside jokes, shared moments, milestones, shared references, callbacks, open threads, steady exchanges, and adult-redacted episodes; those signals feed prompt assembly, signal-matched private response planning, the Journal UI, and account export without exposing raw metadata in chat. Prompt assembly now includes a private response plan summary derived from persona, consent profile, memories, journals, relationship, safety mode, time context, and pending proactive events, with private debug visibility and user-facing leakage tests. Conversation presence now has migration-backed exact-message read receipts, derived unread counts, visible-tab refresh, stale-load protection, and restrained thread/character indicators. Live replies now move through observable connecting, composing, and streaming phases with persona- and response-length-aware mock cadence plus conversation-bound cancellation. Companion creation and profile saving now share synchronous session-owned mutation custody, complete response validation, canonical malformed-success recovery, and cross-session stale-completion isolation.

## Full frontend reset - 2026-07-15

Status: complete and validated. This checkpoint supersedes the earlier frontend
shell, Inspector, Debug/Data panel, and Threads/Conversation/Companion workspace
references retained later in this file as historical goal evidence.

Implemented:
- Replaced the three-pane dashboard with a full-height, chat-first companion
  room and restrained desktop/mobile navigation for Chat, Memories,
  Relationship, Moments, and Settings.
- Rebuilt streaming chat around an atmospheric companion presence, editorial
  assistant messages, quiet user bubbles, typing choreography, fixed responsive
  composer, honest text-only attachment/voice-ready affordances, private turns,
  remembered-message callbacks, message mutations, and an empty-state first
  conversation that feels intentional.
- Replaced technical thread navigation with a focus-trapped Past conversations
  drawer containing companion switching, conversation history, search, unread
  presence, and real create/open actions.
- Added a five-stage guided introduction covering emotional welcome, name,
  appearance, persisted visual theme, atmosphere, personality, voice,
  relationship expectation, boundaries, memory posture, presence preferences,
  and an authored opening line. The same experience creates additional
  companions without placeholder-only controls.
- Rebuilt Memories as a private archive of people, promises, moments, inside
  jokes, and patterns, preserving real add/edit/pin/fade/restore/delete/conflict
  actions while hiding scores and storage terminology.
- Rebuilt Relationship around natural bond phases, qualitative trust/shared
  language/closeness narratives, repair guidance, milestones, boundaries, and
  shared-history changes without counters or affection bars.
- Rebuilt Moments as a dated cinematic journal with manual reflections,
  generated episode summaries translated into human language, expandable
  callbacks/open moments, redaction posture, and real edit/delete actions.
- Moved companion editing, proactive timing, memory privacy, current-conversation
  privacy, adult age/consent/intensity/memory gates, export, cleanup, account
  deletion, and logout into a cohesive Settings experience. Adult controls no
  longer appear in the header.
- Added reusable visual primitives, a lightweight inline icon system, persisted
  character-specific Ember/Cedar/Rain/Plum themes, layered near-black material
  surfaces, ambient grain/gradients, warm editorial typography, one controlled
  accent, semantic focus states, focus traps, safe-area support, keyboard send,
  and reduced-motion behavior. No frontend dependency was added.
- Reworded live controller errors/notices so canonical state, backend, thread,
  SFW, journal-state, and similar implementation language cannot leak into the
  new product surfaces.

Validation:
- `cd apps/web && npm run lint` - passed.
- `cd apps/web && npm run build` - passed, including TypeScript and all five
  static routes.
- Temporary Playwright Chromium journey - passed after real registration,
  onboarding persistence, SSE chat, generated Moment creation, navigation, and
  conversation-history opening. Auth, onboarding, conversations, Chat,
  Memories, Relationship, Moments, and Settings were visually inspected at
  1440x900; all five primary authenticated views were also inspected at 390x844.
  The temporary browser/spec/screenshots were removed and no test dependency was
  added to the repository.
- `cd apps/api && .venv/bin/python -m pytest` - passed: 168 tests in 228.19s.
- `cd apps/api && .venv/bin/alembic upgrade head` - passed.
- `cd apps/api && .venv/bin/ruff check .` - passed.
- `cd apps/api && .venv/bin/ruff format --check .` - passed: 69 files already
  formatted.
- `git diff --check` - passed after final documentation and cleanup.
- Visual-journey accounts were removed from the local PostgreSQL database after
  inspection.

## Historical goal completion audit - evidence against the original brief

Completion decision:
- The original ten product areas and all runtime constraints are implemented in
  the current worktree and proven by source, backend tests, production frontend
  compilation, a fresh multi-viewport browser journey, visual inspection, and
  canonical PostgreSQL cleanup. No required product behavior remains represented
  only by a placeholder, proposal, fixture, or unverified claim.

Requirement evidence:
1. The dark, brand-first auth entry and mobile-first Threads / Conversation /
   Companion shell render at 320x720, 390x844, and 1440x1000 without document
   overflow, clipped application controls, or incoherent overlap. Fresh captures
   covered auth, empty and populated chat, Builder, Memory, Journal, Bond, Adult,
   Debug, and Data; source inspection confirms human summaries in primary views
   and raw operational state confined to authenticated Debug.
2. The current chat renders companion posture, presence, grouping, timestamps,
   read state, natural composing/streaming cadence, search focus, latest-turn edit,
   reroll, message/thread deletion, privacy and scene event cards, manual presence,
   and guarded fallback/error states. Two real SSE turns completed in the final
   browser run. Conversation text contained no mock label, prompt/version field,
   context manifest, response-plan key, raw relationship state, or memory internals.
3. Registration creates the authored SFW default companion, and the four-stage
   Builder persists identity, relationship type, personality, flaws, values,
   voice, humor, interests, backstory, greeting, nickname posture, scenario,
   boundaries, consent, age/eligibility, intensity, memory/privacy, and proactive
   controls. The final browser run created a second authored companion exactly
   once and opened its canonical room.
4. Adult settings expose account age confirmation, explicit character age,
   profile eligibility, relationship readiness, consent and limits, intensity,
   private posture, and adult-memory opt-in. The final run proved a settled
   fail-closed-to-open gate transition while Conversation remained explicitly in
   Safe mode. Structural backend tests cover ambiguous/minor age, coercion,
   exploitation, illegal content, stalking/privacy abuse, real-world harm, repair
   gating, and durable-memory restrictions without explicit fixtures.
5. PostgreSQL memory supports source links, importance, confidence, emotional
   weight, pinning, decay, reversible forgetting, recall time, contradiction
   groups, conflict resolution, dedupe/update/delete, candidate inspection, and
   pgvector plus keyword fallback. Unit/integration tests cover deterministic
   embeddings, semantic retrieval beyond recent cohorts, preference enforcement,
   contradiction lifecycles, and private/adult exclusions; the final browser run
   persisted and exported a manual memory before verified scoped deletion.
6. Episodic journals distinguish generated episodes and authored notes across
   milestones, emotion, open threads, repair, anniversaries, callbacks, inside
   jokes, shared moments, and references. The private response planner consumes
   bounded persona, continuity, relationship, safety, time, scene, and pending
   presence state without exposing chain-of-thought. The final Debug capture
   showed only the bounded plan summary and manifest, while chat stayed clean.
7. Relationship state owns familiarity, trust, warmth, tension, intimacy,
   attachment, mood, conflict/repair, absence decay, milestones, timeline, recent
   qualitative changes, and tone effects. Tests cover updates, reversals after
   edit/delete, decay persistence, adult gating, prompt posture, and proactive
   suppression; the final Bond view rendered qualitative state without raw scores.
8. PostgreSQL-backed jobs cover inactivity, local morning/goodnight windows,
   unresolved-thread follow-up, relationship milestones, delayed follow-ups,
   cooldowns, snooze/disable controls, quiet hours, stale-user-return suppression,
   retry/backoff, advisory locking, and safe generation fallback. The final run
   created one bounded job, produced one natural manual check-in, and exported its
   continuity before cleanup; scheduler tests do not require Ollama.
9. Authenticated Debug exposes bounded provider/runtime, plan, retrieval,
   relationship, job, and safe diagnostic state separately from primary chat.
   Private threads/turns, export, clear chat/memory, thread deletion, and protected
   account erasure are present. The final export contained two characters, two
   conversations, seven messages, one memory, two journals, two relationship
   states, and one job, with no credential-shaped keys; clear chat, clear memory,
   and password-plus-phrase erasure each issued exactly one accepted request.
10. Current tests cover auth, persistence, safety gates, memory scoring and
    contradiction, relationship changes, proactive cooldowns, prompt cleanliness,
    access isolation, export privacy, migrations, mocked Ollama, diagnostics,
    concurrency, and canonical recovery. All frontend network boundaries exercised
    in the final journey completed with zero page errors, zero console errors,
    and zero unexpected HTTP failures; the only anonymous refresh response was the
    expected `401` before registration.

Constraint evidence:
- Manifests contain only the required lightweight stack: Next.js/React/Tailwind
  and FastAPI/Pydantic/SQLAlchemy/Alembic/asyncpg/APScheduler, with PostgreSQL 16,
  pgvector, and pg_trgm. Streaming uses `text/event-stream`; mock is default and
  Ollama is the only production inference provider.
- A current manifest/source scan found no paid/commercial inference API, managed
  auth/database/queue, external vector database, Redis, Celery, LangChain,
  Supabase, Firebase, Pinecone, Chroma, Clerk, Auth0, NextAuth, Stripe, Socket.io,
  Three.js, Framer Motion, WebRTC, voice, avatar, image/video generation, or other
  forbidden runtime feature. Browser and backend fixtures remained SFW.

Final validation:
- `pip install -e ".[dev]"` passed; Alembic reached
  `0008_diagnostic_events`; all 168 backend tests passed in 96.17 seconds.
  `ruff format .` left all 69 files unchanged, and both Ruff checks passed.
- `npm install` remained current at 394 packages with zero vulnerabilities.
  ESLint passed, and the production build passed TypeScript and generated all
  five static routes.
- The fresh browser audit captured 21 settled states across 320px, 390px, and
  1440px. It exercised one registration, one companion creation, two SSE turns,
  two privacy transitions, one search, one manual memory, one authored journal,
  one age-gate update, one proactive check-in, one export, scoped chat and memory
  cleanup, and one account erasure without duplicate writes or leaked internals.
- Account erasure removed users, characters, conversations, messages, memories,
  journals, relationships, jobs, and refresh sessions. The independent acceptance
  throttle and diagnostic rows, temporary browser runtime, screenshots, script,
  and isolated ports were then removed explicitly.

## World-class continuation - Manual presence and clear-chat trust boundary

Completed in this checkpoint:
- Gave manual check-in and clear-chat requests synchronous custody over the
  authenticated owner, token, session generation, operation, room, companion,
  and known transcript IDs. Navigation and account replacement release the new
  surface before paint; delayed completions and `finally` paths cannot mutate or
  unlock it.
- Replaced the manual-note weak predicate with the complete Message contract,
  exact room/assistant/proactive provenance, a new-ID requirement, and the API's
  600-character limit. Readable JSON `null` remains the valid paused, snoozed,
  or cooling-down result.
- Added one canonical-history recovery read for malformed/non-JSON accepted
  check-ins and require exactly one unambiguous new proactive note before local
  application. Ordinary side/history refresh is a separate guarded operation,
  with distinct persisted-but-refresh-failed feedback.
- Made Clear chat reachable from Data during an active reply and cancel that
  stream before DELETE, while export, memory, thread, and account mutations stay
  disabled. Same-frame repeated actions still issue only one request.
- Accept a direct clear count only when it is a nonnegative integer covering all
  known local message IDs. Otherwise, one complete canonical transcript read
  must prove exact emptiness before local state resets; contradictions and
  unverifiable accepted responses preserve the visible transcript.

Validation completed:
- Controlled browser acceptance cancelled an active streamed reply, issued one
  DELETE after a same-frame double Clear, and observed backend cancellation of
  that stream. A same-frame double check-in issued one POST, persisted a real
  proactive note, replaced its response with non-JSON, and recovered the note
  through canonical history with zero page errors.
- A second clear replaced its successful response with malformed output and used
  one canonical recovery GET plus one later ordinary refresh GET. Final canonical
  PostgreSQL/API history contained zero messages.
- `pip install -e ".[dev]"` passed and `alembic upgrade head` reached
  `0008_diagnostic_events` with the validation-only JWT secret. All 168 backend
  tests passed in 100.47 seconds; `ruff format .` left all 69 files unchanged and
  both Ruff checks passed.
- `npm install` remained current at 394 packages with zero vulnerabilities.
  ESLint passed, and the production build passed TypeScript and generated all
  five static routes. The initial migration attempt also proved that an undersized
  development JWT secret fails closed before database access.
- Temporary browser code, acceptance accounts, throttles, diagnostics, and the
  localhost fault-injection API were removed. The normal API returned the exact
  health payload, the restarted web app returned HTTP 200, acceptance table
  counts were zero, `git diff --check` passed, no forbidden dependency was
  declared, and `next-env.d.ts` was restored to its development route reference.

## World-class continuation - Monotonic presence and receipt trust boundary

Completed in this checkpoint:
- Added a field-wise Conversation summary advancement contract. Immutable owner,
  room, companion, and creation identity must match; title/privacy/scene follow
  the newest update, while last-message and read-cursor timestamps advance
  independently and unread count changes only from a snapshot covering both.
- Replaced background presence's typed collection cast with complete owner-scoped
  list validation. The exact active room/companion must be present, missing rows
  are preserved, new cross-tab rows may merge, and malformed/aborted/superseded
  snapshots remain silent background failures.
- Runtime-validated read-receipt responses against the authenticated owner, exact
  room, and expected companion. Malformed receipts no longer enter navigation
  state, while already validated history remains visible.
- Made single and batch summary merges non-regressing across rail, active room,
  and stable-navigation state. Canonical null titles now correctly clear stable
  drafts instead of resurrecting older title text.
- Runtime-validated fallback companion fetches against the captured session owner
  and requested ID before selection, preserving stable-room recovery on failure.
- Replaced conversation search's final weak object predicate with the complete
  Message-list contract, adding UUID, role, room, timestamp, metadata, duplicate,
  and ordering enforcement.

Validation completed:
- `pip install -e ".[dev]"` and `alembic upgrade head` passed at
  `0008_diagnostic_events`; all 168 backend tests passed in 103.39 seconds.
  `ruff format .` left all 69 files unchanged and both Ruff checks passed.
- `npm install` remained current at 394 packages with zero vulnerabilities.
  ESLint passed. The first production typecheck caught a nullable owner escaping
  across fallback I/O; capturing the synchronous owner fixed both the type and
  runtime custody, and the final build passed TypeScript and all five static routes.
- Controlled browser acceptance held an old presence response while a newer title
  persisted, then released it without rollback. A malformed presence list and two
  malformed read receipts were ignored while history and the foreground title
  remained usable.
- The same pass rejected a malformed search payload with inline readable error
  copy, rendered no injected sentinel, and completed with zero page errors.
- Temporary browser code, accounts, diagnostics, throttles, and localhost API
  were removed. Normal API health returned the exact payload, web returned HTTP
  200 after a clean dev-server restart, PostgreSQL acceptance tables were empty,
  `git diff --check` passed, no forbidden dependency was declared, and
  `next-env.d.ts` was restored to its development route reference.

## World-class continuation - Companion-state hydration trust boundary

Completed in this checkpoint:
- Added one dependency-free runtime contract for active/forgotten memories,
  journals, relationship state, adult readiness, scheduled jobs, character Debug,
  conversation Debug, assembled context, and health payloads.
- Enforced exact companion/thread provenance, UUIDs, unique list IDs, bounded
  text and JSON, offset-aware timestamps, ordered entity updates, finite metric
  ranges, known modes/statuses, lock-state coherence, and adult
  allowed/effective/reason/intensity consistency before React state application.
- Changed all seven companion refresh requests and three health requests to read
  `unknown`. Each slice settles independently; malformed optional Debug cannot
  block chat, while malformed adult state fails closed and malformed health is
  degraded rather than presented as healthy.
- Cleared memory, journals, relationship, adult readiness, and Debug immediately
  on companion change, retained request-version/caller guards, and prevented
  delayed navigation/logout results from hydrating a superseded workspace.
- Reused the same strict memory and journal contracts in every mutation and
  canonical-recovery path, removing weaker controller-local validators.

Validation completed:
- `pip install -e ".[dev]"` and `alembic upgrade head` passed at
  `0008_diagnostic_events`; all 168 backend tests passed in 100.38 seconds.
  `ruff format .` left all 69 files unchanged and both Ruff checks passed.
- `npm install` remained current at 394 packages with zero vulnerabilities.
  ESLint passed, and the first production typecheck identified an overly narrow
  generic predicate signature; it was corrected with explicit boundary types,
  after which final TypeScript and all five static routes built successfully.
- Controlled canonical browser acceptance loaded real relationship, adult,
  scheduler/Debug, and `mock` runtime health state with no page errors.
- A paired malformed pass exercised eight poisoned routes. The workspace stayed
  usable, adult readiness reported unavailable in SFW, invalid Debug remained
  empty, a malformed healthy-provider response rendered degraded, no injected
  sentinel reached the page, and there were no page errors.
- Temporary browser code, accounts, diagnostics, throttles, and the localhost
  acceptance API were removed. The normal API returned its exact health payload,
  web returned HTTP 200 after a clean dev-server restart, PostgreSQL acceptance
  tables were empty, `git diff --check` passed, no forbidden dependency was
  declared, and `next-env.d.ts` was restored to its development route reference.

## World-class continuation - Chat transcript and mutation ownership

Completed in this checkpoint:
- Added a dependency-free complete Message runtime contract for UUID and thread
  provenance, allowed roles, bounded nonempty content, offset timestamps, known
  content/privacy modes, and size/depth/fan-out/key/string-bounded JSON metadata.
  Complete histories also reject duplicate IDs, mixed rooms, and decreasing time.
- Made send streams, latest-turn edits, rerolls, and message deletes capture the
  account owner, access token, local session generation, target room/companion,
  and exact operation intent before I/O. Account reset invalidates all four;
  thread navigation also clears edit ownership, fixing its previous asymmetry.
- Hardened SSE ordering and limits. One exact new user boundary must precede
  tokens; malformed boundaries/JSON/fragments are terminal for local application;
  streamed text is bounded; and completion requires one new complete assistant
  message in the owned room. An unreadable start no longer consumes the draft.
- Runtime-validated canonical history loads and all direct message mutation
  results. Direct edit success must match the submitted text; reroll must carry
  exact provenance; and delete must report a positive count.
- Added one canonical history recovery for malformed/non-JSON accepted edits,
  rerolls, and deletes. Recovery requires the exact edited turn, one unambiguous
  new reroll, or proven target absence before applying state. The later ordinary
  companion/history refresh is separately guarded by the same action owner.
- Preserved recoverable edit text after request and verification failures, and
  prevented delayed old-session/old-room responses and `finally` paths from
  changing messages, feedback, refresh targets, or a newer action lock.

Validation completed:
- `pip install -e ".[dev]"` and `alembic upgrade head` passed at
  `0008_diagnostic_events`; all 168 backend tests passed in 97.16 seconds.
  `ruff format .` left all 69 files unchanged and both Ruff checks passed.
- `npm install` remained current at 394 packages with zero vulnerabilities;
  final ESLint and production builds passed TypeScript and all five static routes.
- Controlled browser acceptance used one real mock-stream turn, proved a
  same-frame double edit save issued one PATCH, retained the exact draft after an
  injected 503, and restored controls.
- A non-JSON accepted edit used one dedicated canonical history recovery read,
  verified the persisted regenerated turn, and then issued one separate ordinary
  post-persistence side/history refresh. PostgreSQL held the canonical edit.
- Temporary browser code, users, diagnostics, and throttle rows were removed.
  Normal API health returned the exact payload, web returned HTTP 200,
  `git diff --check` passed, no forbidden dependency declaration was found, and
  `next-env.d.ts` was restored to its development route reference.

## World-class continuation - Thread metadata mutation ownership

Completed in this checkpoint:
- Replaced independent title, privacy, and Shared Scene in-flight booleans with
  one synchronous session-owned metadata action capturing owner, token, session
  generation, navigation provenance, target room/companion, and canonical intent.
- Made metadata writes mutually exclusive with companion create/save and room
  create/provision/delete before React renders disabled state.
- Added canonical title normalization plus exact title, privacy, and Shared Scene
  match helpers to the complete Conversation runtime contract.
- Runtime-validated every successful PATCH. Malformed/non-JSON accepted writes
  now use exactly one canonical owner-scoped collection read and select the exact
  target room; missing, malformed, or contradictory state fails closed.
- Preserved authored title and scene input after request or verification failure.
  Verified same-session summaries may update the rail after navigation moves,
  while active drafts, side refresh, and feedback require the owning target.
- Invalidated metadata custody with navigation session reset so old-account
  responses and `finally` paths cannot mutate or unlock a newer session.

Validation completed:
- Controlled browser acceptance proved a same-frame double title save issued one
  PATCH, retained the exact title after an injected 503, and restored controls.
- A non-JSON successful title PATCH used exactly one canonical collection GET,
  recovered the complete target room, canonicalized the visible title, and
  persisted exactly one normalized PostgreSQL value.
- `npm run lint` and `npm run build` passed after the shared metadata action and
  contract changes, with clean TypeScript and all five static routes.

## World-class continuation - Auth entry and session bootstrap ownership

Completed in this checkpoint:
- Added a dependency-free runtime contract for canonical email, normalized
  optional display names, complete users, UUIDs, offset timestamps, bounded
  JWT-shaped access tokens, exact bearer type, expected account identity, and
  coherent HS256 issuer/audience/type/subject/token/time claims.
- Replaced render-timed auth submission protection with one synchronous action
  owner capturing mode, canonical email, payload, and local session generation.
  Same-turn repeats issue one request, ordinary failures retain recoverable
  fields, and stale completions or `finally` paths cannot alter newer state.
- Kept the entry experience mounted through bootstrap with distinct Signing in,
  Creating account, and Opening room states, preventing an empty authenticated
  shell from flashing before navigation and companion state are ready.
- Recovered a malformed or non-JSON accepted login/registration response through
  one cookie refresh, accepting only a complete response for the expected email.
- Made refresh rotation generation- and user-owned. Logout invalidates pending
  local work synchronously and serializes server revocation after any accepted
  cookie rotation, so delayed refresh cannot resurrect the session on reload.
- Made bootstrap session-owned across `/auth/me`, companion/thread collections,
  active-companion fetch, navigation hydration, history, and side-state refresh.
- Runtime-validated every bootstrap collection. A malformed/non-JSON successful
  first-room POST now uses exactly one canonical owner-scoped list recovery and
  accepts only one unambiguous new normal empty room for the default companion.
- Added client validation aligned with API email, display-name, and password
  bounds while preserving server authority and readable API failures. No API,
  database, dependency, schema, or migration change was required.

Validation completed:
- `npm run lint` and `npm run build` passed with clean TypeScript and all five
  static routes after the auth lifecycle and navigation hydration changes.
- Controlled browser acceptance proved a same-frame double sign-in issued one
  POST, retained email/password after an injected 503, and restored controls.
- A malformed accepted registration issued one recovery refresh. Its malformed
  persisted first-room response used two collection GETs total, one discovery
  and one recovery read, then opened exactly one PostgreSQL room.
- A scheduled refresh was held while Logout cleared local state. Releasing it
  produced exactly one serialized server logout; the old response did not reopen
  the app, and a full reload remained on the signed-out entry screen.
- A final real-token browser smoke check accepted the backend's JWT claim set and
  completed registration, owned bootstrap, and first-room opening after the
  claim-coherence hardening.

## World-class continuation - Companion selection room provisioning

Completed in this checkpoint:
- Replaced character selection's unvalidated implicit conversation POST with a
  dedicated synchronous session-owned provision action capturing owner, token,
  session generation, navigation version, companion, and known thread IDs.
- Allowed provisioning to nest only under the exact still-owned companion-create
  mutation. Unrelated companion, explicit New/Private, thread deletion, and
  provision mutations are mutually excluded, including before React renders.
- Suppressed repeated same-target selection synchronously and gave only that
  character row native disabled semantics plus stable `Opening room...` copy;
  existing character and thread navigation remains available.
- Runtime-validated the complete returned Conversation owner, companion,
  privacy/default-scene metadata, empty state, title, UUIDs, timestamps, and
  bounded JSON before selection.
- Recovered malformed or non-JSON successful provisioning through exactly one
  canonical owner-scoped list read and one unambiguous new normal empty room.
  Failed or unverifiable creation restores the last fully loaded pair.
- Preserved navigation priority. An accepted provision overtaken by another
  selection may merge only its same-session summary and cannot replace the
  active room or publish stale feedback.
- Invalidated provision and optional parent ownership before paint on logout or
  account replacement. An old response or `finally` path cannot enter the newer
  account, navigate, report, or clear its provision lock.
- Propagated provision state through Chat, content mode, creation, account/
  privacy, and Inspector conflicts without adding dependencies or changing the
  API, database schema, or migrations.

Validation completed:
- Controlled browser acceptance proved one POST after same-frame repeated
  selection, retained the previous room after an injected 503, and persisted no
  target room.
- A non-JSON successful POST used two collection GETs total: one initial
  discovery read and exactly one canonical recovery read. It selected one
  verified room, and PostgreSQL contained exactly one target thread.
- A delayed accepted provision overtaken by selecting the default companion
  added one target summary without replacing `Chat with Eidolon`.
- Account B began provisioning before account A's accepted provision was
  released. A's response did not expose its companion, navigate, report, or
  unlock B; B retained `Opening room...` until its own injected failure settled.
- `npm run lint` passed. The first production build caught and corrected a
  nullable `Array.find` inference mismatch; the next build completed TypeScript
  and all five static routes.
- `pip install -e ".[dev]"` and `alembic upgrade head` passed; `ruff format .`
  left all 69 backend files unchanged, `ruff check .` passed, and all 168 tests
  passed in 124.75 seconds.
- `npm install` remained current with 394 packages and zero vulnerabilities;
  final lint and production build passed, and `next-env.d.ts` was restored to
  the development route reference.
- Temporary Playwright code, users, diagnostics, and throttle rows were removed;
  normal Codespaces origin settings, API health, and web HTTP 200 were restored.

## World-class continuation - Thread deletion session ownership

Completed in this checkpoint:
- Replaced global busy-driven deletion with one synchronous session-owned action
  that snapshots owner, token, session generation, navigation version, target
  room, and companion before I/O. New/Private and companion mutations are
  mutually excluded with this destructive action.
- Suppressed same-turn duplicate DELETE requests before React renders disabled
  state. Chat, content mode, account/privacy, creation, and Inspector mutations
  consume the dedicated deleting state while ordinary thread navigation remains
  available.
- Preserved the active room and exact `DELETE THREAD` phrase after request
  failure, malformed unverified success, or canonical contradiction. The phrase
  clears only after persistence is established.
- Runtime-validated the complete owner-scoped canonical thread list after every
  accepted DELETE. Malformed or zero-count successful output is accepted only
  when one canonical read proves target absence; a still-present target fails
  closed without speculative local deletion.
- Treated a positive delete count as authoritative when the remaining-room read
  is unavailable, removing only the target locally and reporting persistence
  separately from refresh availability.
- Opened an existing same-companion sibling after verified deletion. When none
  remains, created exactly one normal replacement and reused complete
  Conversation validation plus one-list-read malformed/non-JSON recovery.
- Kept navigation overtaking safe: canonical target removal may update the rail,
  but delayed success, failure, and replacement branches cannot reclaim the
  newer selection, publish stale feedback, or refresh obsolete room state.
- Invalidated deletion custody before paint on logout/account replacement. An
  older session response or `finally` path cannot mutate or unlock a newer
  account's deletion, list, confirmation, feedback, or selection.
- Updated frontend UX and acceptance contracts. No backend, dependency, schema,
  or migration change was required; the existing owned DELETE endpoint already
  returns an exact positive count and has cross-account cleanup regressions.

Validation completed:
- `cd apps/web && npm install && npm run lint && npm run build` passed with 394
  packages, zero vulnerabilities, clean TypeScript, and all five static routes;
  `apps/web/next-env.d.ts` was restored to the development route reference.
- `cd apps/api && alembic upgrade head && pytest` passed at
  `0008_diagnostic_events` with all 168 tests green in 128.77 seconds.
  `ruff format .` left all 69 files unchanged and `ruff check .` passed.
- Controlled browser acceptance issued one DELETE for a same-frame double click,
  retained the phrase and selected room after an injected 503, and used exactly
  one canonical GET to recover a persisted delete whose response reported zero.
- Deleting the last room with a non-JSON replacement response issued exactly one
  replacement POST and one recovery GET after the deletion list read, then
  opened one canonical replacement. PostgreSQL contained exactly that one room.
- A delayed accepted delete overtaken by sibling navigation removed its target
  summary without replacing the sibling or publishing stale feedback.
- Account B began a delayed delete before account A's accepted delete was
  released. A's response did not alter or unlock B; B retained its in-flight
  label, target room, and phrase until its own injected failure settled.
- Temporary localhost acceptance services, Playwright scripts, users, diagnostic
  rows, and throttle rows were removed. Normal Codespaces services, configured
  public origins, `/health`, and the web HTTP 200 check were restored.

## World-class continuation - Thread creation session ownership

Completed in this checkpoint:
- Added one synchronous session-owned action for New and Private thread
  creation. It snapshots owner, token, session generation, companion, privacy
  mode, navigation version, and known thread IDs before any request begins.
- Invalidated creation ownership before paint on logout or replacement login,
  and guarded responses and `finally` paths so old sessions cannot insert a
  thread, navigate, publish feedback, or unlock a newer account's action.
- Added a complete Conversation runtime contract covering immutable owner and
  companion UUIDs, normalized title, bounded JSON metadata, privacy and Shared
  Scene invariants, read/unread state, and ordered timestamps. Legacy rows that
  omit the effective default scene marker are normalized to the canonical shape.
- Runtime-validated bootstrap and refreshed companion/thread lists. Malformed or
  non-JSON successful creation now performs exactly one canonical list read and
  accepts only one unambiguous new empty room with the expected companion and
  privacy state.
- Kept ordinary thread and companion navigation available during creation. An
  accepted create overtaken by navigation may merge only its same-session rail
  summary; it cannot replace the selected room or publish stale feedback.
- Propagated creation busy state through Chat, content mode, companion creation,
  account/privacy, and Inspector mutations. New and Private use native disabled
  semantics and a stable Opening label, and remain unavailable without a current
  companion.
- Normalized conversation titles at the API boundary, rejected control/format
  characters, empty PATCHes, and explicit null privacy/scenario fields, while
  preserving intentional blank/null title clearing. New conversations now store
  explicit canonical `scenario_mode: default` metadata.
- Updated API, frontend, and acceptance contracts. No dependency, database
  schema, or migration change was required.

Validation completed:
- `cd apps/web && npm install && npm run lint && npm run build` passed with 394
  packages, zero vulnerabilities, clean TypeScript, and all five static routes;
  `apps/web/next-env.d.ts` was restored to the development route reference.
- `cd apps/api && pip install -e ".[dev]" && alembic upgrade head && pytest`
  passed with Alembic at `0008_diagnostic_events` and all 168 tests green in
  100.26 seconds; `ruff check .` passed and `ruff format .` left all 69 files
  unchanged.
- Disposable-account browser acceptance passed at 390x844 and 1440x1000 with
  zero document-level horizontal overflow, page errors, failed requests, or
  unexpected HTTP responses.
- Five controlled thread POSTs proved failed-state retention, same-turn duplicate
  suppression, one-list-read non-JSON recovery, navigation overtaking, and
  overlapping delayed old/new session creation.
- During a delayed create, New, Private, Create, Send, and content mode were
  natively disabled while an existing thread remained selectable. Releasing the
  accepted response added its summary without replacing that selected room.
- Account B began a delayed create before account A's accepted response was
  released. A's response did not enter B's list, navigate, notify, or unlock B;
  B's own release created and opened exactly one new room.
- Endpoint regressions covered title normalization and clearing, complete empty
  thread response state, empty PATCH rejection, explicit null rejection, and
  control/format-character rejection on create and update.
- Screenshots showed coherent Threads and three-pane layouts without clipping or
  overlap. Temporary Playwright tooling, users, and throttle rows were removed;
  normal Codespaces services and health checks were restored.

## World-class continuation - Companion profile mutation ownership

Completed in this checkpoint:
- Added one synchronous session-owned mutation controller shared by companion
  creation and profile saving. Each action snapshots user, token, session
  generation, navigation version, target, and canonical payload before I/O.
- Invalidated mutation ownership before paint on logout or replacement login, so
  stale responses and `finally` paths cannot alter drafts, lists, rooms,
  feedback, side-state refreshes, or a newer session's action lock.
- Runtime-validated complete Character responses: immutable owner, UUIDs,
  normalized text, bounded profile JSON, adult invariants, and ordered
  timestamps must all match the submitted canonical payload.
- Recovered malformed or non-JSON successful creation through exactly one
  canonical character-list read and one unambiguous new exact profile. Recovered
  malformed successful saving through one canonical target read and exact draft
  verification. Unverified accepted writes retain authored input.
- Preserved create and save drafts after request failure, prevented same-turn
  duplicate writes synchronously, and propagated mutation busy state through
  Chat, content mode, Create, account/privacy, and Inspector controls while
  leaving ordinary room navigation available.
- Added API-aligned native field bounds in Persona, Adult, and Builder surfaces;
  rejected empty Character PATCH requests, required-field nulls, and Unicode
  control/format characters in names while preserving intentional nullable-field
  clearing.
- Cancelled native form default behavior on Builder's final Continue transition.
  This prevents React reconciliation from turning that same activation into an
  unintended submit when the footer changes to Create companion.
- Updated frontend and acceptance contracts. No dependency, database schema, or
  migration change was required.

Validation completed:
- `cd apps/web && npm install && npm run lint && npm run build` passed with 394
  packages, zero vulnerabilities, clean TypeScript, and all five static routes;
  `apps/web/next-env.d.ts` was restored to the development route reference.
- `cd apps/api && pip install -e ".[dev]" && alembic upgrade head && pytest`
  passed with Alembic at `0008_diagnostic_events` and all 167 tests green in
  102.85 seconds; `ruff check .` passed and `ruff format .` left all 69 files
  unchanged.
- Disposable-account browser acceptance passed at 390x844 and 1440x1000 with
  zero document-level horizontal overflow, no page errors, failed requests, or
  unexpected HTTP responses, and only the expected controlled failure logging.
- Four profile PATCHes proved failed-draft retention, same-turn duplicate
  suppression, exactly one canonical-read malformed-success recovery, and
  overlapping delayed old/new session ownership.
- Four companion POSTs proved failed-draft retention, same-turn duplicate
  suppression, exactly one canonical-list-read non-JSON recovery, and overlapping
  delayed old/new session ownership. The run also exposed and verified the
  final-Continue accidental-submit correction.
- Releasing account A's delayed save did not alter or unlock account B's active
  save. Releasing account B's delayed create after account C began creating did
  not insert B's profile, close C's Builder, publish stale feedback, navigate, or
  unlock C's action.
- Persona name and Adult age controls exposed native lengths of 120 and 3.
  Screenshots at both target viewports showed coherent mobile and desktop
  layouts without clipping or overlap.
- Temporary Playwright tooling, disposable users, and acceptance throttle rows
  were removed. PostgreSQL contains zero users and zero throttle rows, and normal
  Codespaces services and health checks were restored.

## World-class continuation - Account session custody ownership

Completed in this checkpoint:
- Added one synchronous session-owned action controller spanning profile update,
  account export, and account erasure so same-frame submissions cannot duplicate
  or overlap.
- Snapshotted access token, user ID, user email, and session generation for every
  account action. Logout and replacement sessions invalidate ownership
  synchronously, so stale responses and `finally` paths cannot alter, unlock,
  download data for, or erase a newer session.
- Normalized display names with control-character rejection, whitespace
  compaction, a 120-character bound, and intentional blank-to-null clearing.
  The API now distinguishes an explicit clear from an omitted field and rejects
  empty profile updates or null age-gate values.
- Runtime-validated the complete returned user identity and recovered malformed
  successful profile responses through exactly one canonical `/auth/me` read.
  Current-room readiness refreshes retry only after an observed room change and
  remain guarded by the exact owning session and active room.
- Validated account exports before creating a browser download: required
  collections, current-user identity, unique character and conversation IDs,
  cross-collection ownership links, and credential-shaped keys are checked
  fail-closed. Valid downloads use one short-lived object URL that is always
  revoked.
- Treated any parsed account-erasure `2xx` as authoritative, even when its count
  payload is malformed, while retaining password and confirmation inputs after
  request failure. Only the exact owning session may clear local credentials.
- Propagated account mutation busy state through Chat, content mode, and
  Inspector actions, added operation-specific progress labels, and bounded and
  labelled destructive credential fields. No dependency, database schema, or
  migration change was required.

Validation completed:
- `cd apps/web && npm install && npm run lint && npm run build` passed with 394
  packages, zero vulnerabilities, clean TypeScript, and all five static routes;
  `apps/web/next-env.d.ts` was restored to the development route reference.
- `cd apps/api && pip install -e ".[dev]" && alembic upgrade head && pytest`
  passed with Alembic at `0008_diagnostic_events` and all 166 tests green in
  97.29 seconds; `ruff check .` passed and `ruff format .` left all 69 files
  unchanged.
- Disposable-account browser acceptance passed at 390x844 and 1440x1000 with
  zero document-level horizontal overflow, no page errors or failed requests,
  and only the expected anonymous refresh `401` plus two controlled `503`
  responses.
- Four profile PATCHes proved failed-draft retention, same-tick duplicate
  suppression, one-read malformed-success recovery, and overlapping old/new
  session ownership. Four canonical-user reads were observed across the tested
  account transitions.
- Two export GETs proved that an injected credential key produced no blob URL or
  download, while one valid export downloaded exactly once, parsed as the
  current account, and created and revoked exactly one object URL.
- Three deletion requests proved failed credential retention, delayed old-session
  deletion without clearing a replacement session, and authoritative local
  closure after a parsed `2xx` with a malformed zero count.
- A delayed profile action from account A settled after account B began its own
  delayed profile action; A's completion did not unlock B or alter B's draft.
  A delayed account-B erasure then settled after account C registered without
  disturbing C, while account C's own accepted erasure closed only C.
- Temporary Playwright tooling, disposable users, and acceptance throttle rows
  were removed. PostgreSQL contains zero users and zero throttle rows after the
  pass.

## World-class continuation - Authored journal mutation ownership

Completed in this checkpoint:
- Added one synchronous character-owned action owner across personal journal
  add, edit, and delete so same-frame submissions cannot duplicate or overlap.
- Snapshotted companion, optional source room, target, normalized authored text,
  and known journal IDs; room changes preserve the captured association while
  companion changes invalidate local ownership and clear old journal state
  before paint.
- Expanded frontend journal typing to the complete API ownership, conversation,
  metadata, and timestamp contract.
- Runtime-validated journal entities, manual-source provenance, target identity,
  normalized text, bounded importance, collections, timestamps, and positive
  delete counts before applying successful responses.
- Added one-read canonical recovery for malformed successful add, edit, and
  delete responses, including verification of a newly created matching row, an
  exact updated target, or durable target absence.
- Preserved add/edit drafts after persistence failure and distinguished an
  accepted operation whose canonical state could not be verified from a failed
  request.
- Prevented stale responses and `finally` paths from changing a newer
  companion's list, forms, notices, errors, or action lock.
- Applied journal busy semantics to Chat, content mode, proactive/data actions,
  and Inspector mutations while leaving room and companion navigation usable.
- Added native 200/2,000-character bounds and accessible labels to the personal
  note fields, and updated frontend/testing contracts for the ownership model.
  No backend, schema, dependency, or generated-episode behavior changed.

Validation completed:
- `cd apps/web && npm install && npm run lint && npm run build` passed with 394
  packages, zero vulnerabilities, clean TypeScript, and all five static routes;
  `apps/web/next-env.d.ts` was restored to the development route reference.
- `cd apps/api && pip install -e ".[dev]" && alembic upgrade head && pytest`
  passed with Alembic at head and all 165 tests green in 91.05 seconds;
  `ruff check .` passed and `ruff format .` left all 69 files unchanged.
- Disposable-account browser acceptance passed at 390x844 and 1440x1000 with
  zero document-level horizontal overflow.
- Five journal POSTs covered controlled persistence failure with retained
  title/summary, same-tick duplicate suppression, malformed provenance recovery,
  a room switch during a delayed add, and concurrent delayed old/new companion
  adds.
- Malformed successful add and edit responses each performed exactly one
  validated canonical journal GET before clearing their form or edit state;
  malformed successful delete performed one canonical GET and verified durable
  absence before publishing success.
- Two PATCH attempts proved failed-edit retention and malformed-success
  recovery; one DELETE proved destructive count validation and canonical repair.
- Room navigation stayed usable and left the delayed note associated with its
  snapshotted origin room while Chat, content mode, and Inspector mutations were
  natively disabled until settlement.
- Companion navigation released old local ownership before paint. A newer
  companion add started before the old response was released; the old `finally`
  left the newer action disabled and its draft intact, and each accepted note
  appeared only under its owning companion in PostgreSQL.
- Browser diagnostics contained only the expected anonymous refresh `401` and
  two controlled `503` responses, with no page errors, failed requests, or
  unexpected HTTP/console errors. Protected account erasure returned `200`.
- Temporary Playwright tooling, disposable users, and acceptance throttle rows
  were removed; normal Codespaces services and health checks were restored.

## World-class continuation - Memory mutation ownership

Completed in this checkpoint:
- Added one synchronous memory-action owner spanning manual add/edit/pin/delete,
  forget/restore, conflict resolution, message Remember, low-value fading, and
  clear-all so same-frame requests cannot duplicate or overlap.
- Snapshotted character, conversation, target, and authored input; character
  changes invalidate ownership before paint, while thread changes invalidate
  message-owned Remember without cancelling character-wide persistence.
- Runtime-validated complete memory entities, character provenance, active or
  forgotten state, bounded scores, timestamps, source-message linkage, delete
  and fade counts, and conflict-resolution IDs.
- Added canonical malformed-success recovery through validated Active and
  Forgotten list reads, including verification that destructive state changes
  actually appear in the recovered lists.
- Guarded local lists, forms, notices, errors, and side/history refreshes by the
  exact action owner; stale completion and `finally` paths cannot alter or unlock
  newer work.
- Preserved add/edit drafts and `CLEAR MEMORIES` after persistence failure;
  accepted clear-all empties both recall states, consumes the phrase, and remains
  locally authoritative after refresh failure.
- Kept clear-all available when Active recall is empty so durable Forgotten-only
  data can still be wiped, and relabeled the displayed count as Active recall.
- Applied native memory busy semantics to Chat, content mode, and Inspector
  mutations while leaving thread navigation available.
- Updated frontend UX, testing acceptance, and this progress log. No backend,
  schema, dependency, or journal behavior changed.

Validation completed:
- `cd apps/web && npm install && npm run lint && npm run build` passed with 394
  packages, zero vulnerabilities, clean TypeScript, and all five static routes;
  `apps/web/next-env.d.ts` was restored to the development route reference.
- `cd apps/api && pip install -e ".[dev]" && alembic upgrade head && pytest`
  passed with Alembic at head and all 165 tests green in 97.74 seconds;
  `ruff check .` and `ruff format --check .` passed across all 69 Python files.
- Disposable-account browser acceptance passed at 390x844 and 1440x1000 with
  zero document-level horizontal overflow.
- Four manual memory POSTs covered controlled persistence failure with retained
  draft, same-tick duplicate suppression, malformed-character provenance, a
  delayed old-character success, and a concurrent new-character success.
- The malformed successful add recovered through exactly one validated Active
  and one Forgotten GET before clearing its draft and rendering canonical data.
- One delayed source-linked Remember persisted once, disabled Chat/content mode/
  Inspector natively, then unlocked the newer room before release. It caused
  zero old-room history, Debug, or read requests and published no stale feedback.
- A Forgotten-only character retained both durable data and `CLEAR MEMORIES`
  after a controlled persistence failure. The accepted malformed-count retry
  consumed the phrase, retained canonical empty state after a controlled history
  refresh failure, and remained empty in both API and UI after reload.
- Character navigation released a delayed add before paint. A newer character
  add started before the old response was released; the old `finally` left the
  newer Inspector/draft disabled, and each persisted memory later appeared only
  under its owning character.
- Browser diagnostics contained only the expected anonymous refresh `401` and
  three controlled `503` responses, with no page errors, failed requests, or
  unexpected HTTP/console errors. Protected account erasure returned `200`.
- Temporary Playwright tooling, disposable users, and checkpoint throttle rows
  were removed; normal Codespaces services and health checks were restored.

## World-class continuation - Manual presence and clear-chat ownership

Completed in this checkpoint:
- Added one synchronous conversation-action owner containing operation, thread,
  and character identity for manual presence notes and clear-chat.
- Replaced closure-based post-await state with committed-conversation guards;
  navigation releases old local ownership before paint and prevents stale message
  append/reset, notices, errors, and side/history refreshes.
- Runtime-validated manual notes as proactive assistant messages from the owned
  room, appended valid persisted notes immediately, and treated null as a normal
  paused/snoozed/cooling-down outcome without unnecessary refresh.
- Runtime-validated nonnegative clear counts for count-specific feedback while
  treating any parsed `2xx` as authoritative deletion and emptying only the
  current owned transcript.
- Distinguished persistence failure from accepted presence/clear operations with
  failed refreshes, retaining the canonical local note or empty transcript.
- Changed clear-chat to return explicit acceptance so `CLEAR CHAT` remains ready
  after failed persistence and clears only after the backend accepted the wipe.
- Applied native action disabling to Chat, content mode, and Inspector mutations
  while keeping thread navigation available.
- Updated frontend UX, testing acceptance, and this progress log. No backend,
  schema, or dependency change was required.

Validation completed:
- `cd apps/web && npm install && npm run lint && npm run build` passed with 394
  packages, zero vulnerabilities, clean TypeScript, and all five static routes;
  `apps/web/next-env.d.ts` was restored to the development route reference.
- `cd apps/api && pytest` passed all 165 tests in 95.77 seconds, while
  `ruff check .` and `ruff format --check .` passed across all 69 Python files.
- Disposable-account browser acceptance passed at 390x844 and 1440x1000 with
  zero document-level horizontal overflow.
- Five manual-note requests covered controlled persistence failure, same-tick
  duplicate suppression, delayed accepted navigation, cooldown null, malformed
  provenance recovery, and persisted refresh failure. Four clear-chat requests
  covered the equivalent failure, duplicate, navigation, malformed-count, and
  persisted refresh-failure paths.
- Delayed accepted note/clear responses caused zero obsolete history, Debug, or
  read requests after navigation and published no stale messages, resets,
  notices, or errors in the newer room. The newer room unlocked before either
  old response was released.
- The malformed successful note and clear responses each recovered through one
  owned history refresh. Valid persisted refresh failures retained the canonical
  local note or empty transcript and recovered the same PostgreSQL state after
  reload.
- Failed clear persistence retained both the transcript and `CLEAR CHAT` phrase;
  an accepted delayed clear consumed the phrase without touching the newer
  thread. Native Chat, content-mode, cleanup, and Inspector disabling was
  observed while the active room owned an action.
- Browser diagnostics contained only the expected anonymous refresh `401`, four
  controlled `503` responses, and normal aborted SSE teardown after the five
  completed setup turns, with no page errors or unexpected HTTP/console errors.
  Protected account erasure returned `200`.
- Alembic is at `0008_diagnostic_events (head)`. Temporary Playwright tooling,
  disposable users, and checkpoint throttle rows were removed; normal
  Codespaces services were restored and `/health`, `/health/db`, `/health/llm`,
  and the web root all passed.

## World-class continuation - Reroll and message-delete mutation ownership

Completed in this checkpoint:
- Added one synchronous message mutation owner containing operation, thread,
  character, and message identity, preventing same-frame reroll/delete duplicates
  and conflicting send/edit actions.
- Replaced reroll/delete's shared global busy writes with conversation-owned local
  state, so navigation can invalidate an old action before paint without
  unlocking a newer unrelated operation.
- Snapshotted reroll content mode and deletion role before awaiting and guarded
  local messages, notices, errors, and companion/history refreshes by current
  conversation and request identity.
- Runtime-validated rerolls as new assistant messages with matching conversation
  and `reroll_of` provenance, and validated positive deletion counts before local
  optimistic removal.
- Preserved canonical local rerolls/removals after successful persistence and
  distinguished failed follow-up refresh from failed persistence.
- Applied native busy semantics to the composer, one-turn privacy, content mode,
  message actions, and Inspector mutations while the current room owns an action.
- Moved committed conversation publication into a layout effect, removing the
  render-time ref mutation while keeping stale ownership invalidation before
  paint.
- Updated frontend UX, testing acceptance, and this progress log. No backend,
  schema, or dependency change was required.

Validation completed:
- `cd apps/web && npm install && npm run lint && npm run build` passed with 394
  packages, zero vulnerabilities, clean TypeScript, and all five static routes;
  `apps/web/next-env.d.ts` was restored to the development route reference.
- `cd apps/api && pytest` passed all 165 tests, while `ruff check .` and
  `ruff format --check .` passed across all 69 Python files.
- Disposable-account browser acceptance passed at 390x844 and 1440x1000 with
  zero document-level horizontal overflow.
- Four rerolls covered controlled persistence failure, same-tick duplicate
  suppression, delayed accepted navigation, malformed-provenance recovery, and
  persisted refresh failure. Four deletes covered the equivalent paths plus
  latest-user-turn local dependent-reply removal.
- Delayed accepted reroll/delete responses caused zero obsolete history, Debug,
  or read requests after navigation and published no stale messages, removals,
  notices, or errors in the newer room. The newer room's composer unlocked before
  either old response was released.
- Both malformed successful responses recovered through exactly one history GET.
  Both valid persisted refresh failures retained the canonical local result and
  recovered the same PostgreSQL state after reload.
- Native composer, privacy, content-mode, message-action, and Inspector disabling
  was observed in flight. Exactly four confirmation dialogs covered four delete
  attempts; the duplicate click opened no second dialog.
- Browser diagnostics contained only the expected anonymous refresh `401` and
  four controlled `503` responses, with no page errors, failed requests, or
  unexpected HTTP/console errors. Protected account erasure returned `200`.
- Temporary Playwright tooling, disposable users, and checkpoint throttle rows
  were removed; normal Codespaces services and health checks were restored.

## World-class continuation - Conversation search ownership and navigation

Completed in this checkpoint:
- Made conversation search case-insensitive literal substring matching, escaping
  PostgreSQL `%`, `_`, and `\\` pattern characters instead of broadening user
  input into wildcard queries.
- Added backend whitespace normalization, visible-text rejection, existing
  120-character query bounds, and deterministic wildcard/boundary coverage.
- Added dedicated idle, loading, ready, empty, and inline-error frontend states
  so typing alone no longer presents a false no-results state.
- Added synchronous request ownership keyed by query, thread, and navigation
  version, suppressing duplicate submits and discarding delayed results/errors
  after query changes or navigation.
- Runtime-validated message arrays and conversation provenance before displaying
  API search results.
- Turned results into accessible human-labeled controls with timestamps that
  open the mobile Conversation workspace, scroll to, and focus the exact
  ordinary, proactive, or system message while respecting reduced motion.
- Updated API, frontend UX, testing acceptance, and this progress log. No new
  dependency or schema migration was required.

Validation completed:
- `cd apps/api && pytest` passed all 165 tests, including literal `%`, `_`, and
  `\\` matching, whitespace normalization, and the 120-character query bound.
- `cd apps/api && ruff check . && ruff format --check .` passed across all 69
  Python files after applying the formatter's one mechanical route adjustment.
- `cd apps/web && npm install && npm run lint && npm run build` passed with 394
  packages, zero vulnerabilities, clean TypeScript, and all five static routes;
  `apps/web/next-env.d.ts` was restored to the development route reference.
- Disposable-account browser acceptance passed at 390x844 and 1440x1000 with
  zero document-level horizontal overflow.
- Ten browser searches covered one controlled `503`, same-tick duplicate
  suppression, delayed query and thread ownership changes, literal-percent and
  empty results, and exact ordinary, proactive, and system-message focus.
- The failed search retained its query and restored submission. Both delayed
  successful responses were ignored after ownership changed, with no stale
  results or errors in the newer state.
- Search-result activation opened the mobile Conversation workspace and focused
  the exact persisted message ID. Browser diagnostics contained only the
  expected anonymous refresh `401` and controlled `503`, with no page errors,
  failed requests, or unexpected HTTP/console errors. Account erasure returned
  `200`.
- Temporary browser tooling, disposable users, and checkpoint throttle rows
  were removed; the normal Codespaces frontend configuration and service health
  checks were restored.

## World-class continuation - Latest-turn edit mutation ownership

Completed in this checkpoint:
- Added a synchronous edit mutation owner containing the conversation,
  character, and message IDs, preventing same-frame duplicate regeneration.
- Bounded both normal and edited composer submissions to the API's 6,000
  character limit and added the matching native textarea limit.
- Made edit/composer state conversation-owned: navigation clears old text, edit
  mode, and one-turn privacy while leaving any accepted backend edit to finish.
- Guarded regenerated-turn application, composer clearing, notices, errors, and
  side/history refresh by current conversation and mutation identity.
- Added runtime verification that the response contains the expected edited user
  message and an assistant reply in the owned conversation before local use.
- Preserved edit drafts after persistence failure and distinguished persisted
  edits with unreadable responses or failed follow-up refreshes.
- Disabled both Save and Cancel while edit regeneration owns the composer.
- Updated frontend UX, testing acceptance, and this progress log. No dependency,
  schema migration, or backend change was required.

Validation completed:
- `cd apps/web && npm install` passed with 394 packages audited and zero
  vulnerabilities.
- `cd apps/web && npm run lint && npm run build` passed; TypeScript and all five
  static routes completed, and `apps/web/next-env.d.ts` was restored to its
  development route reference afterward.
- Disposable-account browser acceptance passed at 390x844 and 1440x1000 with
  zero document-level horizontal overflow.
- Four controlled edit attempts proved failed-draft retention, Save/Cancel
  in-flight disabling, same-tick duplicate suppression, persisted regeneration,
  stale-navigation isolation, and refresh-failure reload recovery.
- The delayed accepted response caused zero old-thread history, debug, or read
  requests after navigation, while the current successful edit performed exactly
  one history GET.
- Browser diagnostics contained only the expected anonymous refresh `401` and
  two controlled `503` responses, with no unexpected HTTP failures, page errors,
  failed requests, or console errors. Protected account erasure returned `200`.
- Temporary browser files, disposable users, and checkpoint throttle rows were
  removed; final repository hygiene and API/frontend health checks passed.

## World-class continuation - Shared Scene mutation ownership

Completed in this checkpoint:
- Added a synchronous Shared Scene request lock alongside the existing mutation
  and navigation versions, preventing same-frame Set/Reset duplicates before
  React commits the dedicated saving state.
- Defensively normalized and bounded custom scene text before submission while
  preserving the authored draft after validation or API failure.
- Made stale persisted responses merge only canonical scenario metadata and
  monotonic activity timestamps into their matching list/stable room, preserving
  newer title, privacy, read, unread, and active-draft state.
- Restricted full active-room replacement, draft canonicalization, event/history
  loading, notices, and refresh errors to the still-current room and character.
- Replaced the previous explicit history load plus side-state refresh with one
  guarded refresh chain, eliminating the duplicate current-room history GET.
- Retained the distinct saved-but-refresh-unavailable error contract for custom
  scenes and resets.
- Updated frontend UX, testing acceptance, and this progress log. No dependency,
  schema migration, backend change, or additional React state was required.

Validation completed:
- `cd apps/web && npm install` passed with 394 packages audited and zero
  vulnerabilities.
- `cd apps/web && npm run lint && npm run build` passed; TypeScript and all five
  static routes completed.
- Restored `apps/web/next-env.d.ts` to the development route reference after the
  production build.
- Delayed-request disposable-account browser acceptance passed at 390x844 and
  1440x1000 with zero document-level horizontal overflow.
- The harness observed exactly four scenario PATCHes across one controlled
  `503`, one delayed stale success, one current custom save, and one reset. It
  proved failed-draft retention, native in-flight disabling, same-tick duplicate
  suppression, stale room-only application, and zero obsolete old-room reads.
- The current custom save performed exactly one history GET and rendered its
  generic backend event immediately, proving the duplicate history load was
  removed.
- The reset persisted while its next history GET received a controlled `503`;
  the UI retained default mode, cleared the custom draft, showed the distinct
  refresh error, fabricated no local event, and recovered the backend reset
  event after reload. The delayed scene also remained intact in its own room.
- Browser diagnostics contained only the expected anonymous refresh `401` and
  controlled `503` failures, with no unexpected console errors, page errors,
  failed requests, or server errors. Protected account erasure returned `200`
  for every created account.
- Temporary Playwright files, packages, disposable users, and harness throttle
  rows were removed, and the normal Codespaces frontend API configuration was
  restored.

## World-class continuation - Thread privacy mutation ownership

Completed in this checkpoint:
- Added synchronous single-request ownership for conversation privacy PATCHes so
  repeated actions cannot create duplicate transitions before the busy render.
- Snapshotted the target conversation, character, requested mode, and navigation
  version; privacy remains backend-confirmed and a failed request leaves the
  visible mode unchanged.
- Made stale successes merge only the matching thread's canonical privacy mode
  and monotonic activity timestamps, preserving newer title, scenario, read, and
  unread fields.
- Restricted active conversation replacement, companion-state refresh, history
  reload, notices, and refresh errors to the still-current navigation owner.
- Kept current transitions refreshing history immediately so their atomic,
  backend-owned privacy event appears without a manual reload.
- Distinguished failed persistence from a saved privacy mode whose follow-up
  history/companion refresh failed.
- Updated frontend UX, testing acceptance, and this progress log. No dependency,
  schema migration, backend change, or additional React state was required.

Validation completed:
- `cd apps/web && npm install` passed with 394 packages audited and zero
  vulnerabilities.
- `cd apps/web && npm run lint && npm run build` passed; the final defensive
  no-op adjustment was followed by another clean lint, TypeScript run, and
  five-route production build.
- Restored `apps/web/next-env.d.ts` to the development route reference after
  each production build.
- Delayed-request disposable-account browser acceptance passed at 390x844 and
  1440x1000 with zero document-level horizontal overflow.
- The concurrency harness observed exactly three privacy PATCHes across one
  controlled `503`, one delayed stale success, and one current success. It
  proved failed-mode retention, native in-flight disabling, same-tick duplicate
  suppression, stale list-only application, zero obsolete old-thread refreshes,
  and immediate backend event rendering for the current transition.
- A second fault-injection harness persisted one private transition, failed its
  next history GET with a controlled `503`, retained the saved private mode,
  showed the distinct refresh error, rendered no fabricated local event, and
  recovered the persisted event after reload.
- Browser diagnostics contained only the expected anonymous refresh `401` and
  controlled `503` failures, with no unexpected console errors, page errors,
  failed requests, or server errors. Protected account erasure returned `200`
  for every created account.
- Temporary Playwright files, packages, disposable users, and harness throttle
  rows were removed, and the normal Codespaces frontend API configuration was
  restored.

## World-class continuation - Thread title mutation ownership

Completed in this checkpoint:
- Added synchronous single-request ownership for title PATCHes so repeated clicks
  cannot submit twice before React commits the busy render.
- Snapshotted the target thread, normalized title, and navigation version for
  every save; blank titles remain an intentional clear and nonblank titles are
  defensively checked against the API's 200-character bound.
- Preserved the visible title draft and surfaced readable API errors after
  failed saves while always releasing busy and request ownership.
- Applied a successful stale response only to the matching thread-list and
  stable-navigation title fields, preserving newer metadata and preventing the
  old response from replacing a newer active thread or editor draft.
- Added native disabled behavior to the title input and Save button during
  global mutation ownership or message sending.
- Updated frontend UX, testing acceptance, and this progress log. No dependency,
  schema migration, backend change, or additional React state was required.

Validation completed:
- `cd apps/web && npm install` passed with 394 packages audited and zero
  vulnerabilities.
- `cd apps/web && npm run lint && npm run build` passed; TypeScript and all five
  static routes completed.
- Restored `apps/web/next-env.d.ts` to the development route reference after the
  production build.
- Delayed-request disposable-account browser acceptance passed at 390x844 and
  1440x1000 with zero document-level horizontal overflow.
- The harness observed exactly two title PATCHes: one controlled `503` and one
  successful recovery. It proved failed-draft retention, native in-flight
  disabling, same-tick duplicate suppression, and list-only application after a
  newer thread selection overtook the delayed response.
- Browser diagnostics had one expected anonymous refresh `401`, one expected
  controlled title-save `503`, no unexpected console errors, page errors,
  failed requests, or server errors, and protected account erasure returned
  `200`.
- Temporary Playwright files, packages, disposable users, and harness throttle
  rows were removed, and the normal Codespaces frontend API configuration was
  restored.

## World-class continuation - Inspector mutation ownership

Completed in this checkpoint:
- Added a synchronous character-save lock so repeated clicks cannot start a
  second profile PATCH before React commits its busy render.
- Snapshotted the target character, draft, conversation, and navigation version
  for each save instead of reading mutable selection state after awaits.
- Made persisted saves update the matching list/stable record while replacing
  the active character and draft only when that character is still selected.
- Guarded post-save companion refresh with the captured navigation version and
  active character, so a newer character/thread selection wins and obsolete
  side state cannot apply.
- Distinguished failed persistence from successful persistence followed by a
  failed readiness refresh; the former preserves the draft, while the latter
  reports that reload is needed without claiming the save failed.
- Wrapped Inspector panel content in one native disabled, `aria-busy` fieldset
  during global save, send, and Shared Scene ownership. Panel navigation remains
  readable while all descendant mutation controls are locked.
- Updated frontend UX, testing acceptance, and this progress log. No dependency,
  schema migration, backend change, or additional React state was required.

Validation completed:
- `cd apps/web && npm install` passed with 394 packages audited and zero
  vulnerabilities.
- `cd apps/web && npm run lint && npm run build` passed; TypeScript and all five
  static routes completed.
- Restored `apps/web/next-env.d.ts` to the development route reference after the
  production build.
- Delayed-request disposable-account browser acceptance passed at 390x844 and
  1440x1000 with zero document-level horizontal overflow.
- The harness observed exactly two profile PATCHes: one controlled `503` and one
  successful recovery. It proved disabled descendants, duplicate prevention,
  failed-draft retention, later-save recovery, and that an overtaking character
  selection was not replaced by the old response.
- The released stale response started zero obsolete character side refreshes.
- Browser diagnostics had one expected anonymous refresh `401`, one expected
  controlled save `503`, no unexpected console errors, page errors, failed
  requests, or server errors, and protected account erasure returned `200`.
- Temporary Playwright files and packages were removed, and the normal
  Codespaces frontend API configuration was restored.

## World-class continuation - cross-surface adult draft invariants

Completed in this checkpoint:
- Added one pure character-draft canonicalizer shared by the staged Builder,
  Persona editor, Adult settings, and final character payload construction.
- Kept malformed active input available for readable field validation while
  immediately closing dependent permissions when age, eligibility, or privacy
  prerequisites fail.
- Made an ineligible age clear character adult eligibility, intensity, and
  adult-memory storage in every editing surface.
- Made private-by-default clear adult-memory storage in Builder and Persona as
  well as Adult settings, and disabled the Builder storage control while private.
- Added explicit validation for legacy or programmatic private-plus-storage and
  eligibility-off-plus-storage contradictions.
- Preserved account age-gate ownership inside Adult settings: it remains a
  runtime permission and does not leak into reusable character profile state.
- Updated frontend UX, testing acceptance, and this progress log. No dependency,
  schema migration, backend change, or additional React state was required.

Validation completed:
- `cd apps/web && npm install` passed with 394 packages audited and zero
  vulnerabilities.
- `cd apps/web && npm run lint && npm run build` passed; TypeScript and all five
  static routes completed.
- Restored `apps/web/next-env.d.ts` to the development route reference after the
  production build.
- Disposable-account browser acceptance passed at 390x844 and 1440x1000 with
  zero document-level horizontal overflow.
- The browser created a companion through the staged Builder, proved private and
  ineligible resets there, carried state through Persona and Adult panels,
  verified canonical create/update responses, and reloaded persisted state.
- Browser diagnostics had one expected anonymous refresh `401`, no unexpected
  console errors, page errors, failed requests, or server errors, and protected
  account erasure returned `200`.
- Temporary Playwright files and packages were removed, and the normal
  Codespaces frontend API configuration was restored.

## World-class continuation - canonical Adult settings interaction

Completed in this checkpoint:
- Reused the character builder's strict whole-number age parser in Adult
  settings, so partial numeric strings, decimals, negatives, and over-150 values
  never appear eligible.
- Made in-panel draft transitions canonical: an ineligible age or eligibility-off
  action immediately resets intensity to Off and adult-memory storage off.
- Made private-by-default immediately clear adult-memory storage while preserving
  otherwise valid character eligibility and intensity.
- Disabled intensity unless the account age gate, adult character age, and
  character eligibility are open; disabled adult-memory storage unless those
  gates are open and private-by-default is off.
- Kept a one-way safety action available after account age-gate revocation: an
  already eligible character can still be turned off, while enabling and
  dependent edits remain locked.
- Added defensive transition handlers so programmatic events cannot bypass the
  same dependent-control rules.
- Updated frontend UX, browser acceptance, and this progress log. No dependency,
  schema migration, backend contract, or new React state was required.

Validation completed:
- `cd apps/web && npm install` passed with 394 packages audited and zero
  vulnerabilities.
- `cd apps/web && npm run lint && npm run build` passed; TypeScript and all five
  static routes completed.
- Restored `apps/web/next-env.d.ts` to the development route reference after the
  production build.
- Disposable-account browser acceptance passed at 390x844 and 1440x1000 with
  zero document-level horizontal overflow.
- The browser proved strict malformed-age locking, age/eligibility/private
  dependent resets, save-and-reload persistence, and closed-account-gate
  one-way disable behavior through real controls and API responses.
- Browser diagnostics had one expected anonymous refresh `401`, no unexpected
  console errors, page errors, failed requests, or server errors, and protected
  account erasure returned `200`.
- Temporary Playwright files and packages were removed, and the normal
  Codespaces frontend API configuration was restored.

## World-class continuation - canonical adult-dependent persistence

Completed in this checkpoint:
- Added API-boundary validation for the four known memory controls; malformed
  preference containers and non-boolean values now fail with readable `422`
  responses before persistence.
- Canonicalized character create and merged partial-update state so disabling
  adult eligibility forces content intensity to Off and adult-memory storage
  off, including a disable-only request.
- Made private-by-default character profiles force adult-memory storage off
  without changing otherwise eligible adult mode or its chosen intensity.
- Preserved unknown authored profile fields and copied profile layers before
  normalization instead of mutating request data.
- Kept explicit-age eligibility strict: an enabled profile cannot be downgraded
  below 18, and a rejected merged update leaves the previous row unchanged.
- Kept account age-gate revocation as an immediate runtime SFW gate rather than
  unexpectedly rewriting every authored character.
- Updated the data model, API contract, safety boundaries, testing acceptance,
  and this progress log. No migration, dependency, or frontend change was
  required.

Validation completed:
- Focused canonicalization and malformed-preference endpoint regressions passed.
- `cd apps/api && pip install -e ".[dev]"` passed with dependencies already
  satisfied.
- `cd apps/api && alembic upgrade head` passed with a valid ephemeral
  process-level JWT key; the existing short local env value was not edited or
  allowed to weaken runtime validation.
- Full backend suite passed: 164 tests in 92.47 seconds.
- `cd apps/api && ruff check . && ruff format . && ruff check .` passed; two
  touched files were formatted and the final lint pass was clean.

## World-class continuation - private Debug relationship and retrieval

Completed in this checkpoint:
- Added purpose-built frontend contracts for the private relationship and active
  memory snapshots already returned by the owner-scoped character Debug API.
- Added a raw Relationship State section to authenticated Debug with six bounded
  metrics, mood, conflict posture, repair state, and defensive tag rendering.
- Added Retrieved Memories as collapsed disclosures with type, importance,
  confidence, pin state, last-turn selection, and bounded inspectable prose.
- Kept both views out of the primary conversation and supplied explicit empty
  states for missing legacy snapshots instead of inventing diagnostic values.
- Added endpoint regressions that lock the safe memory field set, exclude
  embeddings, and verify the complete relationship snapshot shape.
- Updated the API contract, frontend UX, testing acceptance, and this progress
  log. No schema migration or new dependency was required.

Validation completed:
- Focused Debug endpoint regression - passed.
- `cd apps/api && pip install -e ".[dev]" && alembic upgrade head && pytest` -
  passed; 162 tests at revision `0008_diagnostic_events`.
- `cd apps/api && ruff check . && ruff format . && ruff check .` - passed; 69
  files remained formatted and the second lint pass was clean.
- `cd apps/web && npm install && npm run lint && npm run build` - passed with
  zero audit vulnerabilities; TypeScript and all five static routes completed.
- Live disposable-account browser acceptance - passed at 390x844 and
  1440x1000 with zero horizontal overflow, no unexpected console/page/request
  errors, and successful protected account erasure.
- Browser disclosure acceptance proved memory prose hidden while collapsed,
  visible on request, and absent with Relationship State from Conversation.
- Restored `apps/web/next-env.d.ts` to the development route reference after the
  production build.

Privacy posture:
- Raw relationship values and memory prose are authenticated diagnostic data,
  not companion-facing interface copy.
- The Debug API remains owner-scoped, caps memory snapshots at 10, excludes
  embeddings and internal ranking features, and tolerates old partial payloads.

## World-class continuation - rendered mobile hierarchy and browser proof

Completed in this checkpoint:
- Established a temporary Playwright/Chromium inspection path outside the
  application manifests and used actual pixels rather than CSS inference to
  audit signed-out, desktop, phone, builder, and companion states.
- Found and fixed a 390px chat hierarchy defect where the title collapsed into
  a short fragment and five stacked context cards pushed the conversation out
  of the first viewport.
- Made the phone conversation full-bleed, placed the bounded title and Save
  command in a stable grid, and kept privacy and presence-note commands paired
  without shrinking their labels.
- Replaced stacked phone context cards with a labeled, keyboard-focusable,
  snap-aligned internal strip whose continuation is visible at the edge; larger
  screens retain the existing two- and five-column grids.
- Reduced empty-room vertical ceremony so the authored greeting enters the
  first phone viewport while preserving the spacious desktop conversation.
- Reworked inspector navigation into fixed two-line label/status controls so
  Overview and Account no longer truncate on phone or desktop.
- Preserved the complete Conversation workspace label and allowed relationship
  posture to wrap cleanly at 320px without changing navigation state.
- Kept the implementation dependency-free and presentation-only: API contracts,
  React controller state, streaming ownership, stale-response guards, privacy,
  and error behavior are unchanged.
- Updated frontend UX, testing acceptance, and this progress log.

Validation completed:
- Temporary rendered browser run - passed at 320x720, 390x844, and 1440x1000;
  every measured state had exactly zero document-level horizontal overflow.
- Captured and visually inspected auth, empty conversation, real populated
  conversation, Threads, Companion, and character-builder states.
- Live browser mock-stream exchange - passed with natural persisted dialogue and
  no `[mock]`, prompt-version, relationship-score, or active-scene labels in the
  visible chat.
- Browser diagnostics - passed with no unexpected console errors, page errors,
  or failed requests; the single anonymous refresh `401` was recognized as the
  expected signed-out session probe.
- Browser cleanup - passed after every run; protected account erasure removed
  each temporary account and its conversation data.
- `cd apps/api && pip install -e ".[dev]" && alembic upgrade head && pytest` -
  passed; 162 tests at revision `0008_diagnostic_events` using ephemeral
  process-level JWT validation keys.
- `cd apps/api && ruff check . && ruff format . && ruff check .` - passed; 69
  files remained formatted and the second lint pass was clean.
- `cd apps/web && npm install && npm run lint && npm run build` - passed with
  zero audit vulnerabilities; TypeScript and all five static routes completed.
- Restored `apps/web/next-env.d.ts` to the development route reference after the
  production build.

Rendered posture:
- Phone layout now gives the exchange priority over status furniture while
  keeping all context available by touch or keyboard.
- Desktop retains its efficient three-pane view, but labels and controls no
  longer rely on clipping to fit.
- The visual evidence is reproducible with temporary local browser tooling and
  adds no runtime, paid-service, or recurring infrastructure dependency.

## World-class continuation - conversation-owned Shared Scene

Completed in this checkpoint:
- Replaced character-global scenario switching with a conversation-owned
  `default` or `custom` Shared Scene state stored in existing bounded metadata.
- Added normalized 1-1200 character validation, invisible-control rejection,
  safety-boundary checks, owner scoping, row locking, idempotent updates, and
  generic history events that never copy private scene prose into the transcript.
- Kept sibling conversations isolated and made reset fall back to the active
  character's authored setting without rewriting that character's profile.
- Fed the effective scene through reasoning, qualitative response planning,
  prompt assembly, and the deterministic mock provider so it changes ordinary
  dialogue without exposing internal labels.
- Exposed only scene mode and character count in authenticated Debug context;
  raw scene text remains absent from the manifest and generic event content.
- Added a compact Shared Scene control to the conversation surface with presets,
  custom text, a bounded counter, character-default preview, reset, per-thread
  draft retention, mutation locks, navigation-version guards, and readable
  persisted-versus-refresh failure handling.
- Added defensive legacy metadata parsing and Debug sanitization so malformed or
  oversized stored values fail closed to the character default.
- Added deterministic tests for concurrent identical writes, event idempotency,
  sibling and cross-account isolation, validation and safety rejection, reset,
  prompt use, Debug non-disclosure, and natural mock behavior.
- Updated README, product requirements, architecture, data model, API contract,
  prompt assembly, safety boundaries, frontend UX, testing acceptance, and this
  progress log.

Validation completed:
- Focused scenario, provider, prompt, memory, and relationship run - passed; 38
  tests.
- `cd apps/api && pip install -e ".[dev]" && alembic upgrade head && pytest` -
  passed; 162 tests at revision `0008_diagnostic_events` using an ephemeral
  process-level JWT validation key.
- `cd apps/api && ruff check . && ruff format . && ruff check .` - passed; 69
  files remained formatted and the second lint pass was clean.
- `cd apps/web && npm run lint && npm run build` - passed; TypeScript and all
  five static routes completed successfully.
- Restored `apps/web/next-env.d.ts` to the development route reference after the
  production build.
- Live authenticated Shared Scene smoke - passed: a custom scene shaped the mock
  reply, remained isolated from a sibling thread, appeared in private export,
  exposed only mode and character count in Debug, reset cleanly, and emitted only
  generic scene-change events.
- Protected account erasure removed the smoke account and all scene-bearing rows;
  database residue checks found zero matching users and messages.
- Live API request logs contained only expected `2xx` records, `/health` returned
  the exact expected payload, and the frontend returned HTTP `200`.

Ownership posture:
- A shared scene is room context, not a rewrite of the companion's durable
  identity.
- Character-authored settings remain the fallback, while custom text belongs to
  one conversation and is handled as private prompt context.
- Debug can prove that scene context was used without becoming another copy of
  the user's prose.

## World-class continuation - privacy-safe generation diagnostics

Completed in this checkpoint:
- Added migration `0008_diagnostic_events` with account, character, and
  conversation ownership plus cascading cleanup.
- Added an independent best-effort recorder that runs after the failed request
  transaction rolls back, retains only the newest 100 events per account, and
  cannot replace the original API or SSE failure.
- Restricted stored diagnostic data to controlled source, operation, code,
  allowlisted provider, approved safe message, ownership ids, and timestamp.
- Replaced forwarded provider exception strings with one fixed safe client
  response for ordinary messages, streams, rerolls, and edited turns.
- Captured immutable ownership ids before generation so SQLAlchemy rollback
  expiration cannot trigger lazy loading while recording the failure.
- Added character-scoped recent errors to the existing authenticated Debug
  payload and a compact Errors view with safe operation, provider, code, and
  time labels.
- Cleared Debug and active-conversation context on character changes, rejected
  refreshes, and superseded requests so stale diagnostics cannot remain visible.
- Added deterministic tests for post-rollback durability, fixed response text,
  provider sanitization, stream behavior, unchanged-history rollback for reroll
  and edit, bounded retention, migration shape, and cross-account isolation.
- Updated README, product requirements, data model, API contract, frontend UX,
  testing acceptance, and progress documentation.

Validation completed:
- Focused diagnostic and migration runs passed, including the additional
  reroll/edit rollback regression.
- `cd apps/api && pytest` - passed; 159 tests.
- `cd apps/api && ruff check . && ruff format . && ruff check .` - passed;
  67 files remained formatted and the second lint pass was clean.
- `cd apps/web && npm run lint && npm run build` - passed; TypeScript and all
  static routes completed successfully.
- Restored `apps/web/next-env.d.ts` to the development route reference after the
  production build.
- Migration upgrade - passed at revision `0008_diagnostic_events` using an
  ephemeral process-level JWT validation key.
- Live authenticated unavailable-Ollama smoke - passed: chat returned the fixed
  safe `503`, Debug returned exactly one owner-scoped
  `message/provider_unavailable/ollama` event without prompt or exception fields,
  and protected account erasure removed the smoke account and diagnostic row.
- Returned the live API to mock mode with the scheduler disabled for local
  inspection.

Diagnostic posture:
- Debug explains that generation failed without becoming a second store for
  private conversation or transport details.
- Request rollback and diagnostic commit are intentionally independent.
- Scheduled-job failures remain represented by their existing safe job state;
  this table covers foreground generation only.

## World-class continuation - authored journal integrity and control

Completed in this checkpoint:
- Fixed deterministic conversation refresh so it selects only generated journal
  rows, never the newest row regardless of source.
- Recognized both new `source=deterministic_summarizer` metadata and legacy
  `created_by=deterministic_summarizer` rows, avoiding a data migration while
  preserving existing automatic summaries.
- Marked new automatic episodes with explicit source ownership and retained the
  compatibility creator marker.
- Added normalized, visible-text validation for manual journal creation and a
  PATCH schema that rejects empty bodies, explicit nulls, whitespace-only text,
  and out-of-range importance.
- Added owner- and character-scoped personal-note PATCH/DELETE endpoints.
  Transcript-owned episodes return readable `409` responses so their summary
  and derived continuity metadata cannot drift apart.
- Added service-level mutation guards and `edited_by_user_at` provenance for
  successful personal-note corrections.
- Added clear Personal note and Conversation episode labels, inline note editing,
  cancellation, deletion, action-specific progress copy, and generated-episode
  transcript guidance in the Journal panel.
- Reworked journal mutations with one-action locking, preserved add/edit drafts
  on failure, readable API errors, and active-character checks before applying
  late responses.
- Updated README, product requirements, data model, API contract, memory design,
  frontend UX, testing, and progress documentation.

Validation completed:
- Focused journal integrity, validation, mutation, and access-control run -
  passed; 2 tests.
- `cd apps/api && pytest` - passed; 156 tests.
- `cd apps/api && ruff check . && ruff format . && ruff check .` - passed;
  64 files remained formatted and the second lint pass was clean.
- `cd apps/web && npm run lint && npm run build` - passed; TypeScript and all
  five static routes completed successfully.
- Restored `apps/web/next-env.d.ts` to the development route reference after the
  production build.
- Live authenticated overwrite regression - passed: a manual note and generated
  episode shared one conversation; after another chat, the manual title/summary
  remained exact while only the generated row advanced to four messages and
  incorporated the new transcript detail.
- Live personal-note PATCH recorded edit provenance, DELETE removed one row, and
  the generated episode remained intact.
- Live request logs contained only expected `2xx` records and no runtime errors.
- Smoke user and auth-throttle cleanup - passed; both residual counts were zero.
- API health returned the exact expected payload and the frontend returned HTTP
  `200`.

Ownership posture:
- Personal notes belong to the user even when linked to a conversation.
- Generated episodes belong to transcript-derived continuity and are changed by
  transcript edit, clear, or deletion flows rather than direct metadata drift.
- A later companion exchange can enrich its generated episode without silently
  replacing authored reflection.

## World-class continuation - reversible forgotten memory lifecycle

Completed in this checkpoint:
- Added migration `0007_memory_forgetting` with indexed nullable
  `memory_items.forgotten_at`; existing rows remain active after upgrade.
- Replaced destructive decay forgetting with an idempotent state transition and
  kept pinned memories protected from automatic fading.
- Added owner-scoped single-memory forget and restore endpoints plus active,
  forgotten, and all-state list filtering.
- Excluded forgotten rows from recent and pgvector candidate queries, prompt
  sections/manifests, debug source links, and active contradiction calculation.
- Added a second prompt-rendering guard so a mistakenly supplied forgotten model
  cannot contribute content or even a manifest identifier.
- Restoring recomputes current contradiction links and lowers accumulated decay;
  matching dedupe or explicit Remember revives the existing row instead of
  producing a duplicate.
- Kept permanent row deletion, full clear, account erasure, and source cleanup
  distinct and destructive; private export retains `forgotten_at` and bounded
  forget/restore history.
- Added separate Active and Forgotten memory views with reviewable timestamps,
  restore, manual forget, permanent delete, and honest active-only overview
  counts.
- Added per-character response tagging, request versioning, action locks,
  preserved forms on failure, and readable errors so late responses cannot move
  memory state into a newly selected companion.
- Updated README, product requirements, data model, API, memory, frontend,
  testing, roadmap, and progress documentation.

Validation completed:
- Focused migration/forget/restore/prompt tests - passed; 4 tests.
- Focused source-linked Remember revival regression - passed; the forgotten row
  returned with the same ID and `remembered_by_user` restore provenance.
- `cd apps/api && pytest` - passed; 154 tests.
- `cd apps/api && ruff check . && ruff format . && ruff check .` - passed;
  64 files remained formatted and the second lint pass was clean.
- `cd apps/web && npm run lint && npm run build` - passed; TypeScript and all
  five static routes completed successfully.
- Restored `apps/web/next-env.d.ts` to the development route reference after the
  production build.
- Migration round-trip - passed: downgraded from `0007_memory_forgetting` to
  `0006_auth_throttles`, upgraded to head, and confirmed revision `0007`.
- Live authenticated lifecycle smoke - passed: active search returned the test
  memory, forgetting moved it to the owner-only forgotten list and removed it
  from search and the actual assembled-context manifest, while restore made it
  active and selectable in the next real generation context.
- Live request logs contained only expected `2xx` records and no runtime errors.
- Smoke user and auth-throttle cleanup - passed; both residual counts were zero.
- API health returned the exact expected payload and the live frontend returned
  HTTP `200`.
- Final whitespace, generated-route, forbidden-dependency, and service-health
  checks passed.

Lifecycle posture:
- Forget is reversible and removes a memory from cognition; Delete is permanent.
- Forgotten rows remain private owner data and are included in export so fading
  never silently destroys continuity.
- Re-learning is intentional evidence that a faded memory matters again, so it
  revives the original row with source and lifecycle history intact.

## World-class continuation - strict access-token trust boundary

Completed in this checkpoint:
- Responded to a real PyJWT short-HMAC-key runtime warning by enforcing
  `JWT_SECRET` at 32-4096 UTF-8 bytes in development, testing, and production.
- Changed the setting to Pydantic `SecretStr` so settings representations mask
  the signing key; validation errors report only the variable/bound, never value
  or prefix.
- Added production rejection for the repository placeholder, common replacement
  markers, and obviously low-diversity values.
- Added complete HS256 access-token claims: issuer `eidolon-api`, audience
  `eidolon-web`, type `access`, issued-at, not-before, expiry, user subject UUID,
  and unique token UUID.
- Required every claim during decode, restricted algorithms to HS256, validated
  token/subject UUIDs and semantic issuer/audience/type, and bounded clock skew
  to five seconds.
- Routed auth-throttle HMAC fingerprints through the same explicit unwrapped,
  validated signing key without exposing it through general settings output.
- Added deterministic tests for ASCII/multibyte byte boundaries, upper bounds,
  masked representation, production marker/diversity rejection, complete token
  round-trip, every missing claim, semantic mismatch, expiry/future timing,
  invalid UUIDs, wrong key, wrong algorithm, and malformed compact tokens.
- Preserved register/login, refresh rotation, and login-throttle behavior in
  focused endpoint tests.
- Updated README, environment example, architecture, API, deployment, testing,
  and progress documentation with generation and rotation behavior.

Validation completed:
- Focused configuration/token/auth flow run - passed; 18 tests, including
  refresh-session continuity across signing-key rotation.
- Focused Ruff checks and formatting - passed.
- `cd apps/api && pytest` - passed; 151 tests.
- `cd apps/api && ruff check . && ruff format . && ruff check .` - passed;
  63 files remained formatted and the second lint pass was clean.
- `git diff --check` - passed.
- Verified the ignored 22-byte API env is rejected by `Settings()` with all
  output suppressed; its value was neither printed nor modified.
- Restarted the API under generated key A (`openssl rand -hex 32`) and completed
  registration without any PyJWT short-key warning.
- Live two-process rotation smoke - passed: after restart under independently
  generated key B, the old access token returned `401`, the unchanged HttpOnly
  refresh cookie returned `200`, and its new access token authenticated with
  `200` for the expected account.
- Live server logs contained only expected request records and no HMAC key-length
  warning after hardening.
- Smoke user and auth throttle cleanup - passed; both residual counts were zero.
- Final secret-reference, placeholder, forbidden-dependency, whitespace,
  generated-route-reference, schema-head, and service-health scans passed.

Rotation posture:
- Rotating `JWT_SECRET` intentionally invalidates all access tokens immediately.
- Opaque refresh tokens are independently generated and hashed in PostgreSQL, so
  valid refresh cookies can rotate and receive newly signed access tokens.
- Old auth-throttle HMAC rows become unreachable after rotation and age out via
  the existing bounded retention cleanup.
- The ignored local API env was found to contain a 22-byte development key. It
  was not printed or modified; the validated live server will use a generated
  process-level override.

## World-class continuation - truthful private generation context

Completed in this checkpoint:
- Removed character Debug's fabricated prompt built from an empty history and
  literal `debug preview` message; Debug no longer returns raw prompt text.
- Extended central prompt assembly with a JSON-safe manifest of character ID,
  qualitative relationship posture, selected memory/journal IDs and types,
  continuity-signal labels, recent roles/privacy modes, safety posture, time,
  and current-message length without storing raw state or message prose.
- Recorded provider, generation kind, prompt version/size, assembly time, bounded
  response-plan summary, and manifest on the exact triggering user turn.
- Covered ordinary chat, SSE, reroll, and edited-turn regeneration; SSE commits
  attempted context before provider streaming while transactional failures keep
  the previous committed context.
- Added a defensive `MessageOut` filter for all underscore-prefixed private
  metadata so context cannot leak through chat, stream, history, edit, reroll,
  search, or Debug recent-message payloads.
- Added owner-scoped latest-context selection by actual assembly time so rerolls
  of older turns can still become the truthful latest generation.
- Added strict Debug sanitization for schema version, timestamp, generation kind,
  provider/version labels, mode, UUIDs, nested whitelist, list sizes, prompt
  length, message length, and response-plan length; malformed rows are skipped.
- Replaced the frontend prompt dump with Last Assembled Context, actual response
  plan, selected type/role/safety summaries, and a separate Current Retrieval
  snapshot.
- Updated architecture, API, prompt assembly, frontend, testing, and progress
  documentation.

Validation completed:
- Focused chat/SSE/reroll/edit/context tests - passed; 10 tests after correcting
  a test-only SQLAlchemy nested-JSON mutation.
- Full affected auth/chat/continuity/prompt set - passed; 64 tests.
- Focused Ruff checks and formatting - passed.
- `cd apps/web && npm run lint` - passed.
- `cd apps/api && pytest` - passed; 145 tests.
- `cd apps/api && ruff check . && ruff format . && ruff check .` - passed;
  62 files remained formatted and the second lint pass was clean.
- `cd apps/web && npm run build` - passed; compilation, TypeScript, page data,
  and all five static pages completed successfully.
- Restored `apps/web/next-env.d.ts` to the development route reference after the
  production build and restarted the Next dev server on port 3000.
- Restarted the API with the scheduler disabled on port 8000.
- Live authenticated context smoke - passed: PostgreSQL user-message metadata
  contained `_prompt_context`, its serialized value did not contain the marker
  prose, chat/history both omitted the private key, conversation Debug reported
  generation kind `chat` without marker prose, and character Debug omitted
  `prompt_preview`.
- Live smoke user and auth throttle cleanup - passed; both residual counts were
  verified at zero.
- `cd apps/api && alembic current` - reported `0006_auth_throttles (head)`; an
  initial repository-root invocation lacked Alembic's script location and was
  rerun from the correct application directory.
- Final generated-file, stale-preview, private-key boundary, forbidden
  dependency, placeholder, whitespace, and service-health scans passed.

Privacy and state posture:
- Response-plan summary remains private Debug data and may contain bounded
  continuity wording; raw prompt, current-message prose, memory content, and
  journal summary are excluded from the manifest.
- Export remains a private account backup and may include internal persisted
  metadata, but that metadata contains the safe manifest rather than prompt text.
- Threads without a valid recorded assembly show no last context instead of a
  generated approximation.

## World-class continuation - bounded account creation work

Completed in this checkpoint:
- Generalized migration-backed throttle storage from `login_throttles` to
  `auth_throttles` through forward revision `0006_auth_throttles`, preserving
  existing rows while renaming the table, primary/check constraints, and index.
- Added an independent registration-client HMAC scope so signup activity cannot
  consume or reset login identity/client limits.
- Checked active registration blocks before Argon2 and durably counted every
  request allowed to reach hashing before user creation begins.
- Kept accounting after successful registration and duplicate-email rollback so
  random unique accounts or predictable conflicts cannot reopen costly work.
- Kept schema-invalid and untrusted-Origin requests outside the counter because
  they are rejected before the route's hashing boundary.
- Allowed the configured number of costly requests to complete, then returned a
  generic `429` with integer `Retry-After` before hashing subsequent requests.
- Added bounded `REGISTRATION_MAX_ATTEMPTS`,
  `REGISTRATION_ATTEMPT_WINDOW_SECONDS`, and `REGISTRATION_BLOCK_SECONDS`
  settings with five attempts/15 minutes/15 minutes as defaults.
- Preserved HMAC-only persistence, stale-window reset/cleanup, direct ASGI client
  use, and no raw attempted identity/address in database or export state.
- Added regressions for pre-hash blocking, duplicate rollback persistence,
  validation/origin exclusion, expiry recovery, privacy, scope isolation,
  bounded settings, schema rename, and parallel account creation.
- Updated README, architecture, data model, API contract, testing, environment,
  and progress documentation.

Validation completed:
- `cd apps/api && alembic upgrade head` - passed; upgraded from revision `0005`
  to `0006_auth_throttles`.
- Focused registration/login/configuration/migration run - passed; 34 tests.
- Focused Ruff check/fix and formatting - passed.
- `cd apps/api && pytest` - passed; 144 tests.
- `cd apps/api && ruff check . && ruff format . && ruff check .` - passed;
  62 files remained formatted and the second lint pass was clean.
- `git diff --check` - passed.
- Migration round-trip with a sentinel row - passed: downgrade exposed revision
  `0005_login_throttles`, table `login_throttles`, and attempt count `3`; upgrade
  restored revision `0006_auth_throttles`, table `auth_throttles`, and the same
  attempt count before cleanup.
- `alembic current` - reported `0006_auth_throttles (head)`; the legacy table was
  absent and the auth throttle table had zero rows after validation cleanup.
- Restarted the API with the scheduler disabled for local development; live
  `/health` returned the exact healthy payload.
- Live registration smoke returned `201` for five real account creations, then
  generic `429` with `Retry-After: 900` on request six. Login for one created
  account still returned `200` during the registration block, proving scope
  separation. Smoke users and throttle rows were removed and verified at zero.
- PostgreSQL remained healthy and the live frontend returned `200` with the
  generated Next route reference unchanged.
- Forbidden dependency, placeholder, stale model/table-name, and repository
  whitespace scans passed; no runtime dependency was added.

Operational posture:
- Registration and login use distinct HMAC scopes but share one small operational
  table and lock implementation.
- Registration counting is intentionally not cleared by successful signup; that
  would let unique-account creation bypass the CPU boundary.
- The short client-wide block can affect legitimate users sharing one apparent
  address, so defaults are bounded and configurable within strict limits.

## World-class continuation - privacy-preserving login throttling

Completed in this checkpoint:
- Added PostgreSQL-backed rejected-login limits across both canonical email and
  ASGI client host, checked before Argon2 once a block is active.
- Stored only scoped HMAC-SHA256 fingerprints keyed by the runtime JWT secret;
  attempted email and client-address text never enters the throttle table.
- Serialized both fingerprint keys with sorted transaction advisory locks so
  parallel API processes cannot race through the configured threshold.
- Kept unknown users, bad passwords, and malformed stored hashes on the same
  generic failure path, with the threshold-triggering request and active blocks
  returning generic `429` plus a bounded integer `Retry-After`.
- Cleared matching failures on successful authentication, reset elapsed windows,
  and pruned old operational rows during committed rejected-login traffic.
- Added strictly bounded attempt, window, and block settings plus documented
  defaults in `.env.example`; no dependency or external service was added.
- Added Alembic revision `0005_login_throttles` and model/schema checks.
- Added endpoint regressions for known-account blocking, correct-password
  lockout, expiry recovery, successful reset, rotating-email client limits,
  canonical fingerprints, raw-value non-persistence, and concurrent requests.
- Updated README, architecture, data model, API contract, testing, and progress
  documentation.

Validation completed:
- `cd apps/api && alembic upgrade head` - passed; upgraded from revision `0004`
  to `0005_login_throttles`.
- Focused auth, configuration, and migration regression run - passed; 14 tests.
- Focused Ruff check/fix and formatting - passed.
- `cd apps/api && pytest` - passed; 140 tests.
- `cd apps/api && ruff check . && ruff format . && ruff check .` - passed;
  61 files remained formatted and the second lint pass was clean.
- `alembic current` - reported `0005_login_throttles (head)`.
- `git diff --check` - passed.
- PostgreSQL container check - healthy.
- Restarted the API with the scheduler disabled for local development; live
  `/health` returned the exact healthy payload.
- Live unknown-account login smoke returned `401` for attempts one through four,
  `429` on attempt five and the blocked follow-up, generic response text, and
  `Retry-After: 900`; smoke throttle rows were then removed and the table count
  verified as zero.
- Live frontend smoke at `http://127.0.0.1:3000` returned `200` with the existing
  private-shell security headers.
- Forbidden dependency, placeholder, generated route-reference, and repository
  whitespace scans passed; no runtime dependency was added.

Security posture and limits:
- The throttle intentionally uses `request.client.host` as supplied by the ASGI
  runtime and does not trust caller-controlled forwarding headers itself.
- A global per-identity limit can briefly block a legitimate account after
  targeted failures; the default block is bounded to 15 minutes and a correct
  login succeeds after expiry.
- Throttling protects login password verification. Registration remains governed
  by request validation and deployment-level request controls rather than this
  login-specific table.

## World-class continuation - private standalone web shell

Completed in this checkpoint:
- Added a typed Next metadata surface with a private application identity,
  standalone manifest link, SVG browser icon, dark theme, and no-referrer policy.
- Added explicit viewport-fit cover, visual-keyboard content resizing, dark color
  scheme, and an accessible initial scale without disabling user zoom.
- Added a generated standalone manifest with stable app identity/scope, existing-
  window launch behavior, dark background/theme, and separate any/maskable uses
  of one tiny code-native brand mark.
- Added a disallow-all `robots.txt` route plus document-level noindex, nofollow,
  noarchive, nosnippet, noimageindex, and nocache metadata for the private app.
- Added horizontal device-safe insets, top header/auth insets, bottom auth/composer
  insets, dynamic viewport chat height, and standalone-like overscroll behavior.
- Added no-referrer, anti-framing, MIME-sniffing, same-origin opener/resource,
  cross-domain-policy, and unused browser capability response headers.
- Kept camera, microphone, geolocation, payment, USB, and browsing-topics disabled
  because the text-only product has no workflow that should request them.
- Deliberately omitted a service worker and offline API cache so private tokens,
  conversations, memories, and continuity remain online, server-owned state.
- Updated README, architecture, stack, frontend, testing, and progress docs.

Commands run:
- `npm run lint` from `apps/web` - passed.
- `npm run build` from `apps/web` - passed; TypeScript and static `/`,
  `/_not-found`, `/manifest.webmanifest`, and `/robots.txt` generation completed.
- Restarted `npm run dev -- --port 3000`; the frontend is live with the updated
  Next configuration.
- Parsed live manifest JSON and verified standalone identity, start URL, and both
  icon purposes.
- Verified live robots denial, icon/manifest MIME types, SVG XML structure,
  viewport/theme/private metadata, and all configured response headers.
- Restored and verified `apps/web/next-env.d.ts` after the production build.

Known limitations:
- Browser screenshot tooling and an SVG rasterizer are unavailable in this
  Codespace. The simple path-based mark passed XML, MIME, dimensions, manifest,
  and source inspection but not a rendered screenshot regression.
- Standalone metadata does not make Eidolon offline-capable; chat intentionally
  still requires its authenticated backend and PostgreSQL source of truth.

## World-class continuation - truthful fail-closed content mode

Completed in this checkpoint:
- Bound every frontend adult-readiness result to the exact character ID used by
  its request instead of retaining an unscoped status object.
- Cleared prior readiness immediately when a different character begins loading
  and discarded stale overlapping results through the existing refresh version.
- Made a failed adult-status request clear readiness and notify the controller so
  requested Adult state cannot reactivate after a transient failure.
- Derived effective mode from current account age gate, current profile age and
  permission, matching character-bound backend readiness, and allowed status.
- Replaced the raw mode setter with a guarded transition that stays Safe while
  readiness loads, surfaces the first bounded backend gate reason when blocked,
  and leaves hard boundaries explicit when Adult activates.
- Reset requested mode at the navigation ownership boundary on character changes
  while preserving it for same-character thread transitions and profile saves.
- Reset newly blocked same-character state from the async readiness completion
  callback without a render-cascading React effect.
- Froze content-mode controls during busy/send state so an in-flight request and
  the shell cannot disagree about the mode attached to that turn.
- Added a visible `Adult locked` state with contextual accessible labels; blocked
  or loading attempts open the Adult panel and switch mobile to Companion.
- Distinguished readiness loading from request failure so a failed check explains
  that Safe remains active instead of displaying an indefinite checking state.
- Made account/profile eligibility changes fail closed before the refreshed
  status arrives, and made account updates catch request plus partial-refresh
  failures without unhandled promises or falsely claiming persistence failed.
- Updated product, safety, frontend, testing, and progress documentation.

Commands run:
- `npm run lint` from `apps/web` - passed after moving character reset out of a
  rejected synchronous effect and into navigation ownership.
- `npm run build` from `apps/web` - passed; TypeScript and static `/` plus
  `/_not-found` generation completed after correcting a misplaced readiness prop
  caught by the first final type-check pass.
- Restored and verified `apps/web/next-env.d.ts` after the production build.
- Character-provenance, fail-closed derivation, guarded-transition, navigation
  reset, send-lock, stale raw-setter, forbidden dependency, placeholder/secret,
  and `git diff --check` source audits - passed.
- Live frontend `/` returned HTTP 200 and API `/health` returned the exact payload.

Known limitations:
- Browser screenshot automation remains unavailable in this Codespace, so the
  state/race validation is TypeScript, lint, production build, live HTTP, and
  explicit source-invariant based rather than an end-to-end browser interaction.

## World-class continuation - hardened account identity boundary

Completed in this checkpoint:
- Added dependency-free canonical email validation for bounded ASCII mailbox
  syntax, dot-qualified domains, label length/shape, repeated dots, and malformed
  separators before database lookup or persistence.
- Canonicalized registration and login email case/whitespace so equivalent
  identities share one uniqueness boundary.
- Normalized optional display names by collapsing whitespace, mapping blank input
  to `null`, and rejecting control or invisible format characters.
- Raised the new-account passphrase minimum to 12 characters, retained the
  existing 256-character bound, rejected whitespace-only passphrases, and kept
  login compatible with already-created passwords.
- Made unknown-account login run one Argon2 verification against a fixed dummy
  hash before returning the same generic `401` used for an incorrect password.
- Made malformed stored Argon2 hashes fail closed with the same generic response
  instead of risking an internal server error.
- Mirrored the registration length constraint with native browser validation and
  an associated accessible requirement label while keeping the API authoritative.
- Added regressions for canonical login, canonical duplicate detection, blank and
  normalized names, malformed addresses, short/blank passphrases, invisible name
  characters, unknown-account verification, and corrupt stored hashes.
- Updated product, architecture, API, frontend, testing, and progress docs.

Commands run:
- `docker compose up -d postgres` - passed.
- `pip install -e ".[dev]"` and `alembic upgrade head` from `apps/api` - passed.
- `pytest tests/test_auth_chat.py -q` from `apps/api` - passed; 17 tests.
- `pytest -q` from `apps/api` - passed; 135 tests.
- `ruff check .`, `ruff format .`, and a post-format `ruff check .` from
  `apps/api` - passed; 59 files unchanged.
- `npm run lint` and `npm run build` from `apps/web` - passed; TypeScript and
  static `/` plus `/_not-found` generation completed.
- Restored `apps/web/next-env.d.ts` to the checked-in development route reference.
- Live API/frontend smoke - `/health` returned the exact payload, malformed
  registration returned `422`, unknown login returned the generic `401`, and
  frontend `/` returned HTTP 200.

Known limitations:
- Internationalized email addresses are intentionally unsupported in this
  zero-dependency MVP; users must enter the ASCII/punycode form of an address.
- Dummy verification removes the large missing-account Argon2 difference but
  cannot make database lookup, scheduling, and network timing perfectly equal.

## World-class continuation - private brand-first entry

Completed in this checkpoint:
- Replaced the generic centered auth card with a full-viewport, brand-first,
  responsive text composition that remains restrained on mobile and desktop.
- Kept the entry strictly text-only, using no images, gradients, multimedia,
  client-heavy effects, or decorative animation.
- Added an unframed semantic form with labeled fields, accessible segmented auth
  modes, polite live status, a checkbox password-visibility control, and disabled
  mode/submit actions while a request is active.
- Made auth-mode transitions clear password, error, and notice state without
  discarding a non-sensitive email draft.
- Cleared password state immediately after successful authentication and on every
  logout or expired-session reset.
- Reset login mode, display name, and content mode to SFW when account state is
  cleared so one session cannot leak UI posture into the next.
- Matched the private session-opening screen to the entry identity and added dark
  autofill treatment plus system-wide reduced-motion fallbacks.
- Updated product, frontend, testing, and progress documentation.

Commands run:
- `npm run lint` from `apps/web` - passed.
- `npm run build` from `apps/web` - passed after the final auth-state changes;
  static `/` and `/_not-found` routes compiled.
- Restored and verified `apps/web/next-env.d.ts` after the Next.js build.
- `npm run dev -- --port 3000` from `apps/web` - ready at
  `http://localhost:3000`.
- Live `GET /` - returned HTTP 200 with the private session-opening content.
- Auth source invariants, stale-copy rejection, forbidden dependency scan,
  placeholder/secret scan, and `git diff --check` - passed.

Known limitations:
- This Codespace has no Chromium, Playwright, or Puppeteer browser binary, so a
  rendered screenshot regression was unavailable. Validation used TypeScript,
  lint, production build, live HTTP output, and source-level responsive and
  accessibility invariants.

## World-class continuation - persona-aware typing cadence

Completed in this checkpoint:
- Added deterministic mock cadence profiles for initial composing delay, natural chunk size, ordinary token interval, and punctuation pause.
- Derived pace only from exact authored speech-style words and final response length, with measured/reflective and brisk/direct profiles plus a neutral default.
- Made missing, conflicting, and substring-only style cues resolve safely without false classification.
- Bounded every delay and chunk target so authored style cannot create a long stall or burst unreadable text.
- Preserved generated text, SSE event ordering, final message persistence, thread ownership, and cancellation behavior.
- Added provider regressions for slow versus fast voice, short versus long output, conflicting and empty style, substring safety, bounds, punctuation pauses, chunk reconstruction, and unchanged text.
- Updated prompt, frontend streaming, testing, and progress documentation.

Commands run:
- `docker compose up -d postgres` - passed; PostgreSQL was already running.
- `alembic upgrade head` from `apps/api` - passed.
- `pytest tests/test_llm_providers.py tests/test_auth_chat.py -q` from `apps/api` - passed; 31 tests.
- `pytest -q` from `apps/api` - passed; 133 tests.
- `ruff check .` and `ruff format --check .` from `apps/api` - passed; 59 files already formatted.

Known limitations:
- Cadence recognizes a bounded set of exact English speech-style words; unrecognized or contradictory authoring deliberately uses the neutral profile.
- Ollama token timing remains provider-driven, while the same client composing, streaming, stale-event, and cancellation lifecycle still applies.

## World-class continuation - relationship-aware proactive presence

Completed in this checkpoint:
- Reduced backend-owned relationship state to bounded new, warming, trusted, close, careful, or repair postures with non-finite metrics defaulting safely.
- Rechecked relationship posture when proactive jobs are queued and again immediately before a message is generated.
- Suppressed delayed double-texts and milestone celebrations during careful or repair states so queued warmth cannot become pressure after later tension.
- Recorded relationship-suppressed due work as a bounded `skipped_by_relationship_state` outcome without writing a proactive message.
- Made remaining careful/repair check-ins use spacious authored SFW copy and omit unresolved-thread excerpts.
- Added qualitative posture guidance to the isolated proactive prompt without scores, raw relationship metadata, private history, or adult context.
- Made the mock provider and provider-unavailable fallback honor the same relationship-aware safe anchor.
- Rejected generated posture-label leakage and persisted only the bounded posture key in message and completed-job metadata.
- Added focused tests for all posture bands, malformed metrics, prompt score non-disclosure, queue and delivery suppression, fallback behavior, and scheduler provenance.
- Updated prompt, relationship, background-job, API, testing, and progress documentation.

Commands run:
- `docker compose up -d postgres` - passed; PostgreSQL was already running.
- `alembic upgrade head` from `apps/api` - passed.
- Focused proactive relationship/provider/scheduler regressions - passed; 60 tests.
- `pytest -q` from `apps/api` - passed; 132 tests.
- `ruff check .` and `ruff format --check .` from `apps/api` - passed; 59 files already formatted.

Known limitations:
- Posture selection is intentionally deterministic and coarse rather than LLM-classified; this keeps relationship ownership inspectable and prevents background emotional inference from creating pressure.

## World-class continuation - pgvector-backed hybrid memory recall

Completed in this checkpoint:
- Added deterministic normalized 384-dimensional local feature embeddings with no runtime service, model, or dependency cost.
- Added defensive PostgreSQL vector bind/result handling that rejects wrong-sized, malformed, boolean, and non-finite vectors.
- Generated embeddings for manual/extracted memories, dedupe merges, content edits, user-saved memory updates, and relationship milestone anchors.
- Combined PostgreSQL `<=>` nearest-vector candidates with pinned/recent candidates before keyword, vector, recency, importance, confidence, emotional weight, relationship, contradiction, and decay ranking.
- Lazily backfilled legacy null vectors during recall without exposing raw embeddings through API schemas.
- Added regression coverage for determinism, normalization, malformed input, related phrases without shared keywords, content-edit recomputation, legacy backfill, API non-disclosure, zero-signal query fallback, and an older relevant memory outside the 100-row recency cohort.
- Updated architecture, data model, memory, testing, roadmap, and progress documentation.

Commands run:
- `docker compose up -d postgres` - passed; PostgreSQL was already running.
- `alembic upgrade head` from `apps/api` - passed.
- Focused embedding lifecycle regressions - passed; 4 tests.
- Focused embedding plus prompt/memory/relationship regressions - passed; 21 tests.
- `pytest -q` from `apps/api` - passed; 122 tests.
- `ruff check .` and `ruff format --check .` from `apps/api` - passed; 58 files already formatted.

Known limitations:
- The local encoder is a lightweight feature hash with bounded concept aliases, not a multilingual neural semantic model. Its `vector(384)` storage contract can be replaced by a higher-fidelity local encoder later.
- Nearest-vector selection currently uses an exact pgvector scan, which is appropriate for the personal MVP; a future large dataset would need an HNSW/IVFFlat index and an explicit full legacy-vector backfill command.

## World-class continuation - contextual proactive generation with safe fallback

Completed in this checkpoint:
- Added local-provider generation for eligible proactive notes after all privacy, staleness, local-time, user-control, context, and cooldown guards pass.
- Built a separate bounded SFW proactive prompt from only character name, screened speech style, note label, and an already-safe variant/context anchor.
- Rejected empty, non-string, oversized, non-SFW-labeled, structurally blocked, credential-like, and hidden-prompt output without persisting rejected text.
- Preserved deterministic type-aware SFW copy when the provider is unavailable, errors unexpectedly, or returns invalid output.
- Added safe `llm`/`fallback` generation provenance to proactive message metadata and completed job payloads without storing provider exception details.
- Extended the mock provider with natural deterministic proactive variants so offline development and tests exercise the generated path.
- Strengthened scheduler coverage for successful generation, provider unavailability, hidden-context output, malformed output, and abstract non-SFW output.
- Updated background-job, prompt, API, testing, and progress documentation.

Commands run:
- Focused proactive generation and fallback regressions - passed; 5 cases.
- `ruff check` and `ruff format --check` for the five touched backend/test files - passed; 5 files already formatted.
- `pytest tests/test_jobs_proactive_export.py -q` from `apps/api` - passed; 35 tests.
- `pytest tests/test_llm_providers.py -q` from `apps/api` - passed; 15 tests.
- `pytest` from `apps/api` - passed; 118 tests.
- `ruff check .` and `ruff format --check .` from `apps/api` - passed; 56 files already formatted.
- `git diff --check` - passed.
- Forbidden dependency manifest scan - passed.
- Secret pattern scan - passed.
- `git diff --exit-code -- apps/web/next-env.d.ts` - passed.

Known limitations:
- Proactive generation runs inside the claimed job transaction; eligibility and cooldown checks ensure at most one deliverable variant reaches inference in a cooldown window, but slow local Ollama inference extends that job row's lock duration.
- SFW output screening is deterministic structural defense rather than a separate moderation model; rejected or uncertain output falls back to authored SFW copy.

## World-class continuation - scoped chat wipe continuity cleanup

Completed in this checkpoint:
- Made clear-chat delete the owned thread's message rows, conversation-local episodic journals, and queued jobs in one transaction.
- Serialized cleanup on the owned conversation row and refreshed its update timestamp while retaining the empty room.
- Cancelled active browser streams before clear-chat and made assistant completion lock/revalidate its source turn so delayed inference cannot repopulate a wiped room.
- Preserved sibling-thread messages, journals, and queued jobs as well as separately managed durable memories and character-level relationship history.
- Strengthened the existing clear/reroll regression with sibling-thread and durable-memory isolation checks, plus a deterministic delayed-completion cancellation regression.
- Added explicit Data panel scope copy and a completion notice so destructive behavior is understandable before and after the action.
- Reset draft, edit, one-turn privacy, stream, and sending state after a successful wipe so no UI state points at deleted rows.
- Updated API, privacy, frontend UX, acceptance, and progress documentation.

Commands run:
- Focused scoped clear-chat and delayed-completion cancellation regressions - passed; 2 tests.
- `ruff check app/api/chat.py app/services/chat.py app/api/conversations.py tests/test_level2_state.py` from `apps/api` - passed.
- `ruff format --check app/api/chat.py app/services/chat.py app/api/conversations.py tests/test_level2_state.py` from `apps/api` - passed after formatting the completion guard; 4 files already formatted.
- `pytest tests/test_level2_state.py -q` from `apps/api` - passed; 22 tests.
- `pytest` from `apps/api` - passed; 114 tests.
- `ruff check .` and `ruff format --check .` from `apps/api` - passed; 56 files already formatted.
- `npm run lint` from `apps/web` - passed.
- `npm run build` from `apps/web` - passed; static `/` and `/_not-found` routes compiled.
- `git diff --check` - passed.
- Forbidden dependency manifest scan - passed.
- Secret pattern scan - passed.
- `git diff --exit-code -- apps/web/next-env.d.ts` - passed after restoring the generated dev-route reference.

Known limitations:
- Clear chat intentionally retains durable memories and character-level relationship history; both are companion-wide state with separate destructive controls rather than thread-local derivatives.

## World-class continuation - companion-message deletion cleanup

Completed in this checkpoint:
- Made companion and proactive message deletion remove source-linked memory references before deleting the source row.
- Extended latest-user-turn deletion to remove memory references sourced from dependent companion replies as well as the deleted user line.
- Cleared and deterministically rebuilt conversation-local journals from surviving safe messages so deleted reply text cannot remain in episode continuity.
- Replaced stale conversation jobs only when the surviving latest state is a normal, non-private, non-adult, non-proactive companion reply.
- Kept latest-reply deletion quiet when the thread ends on a user line, while preserving valid older state when a newer complete exchange remains.
- Kept the entire cleanup and rebuild under the existing owned-conversation lock and single commit so failures cannot persist partial cleanup.
- Preserved row-only deletion for trusted system event cards, which are already excluded from durable cognition.
- Added regressions for older-reply reconstruction and latest-reply no-requeue behavior, and updated API/testing docs.

Commands run:
- Focused companion-message and dependent-reply deletion regressions - passed; 3 tests.
- `ruff check app/api/conversations.py tests/test_level2_state.py` from `apps/api` - passed.
- `ruff format --check app/api/conversations.py tests/test_level2_state.py` from `apps/api` - passed after formatting the new test block; 2 files already formatted.
- `pytest tests/test_level2_state.py -q` from `apps/api` - passed; 21 tests.
- `pytest` from `apps/api` - passed; 113 tests.
- `ruff check .` and `ruff format --check .` from `apps/api` - passed; 56 files already formatted.
- `git diff --check` - passed.
- Forbidden dependency manifest scan - passed.
- Secret pattern scan - passed.
- `git diff --exit-code -- apps/web/next-env.d.ts` - passed.

Known limitations:
- Deleting a companion reply intentionally does not reverse the relationship effect sourced from its surviving user message; the user interaction still occurred even though that specific generated reply was removed.

## World-class continuation - guarded proactive rebuild after turn deletion

Completed in this checkpoint:
- Rebuilt proactive jobs after latest-user-turn deletion only when the remaining latest state is a normal, non-private, non-proactive companion reply.
- Kept empty threads, private threads/turns, adult-mode remnants, proactive-note endings, and user-ending remnants from requeueing presence jobs.
- Preserved the stale-job cleanup guarantee by deleting old queued jobs before guarded rebuild in the same transaction.
- Strengthened regressions to prove fresh job ids replace stale ones after safe deletion and that deleting the only turn leaves no queued jobs.
- Updated API, testing, and progress docs for the guarded post-delete scheduling contract.

Commands run:
- Focused safe-rebuild and empty-thread deletion regressions - passed; 2 tests.
- `pytest tests/test_level2_state.py -q` from `apps/api` - passed; 19 tests.
- `pytest` from `apps/api` - passed; 111 tests.
- `ruff check .` and `ruff format --check .` from `apps/api` - passed; 56 files already formatted.
- `git diff --check` - passed.
- Forbidden dependency manifest scan - passed.
- Secret pattern scan - passed.
- `git diff --exit-code -- apps/web/next-env.d.ts` - passed.

Known limitations:
- Guarded rebuild intentionally requires an assistant-ending remaining thread; user-ending or proactive-note-ending remnants stay quiet until a new user/assistant exchange creates fresh scheduling context.

## World-class continuation - journal-preserving latest-turn deletion

Completed in this checkpoint:
- Rebuilt the conversation journal after latest-user-turn deletion using the existing deterministic journal summarizer.
- Preserved valid older episode continuity when a newer turn is deleted, while still removing deleted-turn memory, relationship effects, stale assistant replies, stale queued jobs, and stale journal text.
- Kept the deletion operation transactional so a failed journal rebuild cannot commit a half-cleaned state.
- Strengthened regression coverage to prove the remaining journal keeps the older safe exchange and excludes deleted-turn details.
- Updated API, testing, and progress docs for the refined journal semantics.

Commands run:
- Focused latest-turn deletion journal rebuild regression - passed; 1 test.
- `ruff check app/api/conversations.py tests/test_level2_state.py` from `apps/api` - passed.
- `ruff format --check app/api/conversations.py tests/test_level2_state.py` from `apps/api` - passed; 2 files already formatted.
- `pytest tests/test_level2_state.py -q` from `apps/api` - passed; 18 tests.
- `pytest` from `apps/api` - passed; 110 tests.
- `ruff check .` and `ruff format --check .` from `apps/api` - passed; 56 files already formatted.
- `npm run lint` from `apps/web` - passed.
- `npm run build` from `apps/web` - passed.
- `git diff --check` - passed.
- Forbidden dependency manifest scan - passed.
- Secret pattern scan - passed.
- `git diff --exit-code -- apps/web/next-env.d.ts` - passed.

Known limitations:
- Latest-turn deletion still clears queued proactive jobs instead of rebuilding new jobs from the remaining thread; this avoids stale scheduled notes until a guarded post-delete scheduling path is added.

## World-class continuation - latest-turn deletion cleanup

Completed in this checkpoint:
- Changed user-authored message deletion from a raw row delete into latest-user-turn deletion that also removes dependent companion replies.
- Rejected older user-turn deletion with `409` so the backend cannot leave stale replies, cognition, or relationship state behind.
- Reversed source-linked relationship effects for deleted non-private user turns and removed source-linked memories, stale conversation-local journals, and queued jobs.
- Kept assistant, proactive, and system-message deletion as single-message cleanup.
- Hid user-delete controls on older turns and removed dependent companion replies from local chat state after backend acceptance.
- Documented the safer delete semantics in API, UX, testing, and progress docs.

Commands run:
- `ruff check app/api/conversations.py tests/test_level2_state.py` from `apps/api` - passed.
- `ruff format tests/test_level2_state.py` from `apps/api` - applied mechanical wrapping.
- `ruff format --check app/api/conversations.py tests/test_level2_state.py` from `apps/api` - passed; 2 files already formatted.
- Focused latest-turn deletion cleanup regression - passed; 1 test.
- `pytest tests/test_level2_state.py -q` from `apps/api` - passed; 18 tests.
- `npm run lint` from `apps/web` - passed.
- `npm run build` from `apps/web` - passed.
- `pytest` from `apps/api` - passed; 110 tests.
- `ruff check .` and `ruff format --check .` from `apps/api` - passed; 56 files already formatted.
- `git diff --check` - passed.
- Forbidden dependency manifest scan - passed.
- Secret pattern scan - passed.
- `git diff --exit-code -- apps/web/next-env.d.ts` - passed.

Known limitations:
- Relationship reversal applies to new effect-bearing turns. Legacy user messages without relationship-effect metadata still delete safely but cannot subtract an unknown historical delta.

## World-class continuation - reversible relationship edits

Completed in this checkpoint:
- Stored compact `relationship_effect` metadata on new stateful user turns, including exact metric deltas, added tags, source message id, repair posture, and milestone ids.
- Added relationship-effect reversal for latest-turn edits so the old turn's emotional delta is subtracted before the revised turn is applied.
- Removed timeline and relationship-milestone memory entries tied to the edited source message when reversing effect-bearing turns.
- Preserved private-turn behavior; private messages still do not create relationship effects.
- Kept legacy safety: if a turn has no effect metadata, editing does not guess a reversal and records that recalculation was unavailable.
- Added regression coverage for editing a tense latest turn into a warm one, proving tension/repair state and tags are recalculated.
- Documented relationship-effect metadata in the API contract, data model, relationship engine, testing acceptance, and progress log.

Commands run:
- Focused relationship edit recalculation regression - passed; 1 test.
- Focused latest-turn edit regressions - passed; 2 tests.
- `pytest tests/test_level2_state.py -q` from `apps/api` - passed; 17 tests.
- `ruff check app/services/relationship.py app/services/chat.py tests/test_level2_state.py` from `apps/api` - passed.
- `ruff format app/services/relationship.py` from `apps/api` - applied mechanical formatting.
- `ruff format --check app/services/relationship.py app/services/chat.py tests/test_level2_state.py` from `apps/api` - passed; 3 files already formatted.
- `pytest` from `apps/api` - passed; 109 tests.
- `ruff check .` and `ruff format --check .` from `apps/api` - passed; 56 files already formatted.
- Live disposable-account reversible relationship edit smoke - passed for effect storage, relationship reversal, recalculated metrics/tags, and account cleanup.

Known limitations:
- Relationship recalculation is available for new effect-bearing turns. Legacy messages created before this metadata existed still use the safe no-guess fallback when edited.

## World-class continuation - user-paced proactive cooldown

Completed in this checkpoint:
- Added a `proactive_cooldown_hours` draft field with a 1-168 hour range and a 24-hour default for existing profiles.
- Exposed minimum-hours-between-notes controls in both the four-stage companion builder and later Persona editing.
- Persisted the setting as `boundaries_json.proactive_preferences.cooldown_hours` instead of hard-coding 24 hours in the frontend.
- Added backend profile validation so direct create/update requests reject malformed, boolean, too-low, or too-high cooldown values.
- Updated pending proactive job rescheduling so saved preference changes copy the current cooldown into job payloads.
- Documented cooldown behavior in the API contract, data model, background jobs, frontend UX, testing acceptance, and progress log.

Commands run:
- Focused proactive cooldown/profile tests - passed; 2 tests.
- `pytest tests/test_prompt_memory_relationship.py tests/test_jobs_proactive_export.py -q` from `apps/api` - passed; 48 tests.
- `ruff check app/schemas.py app/services/proactive.py tests/test_prompt_memory_relationship.py tests/test_jobs_proactive_export.py` from `apps/api` - passed.
- `ruff format --check app/schemas.py app/services/proactive.py tests/test_prompt_memory_relationship.py tests/test_jobs_proactive_export.py` from `apps/api` - passed; 4 files already formatted.
- `npm run lint` and `npm run build` from `apps/web` - passed; `apps/web/next-env.d.ts` was restored to the checked-in development route reference.
- `pytest` from `apps/api` - passed; 108 tests.
- `ruff check .` and `ruff format --check .` from `apps/api` - passed; 56 files already formatted.
- Live disposable-account proactive cooldown smoke - passed for profile persistence, chat-created proactive jobs, cooldown payload propagation, and account cleanup.

Known limitations:
- Cooldown remains character-level rather than per-thread; different companions can have different pacing, but one companion uses the same minimum gap across all of their threads.

## World-class continuation - latest-turn edit regeneration

Completed in this checkpoint:
- Changed user-message editing from a silent text patch into a latest-user-turn regeneration flow that returns the edited user message plus a fresh companion reply.
- Restricted editing to the latest user-authored turn and hid edit controls on older user messages.
- Removed stale assistant replies for the edited turn and replaced them in the frontend with the regenerated reply.
- Cleared queued conversation jobs, source-linked memories for the edited line, and conversation-local journals before regeneration so old turn content cannot leak into the new prompt or continuity state.
- Preserved original turn privacy across regenerated replies and kept failed saves from clearing the draft.
- Added owner-scope, older-turn rejection, stale reply removal, memory refresh, journal refresh, and queued-job replacement regressions.
- Documented the regenerated-edit contract in the API, frontend UX, testing acceptance, and progress docs.

Commands run:
- Focused latest-turn edit regression - passed; 1 test.
- `pytest tests/test_level2_state.py -q` from `apps/api` - passed; 16 tests.
- `ruff check app/services/chat.py app/services/memory.py app/api/conversations.py tests/test_level2_state.py` from `apps/api` - passed.
- `ruff format app/services/memory.py tests/test_level2_state.py` from `apps/api` - applied mechanical formatting.
- `ruff format --check app/services/chat.py app/services/memory.py app/api/conversations.py tests/test_level2_state.py` from `apps/api` - passed; 4 files already formatted.
- `npm run lint` and `npm run build` from `apps/web` - passed; `apps/web/next-env.d.ts` was restored to the checked-in development route reference.
- `pytest` from `apps/api` - passed; 108 tests.
- `ruff check .` and `ruff format --check .` from `apps/api` - passed; 56 files already formatted.
- Live disposable-account latest-turn edit smoke - passed for regenerated latest turn, stale reply removal, memory refresh, journal refresh, queued-job replacement, older-turn rejection, cross-account block, and account cleanup.

Known limitations:
- Later reversible relationship-edit work resolves this for new effect-bearing turns. Legacy messages created before relationship-effect metadata existed still use a safe no-guess fallback.

## World-class continuation - thread deletion recovery

Completed in this checkpoint:
- Polished active-thread deletion so it uses normal busy/error/notice state instead of leaving failures as unhandled async work.
- Kept deletion recovery inside the same companion context by selecting a sibling thread for that character, or creating a fresh room for the same character when none remains.
- Cleared stale search state and stable active-thread state immediately after the deleted thread is accepted by the backend.
- Strengthened backend regression coverage for cross-account delete rejection, delete count, queued-job cleanup, and conversation-local message/journal removal.
- Documented conversation deletion behavior in the API contract, frontend UX notes, testing acceptance, and progress log.

Commands run:
- Focused thread-deletion test - passed; 1 test.
- `pytest tests/test_level2_state.py -q` from `apps/api` - passed; 15 tests.
- `ruff check tests/test_level2_state.py`, `ruff format tests/test_level2_state.py`, and `ruff format --check tests/test_level2_state.py` from `apps/api` - passed after one mechanical test-file reformat.
- `pytest` from `apps/api` - passed; 107 tests.
- `ruff check .` and `ruff format --check .` from `apps/api` - passed; 56 files already formatted.
- `npm run lint` and `npm run build` from `apps/web` - passed; `apps/web/next-env.d.ts` was restored to the checked-in development route reference.
- Live disposable-account thread-delete smoke - passed for cross-user block, owned thread delete, deleted messages unreachable, queued jobs removed, linked journals removed, and account cleanup.

Known limitations:
- Deleting a thread does not delete durable memories that were already promoted from that thread; those remain account-owned memories until the user clears memories separately.

## World-class continuation - intentional open-thread presence

Completed in this checkpoint:
- Tightened episodic journal open-thread extraction so ordinary user questions that already receive a companion reply no longer become unresolved-thread continuity.
- Preserved intentional future/reminder loops such as "come back to this later", "next time", and "remind me" as open-thread continuity.
- Kept callback requests distinct from open threads; inside-joke recall can become a callback without automatically scheduling an away nudge.
- Made `proactive_unresolved_thread_nudge` scheduling context-aware so chat completion only queues it when the latest journal has an intentional follow-up cue.
- Rechecked follow-up context at worker time, preserving safe fallback behavior while avoiding dangling open-thread jobs.
- Updated memory, prompt assembly, background-job, testing, and progress docs.

Commands run:
- Focused open-thread and proactive nudge tests - passed; 3 tests.
- `pytest tests/test_level2_state.py tests/test_jobs_proactive_export.py -q` from `apps/api` - passed; 46 tests.
- `ruff check app/services/journal.py app/services/proactive.py tests/test_level2_state.py tests/test_jobs_proactive_export.py` from `apps/api` - passed.
- `ruff format --check app/services/journal.py app/services/proactive.py tests/test_level2_state.py tests/test_jobs_proactive_export.py` from `apps/api` - passed; 4 files already formatted.
- `pytest` from `apps/api` - passed; 107 tests.
- `ruff check .` from `apps/api` - passed.
- `ruff format --check .` from `apps/api` - passed; 56 files already formatted.
- `npm run lint` from `apps/web` - passed.
- `npm run build` from `apps/web` - passed; `apps/web/next-env.d.ts` was restored to the checked-in development route reference.
- Live disposable-account open-thread smoke - passed for answered-question no-nudge, intentional future-loop nudge, and account deletion cleanup.

Known limitations:
- Open-thread detection remains deterministic and phrase-based; it avoids broad semantic inference to keep MVP behavior predictable.
- Existing pending unresolved-thread jobs created before this checkpoint are not migrated, but worker-time context checks still prevent contextless nudges.

## World-class continuation - adult profile safety hardening

Completed in this checkpoint:
- Added a reusable structural safety classifier for minor or ambiguous age, coercion/exploitation, illegal sexual content, stalking/harassment, credential/privacy abuse, real-world harm, and safety-bypass cues.
- Preserved protective refusal language such as "no minors" and "refuses coercion" so consent and hard-limit fields can reinforce boundaries without tripping the unsafe-scenario screen.
- Validated the merged character profile whenever `adult_mode_allowed=true`, covering create, enable, and partial update paths for name, description, persona, speech style, scenario, greeting, consent, limits, and arbitrary profile JSON strings/keys.
- Kept SFW-only profiles editable even when their text contains age-coded context, while blocking any attempt to make such a profile adult-capable.
- Expanded user-message safety coverage to catch both numeric and written minor-age patterns while allowing protective boundary statements.
- Added Adult panel boundary-posture copy and readiness row so scenario/identity text and hard-limit refusal language are clearly separated.
- Updated API, safety, frontend UX, testing, and progress docs.

Commands run:
- Focused adult-profile and safety prompt tests - passed; 3 tests.
- `pytest tests/test_prompt_memory_relationship.py tests/test_auth_chat.py -q` from `apps/api` - passed; 32 tests.
- `ruff check app/services/safety.py app/api/characters.py tests/test_prompt_memory_relationship.py` from `apps/api` - passed after a manual import-order fix.
- `ruff format --check app/services/safety.py app/api/characters.py tests/test_prompt_memory_relationship.py` from `apps/api` - passed; 3 files already formatted.
- `pytest` from `apps/api` - passed; 106 tests.
- `ruff check .` from `apps/api` - passed.
- `ruff format --check .` from `apps/api` - passed; 56 files already formatted.
- `npm run lint` from `apps/web` - passed.
- `npm run build` from `apps/web` - passed; `apps/web/next-env.d.ts` was restored to the checked-in development route reference.
- Live disposable-account adult-profile smoke - passed for unsafe adult profile rejection, protective hard-limit language acceptance, and account deletion cleanup.

Known limitations:
- The classifier is deterministic and pattern-based; it is a structural safety screen, not semantic moderation.
- Protective-language detection is intentionally narrow so scenario text cannot hide unsafe cues behind vague wording.
- Existing adult-capable profiles are validated the next time they are updated; this checkpoint does not run a data migration.

## World-class continuation - session privacy hardening

Completed in this checkpoint:
- Moved refresh tokens out of JSON responses and JavaScript-readable storage into the host-only `eidolon_refresh` HttpOnly cookie scoped to `/auth`.
- Kept access tokens in React memory only, removed fixture auth defaults from the sign-in/register screen, added a quiet session-opening state, and deleted legacy `eidolon_token` / `eidolon_refresh_token` values during session restoration and logout.
- Added credentialed API fetches, same-tab refresh deduplication, Web Locks coordination when available, proactive access-token rotation from JWT expiry, and network retry behavior that only logs out on a confirmed `401`.
- Added backend cookie helpers for setting, clearing, shape-checking, and reading refresh tokens while preserving a bounded one-time legacy body-token migration path.
- Rejected untrusted browser `Origin` headers for register, login, cookie refresh/logout, and legacy refresh-token migration while keeping CLI/server requests without an Origin usable.
- Rotated refresh cookies on `/auth/refresh`, cleared cookies on invalid refresh, logout, and account deletion, and accepted malformed stale cookies as long as a valid legacy body token is supplied during migration.
- Validated refresh-cookie settings, including access-token expiry bounds, SameSite normalization, `SameSite=none` requiring Secure, and Secure cookies outside development/testing.
- Updated API, data-model, architecture, frontend UX, testing, README, env example, and progress docs to describe the current cookie/in-memory session contract.

Commands run:
- Focused auth/config/account deletion tests - passed; 8 tests.
- `docker compose up -d postgres` - PostgreSQL started and reported healthy.
- `cd apps/api && pip install -e ".[dev]"` - passed.
- `cd apps/api && alembic upgrade head && alembic current` - passed; database at `0004_conversation_read_state (head)`.
- `cd apps/api && pytest` - passed; 105 tests.
- `cd apps/api && ruff check .` - passed.
- `cd apps/api && ruff format --check .` - passed; 56 files already formatted.
- `cd apps/web && npm install` - dependencies were up to date and audit reported zero vulnerabilities.
- `cd apps/web && npm run lint` - passed.
- `cd apps/web && npm run build` - passed; `apps/web/next-env.d.ts` was restored to the checked-in development route reference.
- Restarted FastAPI at `http://localhost:8000` and Next.js at `http://localhost:3000`.
- Live disposable-account cookie smoke - passed for register cookie attributes, no refresh token in JSON, cookie rotation, bad Origin rejection, legacy bad Origin rejection, stale-token reuse rejection, and account-deletion cookie clearing.
- `/health`, `/health/db`, `/health/llm`, and the web route returned HTTP 200.
- Direct forbidden-dependency scan over package manifests - no matches.
- Secret-signature scan over config/docs/app source - no matches.
- `git diff --check` - passed.

Known limitations:
- Browser storage migration only covers the legacy `eidolon_token` and `eidolon_refresh_token` keys used by this app.
- Cross-tab refresh coordination uses Web Locks when the browser supports it and falls back to per-tab deduplication otherwise.
- Local development keeps `REFRESH_COOKIE_SECURE=false`; HTTPS Codespaces and production must set it to `true`, and truly cross-site frontend/backend deployments must also use `REFRESH_COOKIE_SAMESITE=none`.

## World-class continuation - local-time-aware proactive presence

Completed in this checkpoint:
- Added validated IANA timezone, morning time, goodnight time, quiet-start, and quiet-end presence preferences without a schema migration or external dependency.
- Used Python 3.12 `zoneinfo` to convert local wall-clock targets to UTC across daylight-saving changes.
- Queued morning and goodnight notes at their next configured local target with a four-hour minimum lead and a three-hour recovery window.
- Shifted all other automatically queued presence jobs out of configured quiet hours.
- Rechecked local delivery policy when a time-aware job becomes due, covering sleeping runtimes and preference changes.
- Added a non-failure deferral transition that returns a row to `pending`, clears claim locks, retains retry count, and stores only a bounded reason plus next instant.
- Marked new proactive rows with their local-time policy, delivery timezone, and intended local timestamp.
- Rescheduled enabled pending rows when character presence-clock preferences change and cancelled blocked rows in the same character update transaction.
- Kept safe UTC defaults for existing character rows with no clock fields and failed closed on invalid stored values.
- Rejected malformed clock strings, unknown IANA zones, and non-object proactive preferences at the API boundary.
- Added native time controls, an IANA timezone field, and a device-timezone command to both staged creation and later Persona editing.
- Added readable private Debug outcomes for local-time deferral and preference-driven cancellation.
- Updated product, architecture, data-model, API, background-job, frontend, testing, README, and progress documentation.

Commands run:
- Focused local scheduling, DST, delivery-window, quiet-deferral, pending-reschedule, and API-validation tests - passed; 6 tests.
- Full proactive/export/scheduler module plus clock API validation - passed; 32 tests.
- `npm install` from `apps/web` - dependencies remained current and the audit reported zero vulnerabilities.
- `npm run lint` and `npm run build` from `apps/web` - passed, including TypeScript and static generation; `apps/web/next-env.d.ts` was restored to the checked-in development route reference.
- `ruff check .`, `ruff format .`, and final `ruff check .` from `apps/api` - passed; all 55 files were already formatted.
- Final full `pytest` from `apps/api` - passed; 102 tests.
- Live disposable-account smoke saved a UTC presence clock, completed chat, and verified PostgreSQL jobs targeted local `08:30` morning and `22:30` goodnight instants.
- The same live smoke forced a marked job due inside a dynamic quiet window; it returned to `pending` at quiet end with zero retries, no error, and both lock fields cleared.
- The disposable local-clock account and all cascaded rows were erased through the protected account endpoint.
- Migration-head, live health, generated-file, direct dependency, forbidden-package, secret-signature, and `git diff --check` audits - passed.

Known limitations:
- Existing characters default to UTC until the user chooses an IANA zone or uses the device-timezone command.
- Presence clocks are character-level preferences; different companions may intentionally keep different schedules.
- Local note jobs are still conversation-triggered rather than permanent calendar recurrences, preserving the existing no-spam and stale-user-return semantics.
- Non-clock proactive rows created before this checkpoint do not gain quiet-hour enforcement until the character preferences are saved and those pending rows are rescheduled.

## World-class continuation - natural mock companion voice

Completed in this checkpoint:
- Replaced the diagnostic mock response composer with deterministic, natural SFW companion dialogue.
- Used bounded emotional and topical message cues for tiredness, anger, loneliness, anxiety, positive news, gratitude, greetings, questions, work, relationships, media, decisions, and evening company.
- Let display name, speech style, recent-thread depth, relationship mood and repair state, one selected memory, and a selected episode influence wording without reciting those inputs.
- Turned selected preferences into ordinary-language continuity and response-plan episode focus into a natural callback.
- Projected first-person unresolved-thread notes into companion perspective so callbacks do not produce grammar such as `keep I had...`.
- Added a natural repair posture for strained relationship state without exposing conflict labels or scores.
- Removed provider prefixes, full current-message echo, style recitation, hidden response-strategy narration, raw relationship numbers, and memory metadata from assistant prose.
- Bounded callback fragments, rejected hidden-context markers, failed closed on malformed memory metadata, and sanitized display names before address.
- Added a clean natural fallback for empty or rejected context.
- Preserved deterministic composing and punctuation-aware streaming cadence with identical persisted final text.
- Added provider regressions for emotional cues, persona voice, memory continuity, response plans, first-person projection, repair, permission questions, malformed and tainted context, empty context, punctuation, and cadence.
- Added ordinary and SSE chat-boundary assertions so diagnostic prose cannot be persisted even when provider tests pass.
- Updated the README plus product, prompt, frontend, testing, and progress documentation with the no-leak response contract.

Commands run:
- Initial focused provider, persisted-chat, and SSE tests - passed; 14 tests.
- `docker compose up -d postgres` - PostgreSQL remained running.
- `pip install -e ".[dev]"` from `apps/api` - passed.
- `alembic upgrade head` and `alembic current` from `apps/api` - passed; database confirmed at `0004_conversation_read_state (head)`.
- First full `pytest` from `apps/api` - passed; 94 tests.
- `ruff check .`, `ruff format .`, final `ruff check .`, and `ruff format --check .` from `apps/api` - passed; all 55 files were already formatted.
- `npm install` from `apps/web` - dependencies remained current and the audit reported zero vulnerabilities.
- `npm run lint` and `npm run build` from `apps/web` - passed, including TypeScript and static generation; `apps/web/next-env.d.ts` was restored to the checked-in development route reference.
- Restarted FastAPI and Next.js at `http://localhost:8000` and `http://localhost:3000`.
- The first disposable-account ordinary/SSE live smoke exposed a first-person episode projection error after otherwise clean, persisted responses; the account was erased.
- Added the exact regression and companion-perspective projection; focused provider tests passed.
- Repeated the disposable-account live smoke: ordinary and SSE replies were natural, free of known internal markers, persisted exactly once each, and the account was erased.
- Added malformed-metadata and persona-influence regressions; all 15 provider tests passed.
- Final full `pytest` from `apps/api` - passed; 97 tests.
- Final Ruff lint and formatting checks - passed; all 55 files were already formatted.
- `/health` and `/health/db` returned healthy payloads; the web route returned HTTP 200.
- Generated-file, direct dependency, forbidden-package, secret-signature, and `git diff --check` audits - passed.

Known limitations:
- The deterministic mock recognizes a bounded cue vocabulary and cannot provide the open-ended reasoning or factual depth of Ollama.
- The mock uses the highest-ranked selected memory rather than synthesizing every retrieved memory.
- Perspective conversion covers common first-person openings; unfamiliar syntax falls back to a generic bounded callback rather than a full language rewrite.
- Repeated messages with the same cue can reuse a template; this predictability is useful for development tests but is not the intended production inference experience.

## World-class continuation - live scheduler and resilient presence

Completed in this checkpoint:
- Enabled the PostgreSQL-backed scheduler by default for the personal development runtime while tests explicitly keep background startup disabled.
- Made FastAPI lifespan own the scheduler handle and distinguish configured from actually running state.
- Added configuration bounds for tick interval, batch size, retry count, and retry base delay.
- Added capped exponential backoff for unexpected execution failures without persisting internal exception text.
- Kept invalid payloads and unsupported job types terminal because retries cannot repair them.
- Cleared `locked_at` and `locked_by` after done, retry, and failed transitions.
- Added a PostgreSQL transaction-scoped advisory lock so only one API process can run a scheduler batch.
- Made the test suite hold the matching session lock, preventing an independently running development API from consuming fixture jobs while preserving direct deterministic service tests.
- Exposed scheduler enabled/running state, interval, batch size, and retry cap only through authenticated character Debug.
- Expanded the Debug job view with readable type names, outcomes, retry numbers, next due times, and safe failure text.
- Kept all scheduler/provider/job state out of the primary companion shell.
- Raised the documented development JWT placeholder above the SHA-256 minimum while retaining production placeholder rejection.
- Normalized trailing punctuation in mock speech-style instructions so authored styles cannot produce malformed prose such as `concise.,`.
- Updated the root env example, README, product, architecture, background-job, frontend, testing, and progress documentation.

Commands run:
- Six focused lifecycle, config-bound, lock-release, retry-cap, permanent-failure, and debug-runtime tests - passed.
- Initial full backend suite - passed; 89 tests.
- `ruff check .`, `ruff format .`, and final `ruff check .` from `apps/api` - passed; 55 files remained unchanged.
- `npm install` from `apps/web` - dependencies remained current and the audit reported zero vulnerabilities.
- `npm run lint` and `npm run build` from `apps/web` - passed, including TypeScript and static generation; `apps/web/next-env.d.ts` was restored to the checked-in development route reference.
- Live API ran with a five-second tick, registered a throwaway account, completed chat, and queued normal presence jobs.
- A due delayed-follow-up row was claimed by the lifespan-owned scheduler without a manual processing call; it persisted an unread proactive assistant message, marked the job done, and cleared both lock fields.
- Authenticated Debug reported `scheduler_enabled=true` and `scheduler_running=true` and returned the completed safe job outcome.
- The throwaway scheduler account and all cascaded rows were erased through the protected account endpoint.
- The first post-smoke full suite exposed a live-server race: one runtime tick consumed an unsupported fixture job before its direct service test.
- Added the PostgreSQL advisory tick/test guard; the three affected focused tests then passed with the live five-second scheduler still running.
- Final full `pytest` with the live scheduler still active - passed; 91 tests.
- Focused development-key and mock-punctuation regressions - passed.
- Final Ruff checks and formatting - passed.
- Restarted FastAPI at the normal 60-second cadence and kept Next.js live at `http://localhost:3000`.

Known limitations:
- Codespaces or a VM must be awake for a tick to run; overdue PostgreSQL jobs are processed after the backend resumes, and there are no push notifications.
- Morning and goodnight variants currently use fixed elapsed delays rather than a user-local timezone schedule.
- Unexpected failures store a generic safe reason; detailed exception context remains in private server logs rather than job rows.
- Set `ENABLE_SCHEDULER=false` when an API-only development session should not process background work.

## World-class continuation - authored companion creation

Completed in this checkpoint:
- Replaced the name-only quick-create form with a four-stage Presence, Inner life, Shared world, and Trust builder.
- Covered name, explicit age, relationship type, description, personality, flaws, values, speech, humor, interests, backstory, greeting, nickname posture, scenario presets/custom text, boundaries, consent style, soft/hard limits, return-to-calm style, adult eligibility, intensity, memory, privacy, and proactive presence.
- Seeded each new draft with the complete authored SFW profile foundation while requiring a deliberate name and other essential authored fields.
- Added per-field validation, stage error markers, first-invalid-field focus, character counts enforced through input limits, and cross-field age/adult/intensity rules.
- Forced adult memory storage and intensity off whenever adult eligibility is unavailable.
- Kept recoverable drafts in local state and surfaced creation failures inside the modal.
- Distinguished request failure from a persisted character whose list or initial conversation failed to load, preventing duplicate retries.
- Added modal scroll lock, focus containment, Escape/backdrop close, submit locking, and focus restoration.
- Split orchestration, stage content, shared fields, and builder policy into focused frontend modules.
- Normalized character names and bounded top-level profile text in Pydantic.
- Bounded flexible profile JSON by UTF-8 bytes, depth, collection fan-out, key length, and individual string length.
- Rejected explicit null updates for database-nonnullable character fields before commit.
- Completed the server-authored default Eidolon with consent, soft/hard limit, and return-to-calm fields.
- Added regressions for complete profile persistence, relationship initialization, default profile completeness, blank names, per-value size, aggregate size, excessive nesting, and fair UTF-8 accounting.
- Updated product, architecture, data model, API, frontend, testing, and progress documentation.

Commands run:
- Focused authored-profile/default-character tests - passed; 3 tests.
- Focused UTF-8 and pathological-profile regression after aggregate-size hardening - passed.
- Focused explicit-null update regression - passed.
- Focused Ruff checks for schemas, default profile, and tests - passed.
- `docker compose up -d postgres` - PostgreSQL remained running.
- `pip install -e ".[dev]"` from `apps/api` - passed.
- `alembic upgrade head` and `alembic current` from `apps/api` - passed; database confirmed at `0004_conversation_read_state (head)`.
- `pytest` from `apps/api` before formatting - passed; 86 tests.
- `ruff check .`, `ruff format .`, and final `ruff check .` from `apps/api` - passed; 3 files reformatted and 52 left unchanged.
- Final `pytest` after formatting - passed; 86 tests.
- `npm install` from `apps/web` - dependencies remained current and the audit reported zero vulnerabilities.
- Final `npm run lint` and `npm run build` from `apps/web` - passed, including TypeScript and static generation; `apps/web/next-env.d.ts` was restored to the checked-in development route reference.
- Restarted FastAPI and Next.js at `http://localhost:8000` and `http://localhost:3000`.
- Live authenticated smoke registered an account, created and normalized a complete profile, verified its relationship row, opened its conversation, and erased the throwaway account.
- `/health` and `/health/db` returned healthy payloads; the web route returned HTTP 200.

Known limitations:
- Unsaved builder drafts intentionally disappear when the modal closes or the page reloads.
- Existing character rows are not backfilled with the newly completed default consent profile; users can edit those fields in Persona.
- Character persistence and initial conversation creation remain separate API operations; the UI handles partial success explicitly.
- This lean workspace still has no browser binary or Playwright package, so visual validation uses responsive source review, production compilation, and live HTTP rather than screenshots.

## World-class continuation - companion-first responsive shell

Completed in this checkpoint:
- Made the active conversation the default mobile workspace instead of placing management UI before the companion.
- Added restrained Threads, Conversation, and Companion mobile controls with an aggregate unread indicator.
- Preserved the three-pane desktop workspace for fast personal operation.
- Moved mobile users into chat only after character, thread, or creation navigation succeeds.
- Added monotonic versions to selection, creation, and deletion navigation so a later user choice always wins.
- Discarded stale companion-state payloads and rechecked selection currency before starting history loads.
- Restored the last fully loaded character/thread pair when the current selection fails.
- Kept the stable navigation snapshot current after title, privacy, persona, unread, and conversation-summary changes.
- Replaced the operational shell header with the companion's initial, human bond/temperature language, and privacy posture.
- Replaced the content-mode select with a compact Safe/Adult segmented control.
- Removed API, database, provider, raw mood/conflict, and logout controls from primary chrome.
- Moved runtime health and refresh into the authenticated Debug panel alongside provider, prompt, and job details.
- Updated product, architecture, frontend, and testing documentation with the responsive and async-state contracts.

Commands run:
- Primary-shell and runtime-status source invariant searches - passed; operational health is referenced only by Debug.
- `npm install` from `apps/web` - dependencies were current and the audit reported zero vulnerabilities.
- `npm run lint` from `apps/web` - passed.
- `npm run build` from `apps/web` - passed, including TypeScript and static generation; `apps/web/next-env.d.ts` was restored to the checked-in development route reference.
- `docker compose up -d postgres` - PostgreSQL remained running.
- `pip install -e ".[dev]"` from `apps/api` - passed.
- `alembic upgrade head` and `alembic current` from `apps/api` - passed; database confirmed at `0004_conversation_read_state (head)`.
- `pytest` from `apps/api` - passed; 84 tests.
- `ruff check .`, `ruff format .`, and final `ruff check .` from `apps/api` - passed; 55 files remained unchanged.
- Started fresh FastAPI and Next.js processes at `http://localhost:8000` and `http://localhost:3000`.
- `/health` and `/health/db` returned healthy payloads; the web route returned HTTP 200.

Known limitations:
- Mobile workspace choice is intentionally in-memory and returns to Conversation after a page reload.
- This lean workspace has no browser binary or Playwright package; responsive visual verification used source-state review, production compilation, and live HTTP rather than screenshots.
- Desktop intentionally keeps all three workspaces visible instead of applying the mobile single-pane control.

## World-class continuation - one-turn private exchanges

Completed in this checkpoint:
- Added an optional `privacy_mode` to chat requests with strict `normal` or `private` validation.
- Resolved an authoritative privacy mode when each user turn is accepted; a request can tighten a standard thread but cannot weaken a private thread.
- Persisted the accepted mode on both user and companion messages and preserved or tightened it on reroll.
- Made accepted message provenance, rather than mutable thread state at completion time, control memory, relationship, journal, and proactive writes.
- Prevented private turns from advancing memory `last_recalled_at`.
- Excluded private user and companion rows from later standard prompt history while retaining them for active private-room coherence.
- Excluded private rows at the PostgreSQL query boundary for journal summaries and scheduled batch extraction, so private-heavy history cannot consume a bounded standard window.
- Kept private prose out of journal titles, summaries, emotional tags, callbacks, open threads, continuity notes, and message counts.
- Prevented queued proactive jobs and delayed double-texts from using the latest private turn.
- Kept private messages visible to the authenticated owner through normal history, search, and export.
- Added one-shot composer privacy that resets at the SSE `message_start` acceptance boundary, remains selected across pre-acceptance failures, and clears on thread/session reset.
- Kept the draft intact until server acceptance and added private message labels plus grouping boundaries between private and standard lines.
- Centralized defensive message privacy parsing for chat, memory capture, debug decisions, journals, scheduler, and proactive services.
- Updated product, data model, API, prompt, memory, background-job, safety, frontend, testing, and progress documentation.

Commands run:
- Focused Ruff for all touched backend services, endpoints, schemas, and tests - passed.
- Five focused SSE, continuity, recall, batch-extraction, and proactive privacy regressions - passed.
- Initial `pytest` from `apps/api` - passed; 84 tests.
- `ruff format .` from `apps/api` - passed; one file reformatted and 54 files unchanged.
- `ruff check .` from `apps/api` - passed.
- The five focused regressions after formatting - passed.
- `pip install -e ".[dev]"` from `apps/api` - passed.
- `docker compose up -d postgres` - PostgreSQL remained running.
- `alembic upgrade head` and `alembic current` from `apps/api` - passed; database confirmed at `0004_conversation_read_state (head)`.
- Final `pytest` from `apps/api` - passed; 84 tests.
- `npm install` from `apps/web` - dependencies were current and the audit reported zero vulnerabilities.
- Final `npm run lint` from `apps/web` - passed.
- Final `npm run build` from `apps/web` - passed, then `apps/web/next-env.d.ts` was restored to the checked-in development route reference.
- Restarted FastAPI at `http://localhost:8000`; `/health` and `/health/db` returned the expected healthy payloads.
- Live OpenAPI exposed chat `privacy_mode` as `normal | private` with a `normal` default.
- Restarted Next.js at `http://localhost:3000`; host-side HTTP smoke returned 200.
- Final generated-file, dependency, forbidden-package, and `git diff --check` verification - passed.

Known limitations:
- Private turns remain in authenticated history, search, and export by design; they are not ephemeral or cryptographically erased.
- Existing memories and journals may inform a private reply for continuity, but the turn does not advance recall timestamps or feed later standard recent-message context.
- One-turn privacy is local composer state and intentionally resets on accepted send, navigation, logout, or reload.
- One-turn private exchanges use message labels rather than creating thread-level transition event cards.

## World-class continuation - privacy system event cards

Completed in this checkpoint:
- Added a backend-owned SFW system message for each actual private/standard continuity transition.
- Committed the privacy state and its event atomically so history cannot disagree with the active mode.
- Serialized updates on the owned conversation row so repeated or concurrent writes to the already-active mode remain idempotent while still clearing queued jobs defensively in private mode.
- Kept system events out of assistant unread counts, memory capture, relationship mutation, proactive state, and journal source text.
- Canonicalized recognized privacy events into fixed `conversation event:` prompt lines instead of inserting raw stored system prose.
- Omitted unknown or malformed system rows from recent prompt history.
- Bumped prompt assembly to `persona_memory_relationship_episode_plan_v4`.
- Rendered system rows as restrained timestamped cards with canonical privacy labels and bounded defensive fallbacks.
- Added endpoint coverage for event metadata, order, concurrent idempotency, unread neutrality, resumed journaling, and journal-text exclusion.
- Added a tampered-event regression proving stored prose cannot become a model instruction.
- Updated product, data model, API, prompt, safety, frontend, testing, and progress documentation.

Commands run:
- Focused Ruff for the backend service, endpoint, prompt, journal, and regression files - passed.
- Focused privacy transition and prompt-canonicalization tests during implementation - passed; 2 tests.
- Simultaneous matching privacy PATCH regression with a bounded test timeout - passed; one event persisted.
- `pytest` from `apps/api` - passed; 79 tests.
- `ruff format .` from `apps/api` - passed; 55 files unchanged.
- `ruff check .` from `apps/api` - passed.
- Focused privacy transition and prompt-canonicalization tests after formatting - passed; 2 tests.
- `alembic upgrade head` and `alembic current` from `apps/api` - passed; database confirmed at `0004_conversation_read_state (head)`.
- `npm run lint` from `apps/web` - passed.
- `npm run build` from `apps/web` - passed, then `apps/web/next-env.d.ts` was restored to the checked-in development route reference.
- `docker compose up -d postgres` - PostgreSQL remained running.
- Restarted FastAPI at `http://localhost:8000`; `/health` returned the expected healthy payload.
- Restarted Next.js at `http://localhost:3000`; host-side HTTP smoke returned 200.
- Final dependency, generated-file, and `git diff --check` verification - passed.

Known limitations:
- Privacy transitions are the only durable system-event type currently emitted.
- A conversation created directly in private mode begins private without a transition card; the active privacy state remains visible in the thread header.
- System events intentionally do not create unread or push-notification activity.

## World-class continuation - natural typing rhythm

Completed in this checkpoint:
- Added a short deterministic pre-token pause to mock streaming so composing state is observable.
- Added punctuation-aware delays between bounded natural chunks without changing final generated text.
- Added focused provider coverage that records cadence calls without sleeping through the unit test.
- Strengthened SSE coverage to require `message_start`, multiple `token` events, and `message_done` in order.
- Added explicit client stream phases for connecting, composing, and streaming.
- Added a stable pre-token presence treatment and phase-aware header posture.
- Changed user-line read posture to begin at the server-accepted composing boundary rather than waiting for visible text.
- Bound every active stream to its originating conversation and an `AbortController`.
- Cancelled and ignored stale stream readers and events on thread switch, logout, reset, or unmount.
- Released stream reader locks and suppressed intentional cancellation errors.
- Refused overlapping sends so a second submit cannot abandon an already persisted user turn.
- Disabled message edit, reroll, remember, and delete controls while generation owns the thread.
- Added readable failure handling for streams that close without either `message_done` or `error`.
- Preserved single final-message append and normal side-state refresh after successful or server-reported completion.
- Updated chat requirements, SSE contract, frontend lifecycle, test acceptance, and progress docs.

Commands run:
- Focused Ruff for the mock provider and provider tests - passed.
- `pytest tests/test_llm_providers.py::test_mock_provider_streaming_returns_natural_chunks tests/test_auth_chat.py::test_stream_persists_final_assistant_without_duplicate -q` from `apps/api` after server cadence work - passed; 2 tests.
- `npm run lint` and `npm run build` from `apps/web` after the initial stream lifecycle - passed.
- A failure-path simulation then added premature-EOF detection, overlapping-send prevention, and visible action locking.
- Final focused cadence and SSE-order tests - passed; 2 tests.
- `pytest` from `apps/api` - passed; 78 tests.
- `ruff format .` from `apps/api` - passed; 55 files unchanged.
- `ruff check .` from `apps/api` - passed.
- Focused cadence and SSE-order tests after formatting - passed; 2 tests.
- Final `npm run lint` from `apps/web` - passed.
- Final `npm run build` from `apps/web` - passed, then `apps/web/next-env.d.ts` was restored to the checked-in development route reference.
- `alembic current` from `apps/api` - confirmed `0004_conversation_read_state (head)`.
- `git diff --check` and generated/dependency-file verification - passed.
- Reloaded FastAPI at `http://localhost:8000`; `/health` returned the expected healthy payload.
- Reloaded Next.js at `http://localhost:3000`; host-side HTTP smoke returned 200.

Known limitations:
- Mock cadence is intentionally fixed and modest; it does not yet vary by character speech style or response length.
- Ollama token timing remains provider-driven, while the same client lifecycle and cancellation guards still apply.
- Cancelling the visible browser stream does not guarantee remote or server-side inference cancellation; a completed reply remains attached to its original conversation and appears when that thread is reopened.

## World-class continuation - durable read and away presence

Completed in this checkpoint:
- Added a migration-backed `last_read_at` cursor for every conversation.
- Added derived `last_message_at` and assistant-only `unread_count` fields to conversation responses without duplicating message state.
- Added an authenticated, account-scoped mark-read endpoint that advances only through an exact rendered assistant message.
- Made cursor advancement atomic and monotonic so stale or concurrent tabs cannot move it backward.
- Kept assistant messages that arrive between history fetch and receipt write unread instead of hiding unseen content.
- Initialized pre-migration conversation history as read so existing users do not receive a wall of historical badges.
- Added per-thread and per-character unread presence indicators with activity-based thread ordering.
- Added lightweight 30-second conversation refresh while the tab is visible, plus immediate focus/visibility refresh.
- Added overlap, cancellation, and stale-history guards so background requests cannot overwrite a newly selected thread.
- Kept loaded history usable when a receipt write fails; authentication failures still propagate through the normal session path.
- Added sent/read posture for user messages based on actual companion response order.
- Added the read cursor to private account export and documented the API, model, background, UX, and test contracts.
- Added migration, idempotency, new-reply, invalid-boundary, ownership, and export regressions.

Commands run:
- `alembic upgrade head` from `apps/api` - passed; applied `0004_conversation_read_state`.
- Focused Ruff initially caught one import-order issue; it was corrected and the rerun passed.
- Initial focused read-state, export, and migration tests - passed; 3 tests.
- `npm run lint` from `apps/web` during implementation - passed.
- Production type checking initially caught nullable values captured by the presence-refresh closure; immutable non-null effect values fixed both reports.
- `npm run build` from `apps/web` after the closure fix - passed.
- A concurrency simulation then replaced "read latest" behavior with an exact rendered-message boundary and atomic monotonic update.
- Focused cursor regression after the concurrency correction - passed.
- `pytest` from `apps/api` - passed; 78 tests.
- `ruff format .` from `apps/api` - passed; 55 files unchanged.
- `ruff check .` from `apps/api` - passed.
- Focused read-state, export, and migration tests after formatting - passed; 3 tests.
- Final `npm run lint` from `apps/web` - passed.
- Final `npm run build` from `apps/web` - passed, then `apps/web/next-env.d.ts` was restored to the checked-in development route reference.
- `git diff --check` and generated-route-reference verification - passed.
- `docker compose ps postgres` - PostgreSQL reported healthy.
- Restarted FastAPI at `http://localhost:8000`; `/health` and `/health/db` returned the expected healthy payloads.
- Restarted Next.js at `http://localhost:3000`; host-side HTTP smoke returned 200.

Known limitations:
- Live presence uses visible-tab polling with up to a 30-second delay; push notifications remain outside MVP scope.
- Read state is account-wide per conversation rather than tracked separately per browser device.
- Existing conversations are intentionally initialized as read when the migration is applied.
- User-line `read` posture means a companion response began or completed after that line; it is not a model-generated acknowledgment.

## World-class continuation - distinct shared-history episodes

Completed in this checkpoint:
- Split anniversaries out of generic milestone classification.
- Split inside jokes out of generic shared-reference classification.
- Added a distinct shared-moment signal for explicit shared-history language.
- Added bounded SFW continuity notes for all three signals while preserving adult-mode redaction.
- Added distinct journal types, labels, emotional tags, resonance summaries, prompt labels, and planner priorities.
- Changed private planning to select the note matching the chosen signal instead of blindly using the journal's first continuity note.
- Added planner guidance that acknowledges anniversaries without inventing dates or history, preserves only the supplied inside-joke reference, and honors shared moments with grounded specificity.
- Added API regression coverage through real chat, journal persistence, debug prompt assembly, and private response-plan output.
- Updated memory, data-model, prompt, frontend, product, and progress docs.

Commands run:
- `pytest tests/test_level2_state.py::test_journal_relationship_and_proactive_hooks_after_chat tests/test_level2_state.py::test_journal_distinguishes_anniversary_and_shared_moment tests/test_prompt_memory_relationship.py::test_adult_mode_journal_omits_durable_callback_details -q` from `apps/api` - passed; 3 tests.
- Focused Ruff first caught two long continuity-note lines; both were wrapped and the rerun passed.
- `pytest` from `apps/api` - passed; 77 tests.
- `ruff format .` from `apps/api` - passed; 1 file reformatted and 52 left unchanged.
- `ruff check .` from `apps/api` after formatting - passed.
- The three focused continuity/adult-redaction tests after formatting - passed.
- `npm run lint` from `apps/web` - passed.
- `npm run build` from `apps/web` - passed, then `apps/web/next-env.d.ts` was restored to the checked-in development route reference.
- Diff review caught the new journal-metadata contract under the wrong data-model section; it was moved under `episodic_journals`.
- `alembic upgrade head` from `apps/api` - passed.
- `git diff --check` plus generated-route-reference verification - passed.
- Host-side `curl http://127.0.0.1:3000/` - returned HTTP 200 from the running frontend.

Known limitations:
- Classification is deterministic and phrase-based; it does not infer an anniversary from calendar math alone.
- Existing journal rows gain the new distinct signals when their conversation is summarized again rather than through a data backfill.

## World-class continuation - user-selected message memory

Completed in this checkpoint:
- Added an authenticated per-message memory endpoint for owned user and companion messages.
- Made user-selected memories pinned, source-linked, and visibly marked as kept from chat.
- Preserved bounded additional source-message ids when deterministic dedupe merges similar memories.
- Promoted an existing automatic memory in place instead of creating a duplicate.
- Made repeated capture idempotent and protected client state from an in-flight response after switching companions.
- Enforced current private-thread state and original message privacy so private history cannot be captured after switching a thread back to standard.
- Enforced character-wide memory pause and explicit adult-memory opt-in.
- Rejected system messages, structurally blocked content, and credential-like content with readable errors.
- Added chat controls with derived `Remember`, `Saving`, and `Remembered` states for normal and proactive companion messages.
- Kept automatic source linkage distinct from explicit user selection so an automatically learned line can still be pinned by the user.
- Updated memory source labels, API/data/memory/frontend docs, and product acceptance criteria.

Commands run:
- `pytest tests/test_auth_chat.py -q` from `apps/api` after the first endpoint pass - passed; 10 tests.
- `ruff check app/api/conversations.py app/services/memory.py tests/test_auth_chat.py` from `apps/api` - passed.
- `npm run lint` from `apps/web` after the initial client wiring - passed.
- `npm run build` from `apps/web` after the initial client wiring - passed.
- A combined focused-test/lint shell process later stalled without output and was interrupted; the new promotion case then passed alone and the clean module rerun passed.
- `pytest tests/test_auth_chat.py::test_message_remember_promotes_automatic_memory_without_duplicate -vv -s` from `apps/api` - passed.
- `pytest tests/test_auth_chat.py -q` from `apps/api` with promotion coverage - passed; 11 tests.
- `pytest` from `apps/api` - passed; 76 tests.
- `ruff format .` from `apps/api` - passed; 2 files reformatted and 51 left unchanged.
- `ruff check .` from `apps/api` after formatting - passed.
- `pytest tests/test_auth_chat.py -q` from `apps/api` after formatting - passed; 11 tests.
- `npm run build` from `apps/web` - passed, then `apps/web/next-env.d.ts` was restored to the checked-in development route reference.
- Final `npm run lint` from `apps/web` caught render-time ref synchronization in the companion-switch race guard; moved the update into a React effect and reran successfully.
- Final `npm run build` from `apps/web` after the ref fix - passed, then `apps/web/next-env.d.ts` was restored again.
- `alembic upgrade head` from `apps/api` - passed.
- `git diff --check` plus generated-route-reference verification - passed.
- Host-side `curl http://127.0.0.1:3000/` - returned HTTP 200 from the running frontend.

Known limitations:
- A memory has one relational primary `source_message_id`; additional deduped source links are kept in bounded JSON metadata.
- Message-memory capture is intentionally explicit and one-at-a-time in the UI; bulk capture is not part of this checkpoint.

## World-class continuation - authored first-contact greeting

Completed in this checkpoint:
- Replaced generic empty-thread copy with the active character's authored profile greeting.
- Added a calm first-contact treatment that identifies the character and reads as dialogue rather than dashboard guidance.
- Kept the opening greeting derived and ephemeral so it never creates a synthetic message, affects continuity state, or duplicates when history or streaming content exists.
- Added a natural fallback for absent, malformed, or whitespace-only greeting metadata.
- Bounded imported greeting length at a word boundary to protect the empty-thread layout from untrusted or legacy profile data.
- Updated frontend UX and progress docs.

Commands run:
- `npm run lint` from `apps/web` - passed.
- `npm run build` from `apps/web` - passed, then `apps/web/next-env.d.ts` was restored to the checked-in development route reference.
- `git diff --check` plus generated-route-reference verification - passed.
- `npm run dev` from `apps/web` - started successfully at `http://localhost:3000`.
- Host-side `curl http://127.0.0.1:3000/` - returned HTTP 200 with the Eidolon auth shell.

Known limitations:
- The greeting is an empty-thread presentation, not a stored assistant message, so it has no timestamp or message actions.
- Browser screenshot tooling is not installed; visual validation for this checkpoint is production build and responsive-code inspection.

## World-class continuation - continuity-complete private export

Completed in this checkpoint:
- Expanded the authenticated account export with conversation metadata and update time.
- Preserved memory ownership, extraction/conflict metadata, recall time, and update time.
- Preserved episodic-journal continuity metadata and update time.
- Preserved relationship timeline, recent-change and milestone metadata with interaction and lifecycle times.
- Preserved proactive job ownership, payload, lock/error state, retries, and lifecycle times.
- Serialized nullable recall, interaction, and lock timestamps as JSON `null`.
- Kept every query scoped to the authenticated account and excluded password hashes, refresh-token hashes, secrets, and environment configuration.
- Added a regression that creates real chat continuity state, exports it, and verifies memory, journal, relationship, and job metadata without secret fields.
- Updated the API contract and product acceptance criteria.

Commands run:
- `pytest tests/test_jobs_proactive_export.py::test_export_preserves_continuity_metadata_without_secrets tests/test_jobs_proactive_export.py::test_export_excludes_secrets tests/test_jobs_proactive_export.py::test_export_excludes_other_users_data -q` from `apps/api` - passed; 3 tests.
- `ruff check app/api/export.py tests/test_jobs_proactive_export.py` from `apps/api` - first run caught import ordering; passed after correction.
- `pytest tests/test_jobs_proactive_export.py -q` from `apps/api` - passed; 23 tests.
- `pytest` from `apps/api` - initial run could not reach the shared migration fixture because PostgreSQL was not listening on `localhost:5432`; no application tests ran.
- `docker compose up -d postgres` - passed; `eidolon-postgres` started.
- `docker compose ps postgres` - passed; PostgreSQL reported healthy.
- `pytest` from `apps/api` after restoring PostgreSQL - passed; 71 tests.
- `ruff format .` from `apps/api` - passed; 53 files unchanged.
- `ruff check .` from `apps/api` - passed.
- `pytest tests/test_jobs_proactive_export.py::test_export_preserves_continuity_metadata_without_secrets tests/test_jobs_proactive_export.py::test_export_excludes_secrets tests/test_jobs_proactive_export.py::test_export_excludes_other_users_data -q` from `apps/api` after formatting - passed; 3 tests.
- `git diff --check` - passed.

Known limitations:
- Export is a private JSON backup; there is no import/restore endpoint yet.
- Flexible JSON metadata is exported in its stored form so a backup remains faithful, rather than being reduced to user-facing summaries.

## World-class continuation - scoped data cleanup confirmations

Completed in this checkpoint:
- Replaced the single broad Data panel cleanup checkbox with exact typed confirmations for each destructive scope.
- Added separate unlock phrases for clearing the active chat, clearing character memories, and deleting the current thread.
- Made each cleanup button unlock only for its matching phrase and only when there is data in that scope.
- Cleared the phrase after a cleanup action is triggered to reduce accidental repeat actions.
- Preserved the existing account deletion password plus `DELETE MY ACCOUNT` confirmation.
- Updated frontend UX and progress docs.

Commands run:
- `npm run lint` from `apps/web` - passed.
- `npm run build` from `apps/web` - passed, then `apps/web/next-env.d.ts` was restored to the checked-in dev route reference.
- `git diff --check` - passed.

Known limitations:
- These are frontend safeguards over existing scoped backend deletion endpoints; direct API calls still rely on server-side authorization and endpoint behavior.
- The cleanup phrases are fixed English strings.

## World-class continuation - adult readiness panel

Completed in this checkpoint:
- Reworked the Adult settings panel around a clear readiness checklist for user age gate, explicit adult character age, character permission, and relationship readiness.
- Added adult status title/detail copy that distinguishes SFW fallback, gated adult mode, and incomplete checks.
- Added relationship-repair guidance when adult mode is paused by repair, tension, or relationship-state reasons.
- Added a memory posture section explaining private mode, disabled adult memory storage, and explicit adult-memory opt-in without changing backend rules.
- Replaced raw intensity text with named intensity labels.
- Kept all existing save/toggle behavior and backend contracts intact.
- Updated safety and frontend UX docs.

Commands run:
- `npm run lint` from `apps/web` - passed.
- `npm run build` from `apps/web` - passed, then `apps/web/next-env.d.ts` was restored to the checked-in dev route reference.
- `git diff --check` - passed.

Known limitations:
- This is a frontend presentation checkpoint; relationship blocks still come from the existing backend adult-status reasons.
- The readiness checklist is derived from current draft state and saved status, so unsaved edits still require pressing Save adult settings.

## World-class continuation - journal continuity UI

Completed in this checkpoint:
- Added optional frontend typing for journal continuity metadata while remaining compatible with older/manual journal entries.
- Added cognition helpers that translate only known continuity signals into human labels and compact malformed/long notes defensively.
- Updated Journal overview cards and resonance labels to recognize private episodes, repair arcs, milestones, shared references, callbacks, and open threads.
- Reworked Journal entries to show a bounded Continuity section with safe labels and notes rather than raw metadata.
- Added structural copy for adult-redacted episodes that explains gated details were left out of durable recall.
- Updated frontend UX and progress docs.

Commands run:
- `npm run lint` from `apps/web` - passed.
- `npm run build` from `apps/web` - passed, then `apps/web/next-env.d.ts` was restored to the checked-in dev route reference.
- `git diff --check` - passed.

Known limitations:
- This is a frontend presentation checkpoint; it relies on backend journal metadata being present after conversations are summarized.
- Malformed or unknown continuity metadata is ignored rather than surfaced.

## World-class continuation - episodic continuity signals

Completed in this checkpoint:
- Added deterministic journal continuity metadata for repair arcs, milestones, shared references, callback requests, open threads, steady exchanges, and adult-redacted episodes.
- Changed automatic journal typing so the strongest continuity signal becomes the journal type where useful, without a migration.
- Preserved unknown existing journal metadata while updating deterministic summaries.
- Restricted continuity notes to messages allowed for durable detail, so adult-mode scenes can create only a redaction cue rather than durable scene snippets.
- Added continuity labels and notes to prompt assembly without exposing raw JSON.
- Updated the private response planner to prioritize journal repair arcs, open threads, callbacks, shared references, milestones, and adult redaction cues.
- Added API regression coverage for SFW shared-reference/callback/open-thread metadata reaching debug prompt and response-plan context.
- Extended adult-mode journal redaction coverage to prove continuity notes do not retain adult-mode scene details.
- Updated memory and prompt assembly docs.

Commands run:
- `pytest tests/test_level2_state.py::test_journal_relationship_and_proactive_hooks_after_chat tests/test_prompt_memory_relationship.py::test_adult_mode_journal_omits_durable_callback_details -q` from `apps/api` - passed; 2 tests.
- `ruff check app/services/journal.py app/services/response_planner.py tests/test_level2_state.py tests/test_prompt_memory_relationship.py` from `apps/api` - first run caught one long test assertion.
- `ruff check app/services/journal.py app/services/response_planner.py tests/test_level2_state.py tests/test_prompt_memory_relationship.py` from `apps/api` after wrapping the assertion - passed.
- `pytest` from `apps/api` - passed; 70 tests.
- `ruff format .` from `apps/api` - passed; 1 file reformatted.
- `ruff check .` from `apps/api` after formatting - passed.
- `pytest tests/test_level2_state.py::test_journal_relationship_and_proactive_hooks_after_chat tests/test_prompt_memory_relationship.py::test_adult_mode_journal_omits_durable_callback_details -q` from `apps/api` after formatting - passed; 2 tests.
- `git diff --check` - passed.

Known limitations:
- Continuity classification is deterministic and marker-based; it is intentionally lightweight for the mock-first MVP.
- Existing journal rows gain continuity metadata when their conversation is summarized again rather than through a backfill migration.

## World-class continuation - authored scenario presets

Completed in this checkpoint:
- Replaced the plain scenario preset control in character settings with six authored SFW scenario cards.
- Kept the custom scenario text field so unknown imported values and user-authored scenes remain editable.
- Added active preset highlighting derived from normalized draft text rather than a separate state variable.
- Preserved the existing explicit save flow, backend contract, and adult-mode boundary separation.
- Updated frontend UX docs for the scenario preset picker.

Commands run:
- `npm run lint` from `apps/web` - passed.
- `npm run build` from `apps/web` - passed, then `apps/web/next-env.d.ts` was restored to the checked-in dev route reference.
- `git diff --check` - passed.

Known limitations:
- This is a frontend authoring checkpoint; scenario presets still flow through the existing `scenario_preset` profile field.
- Preset labels are SFW and deterministic; deeper scenario-specific planner behavior can be added later without changing the UI contract.

## World-class continuation - structured consent profile

Completed in this checkpoint:
- Added structured SFW consent-profile fields to character draft state: consent style, soft limits, hard limits, and aftercare style.
- Persisted those fields in existing `boundaries_json`, preserving unknown profile keys and avoiding a migration.
- Added consent-profile controls to the Adult settings panel beside age, intensity, private mode, and adult-memory controls.
- Extended the authored default character with structural consent guidance and hard-limit reinforcement.
- Added consent-profile lines to prompt assembly so the backend owns this guidance and the model receives it as private structural context.
- Added API-level debug prompt coverage proving updated consent-profile fields reach the assembled prompt without raw JSON exposure.
- Updated data model, prompt, safety, frontend UX, and progress docs.

Commands run:
- `pytest tests/test_prompt_memory_relationship.py -q` from `apps/api` - passed; 11 tests.
- `ruff check .` from `apps/api` - first run caught one long test assertion.
- `ruff check .` from `apps/api` after wrapping the assertion - passed.
- `npm run lint` from `apps/web` - passed.
- `npm run build` from `apps/web` - passed, then `apps/web/next-env.d.ts` was restored to the checked-in dev route reference.
- `pytest` from `apps/api` - passed; 70 tests.
- `ruff format .` from `apps/api` - passed; 1 file reformatted.
- `ruff check .` from `apps/api` after formatting - passed.
- `pytest tests/test_prompt_memory_relationship.py -q` from `apps/api` after formatting - passed; 11 tests.
- `git diff --check` - passed.

Known limitations:
- Consent-profile fields are structural text guidance; they do not replace hard safety gates or automated unsafe-content checks.
- Existing characters are not backfilled until edited or saved, though the default profile now includes these fields.

## World-class continuation - stale proactive note skipping

Completed in this checkpoint:
- Added a scheduler guard that checks the latest conversation message before creating a proactive note.
- If the latest message is a user reply newer than the queued job, the job is completed with `skipped_user_returned` instead of emitting a stale away-note.
- Preserved current behavior for legitimate due jobs where the latest user message predates the job.
- Kept private-thread, snooze, disabled-variant, cooldown, and delayed follow-up protections intact.
- Added regression coverage proving a queued thinking-of-you job is skipped after the user returns.
- Updated background-job and progress docs.

Commands run:
- `pytest tests/test_jobs_proactive_export.py -q` from `apps/api` - passed; 22 tests.
- `ruff check .` from `apps/api` - passed.
- `pytest` from `apps/api` - passed; 70 tests.
- `ruff format .` from `apps/api` - passed; 53 files unchanged.
- `ruff check .` from `apps/api` after formatting - passed.
- `git diff --check` - passed.

Known limitations:
- The guard compares against the queued job timestamp; it does not yet inspect per-job semantic context beyond whether the user returned.
- Manually forced debug notes can still be created when appropriate if the user has not returned after the job was queued.

## World-class continuation - proactive presence event cards

Completed in this checkpoint:
- Reworked proactive assistant messages in the chat surface into centered presence event cards.
- Preserved ordinary user, assistant, and system message grouping for normal conversation flow.
- Event cards use safe human labels from proactive metadata, delivery away-state, and bounded context such as relationship milestones, open threads, or callbacks.
- Kept provider, prompt, ids, milestone ids, and debug payloads out of the primary chat UI.
- Proactive cards keep a delete action while avoiding ordinary assistant reroll affordances that do not fit scheduled presence notes.
- Updated frontend UX and progress docs.

Commands run:
- `npm run lint` from `apps/web` - passed.
- `npm run build` from `apps/web` - passed, then `apps/web/next-env.d.ts` was restored to the checked-in dev route reference.
- `npm run lint` from `apps/web` after JSX cleanup - passed.
- `npm run build` from `apps/web` after JSX cleanup - passed, then `apps/web/next-env.d.ts` was restored again.
- `git diff --check` - passed.

Known limitations:
- This is a presentation checkpoint; proactive message creation remains deterministic backend logic.
- Visual verification is lint/build based because browser screenshot tooling is not installed.

## World-class continuation - relationship milestone presence notes

Completed in this checkpoint:
- Made `proactive_milestone_check` relationship-state-aware instead of a generic timed nudge.
- Milestone proactive jobs are only queued when the relationship timeline has an unnoted milestone.
- Due milestone notes now use the latest safe milestone summary in SFW copy and include bounded `relationship_milestone` metadata.
- Relationship metadata now records `proactive_milestones_noted` so the same milestone marker is not repeated.
- Preserved private-thread, snooze, disabled-variant, latest-message, and cooldown protections.
- Added regression coverage proving milestone jobs are skipped without milestones and contextual notes are created for newly crossed milestones.
- Updated background-job, data-model, relationship-engine, and progress docs.

Commands run:
- `pytest tests/test_jobs_proactive_export.py -q` from `apps/api` - passed; 21 tests.
- `ruff check .` from `apps/api` - passed.
- `pytest` from `apps/api` - passed; 69 tests.
- `ruff format .` from `apps/api` - passed; 1 file reformatted.
- `ruff check .` from `apps/api` after formatting - passed.
- `pytest tests/test_jobs_proactive_export.py -q` from `apps/api` after formatting - passed; 21 tests.
- `pytest` from `apps/api` after formatting - passed; 69 tests.
- `git diff --check` - passed.

Known limitations:
- Milestone note copy is deterministic SFW fallback text, not model-generated.
- Milestone dedupe is stored in relationship JSON metadata rather than a separate audit table.

## World-class continuation - memory conflict resolution

Completed in this checkpoint:
- Added a scoped `POST /characters/{character_id}/memories/{memory_id}/resolve` endpoint.
- Resolving keeps the selected memory, removes opposing memories in the same contradiction group, clears stale conflict links, and stamps bounded resolution metadata.
- Added a defensive `409` response when the selected memory has no active opposing conflict.
- Corrected frontend active-conflict detection so ordinary preference groups and resolved memories are not mislabeled as needing review.
- Added a Memory panel "Keep this version" action that refreshes side state and gives a clear success or error notice.
- Added regression coverage for successful conflict resolution and repeated no-conflict resolution.
- Updated API, memory-system, frontend UX, and progress docs.

Commands run:
- `pytest tests/test_level2_state.py -q` from `apps/api` - passed; 12 tests.
- `ruff check .` from `apps/api` - first run caught import ordering in `app/api/memory.py`.
- `ruff check app/api/memory.py --fix` from `apps/api` - fixed the import order.
- `ruff check .` from `apps/api` after the import fix - passed.
- `npm run lint` from `apps/web` - passed.
- `npm run build` from `apps/web` - passed, then `apps/web/next-env.d.ts` was restored to the checked-in dev route reference.
- `pytest` from `apps/api` - passed; 67 tests.
- `ruff format .` from `apps/api` - passed; 53 files unchanged.
- `ruff check .` from `apps/api` after formatting - passed.
- `git diff --check` - passed.

Known limitations:
- Conflict detection remains deterministic and preference-pattern based.
- Resolving a conflict removes opposing memories rather than archiving them in a separate audit trail.

## World-class continuation - visible relationship changes

Completed in this checkpoint:
- Added backend-owned `recent_changes` and `recent_change_summary` metadata for relationship message updates.
- Translated raw trust, warmth, closeness, tension, rhythm, and attachment deltas into bounded human-readable summaries.
- Kept the longer relationship timeline intact while giving the frontend a latest-exchange view for visible progression.
- Added frontend typing and cognition filtering for recent relationship changes so malformed or empty metadata is ignored.
- Reworked the Relationship panel to show a Recent Shifts section without exposing numeric deltas.
- Added regression coverage proving warm chat updates surface recent trust and warmth summaries.
- Updated relationship, data-model, frontend UX, and progress docs for the metadata contract.

Commands run:
- `pytest tests/test_prompt_memory_relationship.py -q` from `apps/api` - passed; 11 tests.
- `ruff check .` from `apps/api` - passed.
- `npm run lint` from `apps/web` - passed.
- `npm run build` from `apps/web` - passed, then `apps/web/next-env.d.ts` was restored to the checked-in dev route reference.
- `pytest` from `apps/api` - passed; 66 tests.
- `ruff format .` from `apps/api` - passed; 1 file reformatted.
- `ruff check .` from `apps/api` after formatting - passed.
- `pytest` from `apps/api` after formatting - passed; 66 tests.
- `git diff --check` - passed.

Known limitations:
- Recent shifts currently describe the latest relationship update only; the timeline remains the place for durable history.
- Change summaries are deterministic and phrase-based, which is appropriate for the mock-first MVP but not nuanced sentiment analysis.

## World-class continuation - emotionally reactive mock replies

Completed in this checkpoint:
- Reworked the deterministic mock provider so development chat replies feel less like status summaries.
- Mock replies now react to current-message cues such as tiredness, questions, thanks, anger, and repair context.
- Relationship mood/conflict now changes mock tone, including strained/repair-first wording.
- Selected memory, speech style, recent thread shape, and response-plan episode focus are still used without leaking private labels.
- Added tests proving response-plan context can influence the reply without exposing "Private response plan" or prompt internals.
- Added tests proving strained relationship context creates repair-oriented copy without echoing the user's message verbatim.
- Updated product and prompt docs for the mock-provider contract.

Commands run:
- `pytest tests/test_llm_providers.py tests/test_auth_chat.py -q` from `apps/api` - passed; 14 tests.
- `ruff check .` from `apps/api` - passed.
- `pytest` from `apps/api` - passed; 66 tests.
- `ruff format .` from `apps/api` - passed; 53 files unchanged.
- `ruff check .` from `apps/api` after formatting - passed.
- `git diff --check` - passed.

Known limitations:
- The mock provider is still deterministic scaffolding for local development, not a replacement for Ollama.
- Emotional cue detection is phrase-based and intentionally lightweight.

## World-class continuation - contextual unresolved-thread nudges

Completed in this checkpoint:
- Tightened episodic journal extraction so adult-mode user messages are omitted from durable callbacks and unresolved-thread text.
- Kept adult-mode journal summaries redacted while still noting that details were intentionally omitted.
- Made `proactive_unresolved_thread_nudge` use the latest safe journal unresolved thread or callback excerpt when available.
- Added bounded screening for proactive context snippets so unsafe or secret-like text is not copied into background notes.
- Added proactive metadata showing whether a nudge used `unresolved_thread` or `callback` context.
- Preserved the existing generic SFW open-thread nudge when no safe context is available.
- Added regression coverage for adult-mode journal callback redaction and safe contextual unresolved-thread proactive messages.
- Updated memory, safety, background-job, and progress docs.

Commands run:
- `pytest tests/test_prompt_memory_relationship.py tests/test_jobs_proactive_export.py -q` from `apps/api` - passed; 30 tests.
- `ruff check .` from `apps/api` - passed.
- `pytest` from `apps/api` - passed; 64 tests.
- `ruff format .` from `apps/api` - passed; 53 files unchanged.
- `ruff check .` from `apps/api` after formatting - passed.
- `git diff --check` - passed.

Known limitations:
- Contextual nudges are deterministic and use a bounded excerpt rather than model-generated personalization.
- Context comes from the latest conversation journal only, not a cross-thread unresolved-thread search.

## World-class continuation - debug memory pipeline visibility

Completed in this checkpoint:
- Added a debug-only `memory_pipeline` summary to `/debug/conversation/{conversation_id}` for recent user turns.
- The summary recomputes the same deterministic candidate decision used by storage and links any stored memory created from that message.
- Private conversations and memory-storage blocks now show explicit debug reasons such as `conversation_private` or `adult_memory_storage_disabled`.
- Normal chat response message metadata remains clean; memory pipeline internals are not added to primary chat responses.
- The frontend now fetches active-conversation debug data during side-state refresh and renders a compact Memory Pipeline section in the private Debug panel.
- Added regression coverage proving accepted/skipped decisions appear in debug while normal chat metadata does not leak pipeline details.
- Updated API, memory, frontend UX, and progress docs.

Commands run:
- `pytest tests/test_prompt_memory_relationship.py -q` from `apps/api` - passed; 10 tests.
- `ruff check .` from `apps/api` - passed.
- `npm run lint` from `apps/web` - passed.
- `npm run build` from `apps/web` - passed, then `apps/web/next-env.d.ts` was restored to the checked-in dev route reference.
- `pytest` from `apps/api` - passed; 62 tests.
- `ruff format .` from `apps/api` - passed; 53 files unchanged.
- `ruff check .` from `apps/api` after formatting - passed.
- `git diff --check` - passed.

Known limitations:
- The debug panel shows recent active-thread learning decisions only; it is not yet a searchable memory audit log across every conversation.
- Candidate decisions remain deterministic and trigger-based.

## World-class continuation - memory candidate pipeline

Completed in this checkpoint:
- Added a deterministic `MemoryCandidateDecision` analyzer so automatic memory extraction has explicit accept/skip reasons before storage.
- Preserved the existing safety posture: short, unsafe, structurally blocked, untriggered, empty, or preference-disabled candidates are skipped without storing rejected message text.
- Accepted automatic memories now store bounded extraction metadata with type, trigger, importance, confidence, and emotional weight.
- Scheduled `memory_extract` jobs now aggregate `accepted_types` and `skip_reasons` in their payloads for private debug visibility.
- Added direct analyzer coverage for safe skip reasons, preference controls, and boundary exceptions.
- Expanded scheduler regression coverage to prove accepted types, skip reasons, and accepted-memory extraction metadata are persisted correctly.
- Updated memory and background-job docs for the candidate pipeline and bounded job payloads.

Commands run:
- `pytest tests/test_prompt_memory_relationship.py tests/test_jobs_proactive_export.py -q` from `apps/api` - passed; 27 tests.
- `ruff check .` from `apps/api` - passed.
- `pytest` from `apps/api` - passed; 61 tests.
- `ruff format .` from `apps/api` - passed; 53 files unchanged.
- `git diff --check` - passed.

Known limitations:
- Candidate classification is still deterministic and trigger-based; it does not attempt semantic extraction beyond the lightweight MVP rules.
- Rejected candidate reasons are aggregated in scheduled jobs, but live chat does not yet surface per-message skip reasons in the debug panel.

## World-class continuation - bidirectional memory contradictions

Completed in this checkpoint:
- Strengthened preference contradiction handling without adding a migration.
- Contradictory preference memories now refresh the whole same-user, same-character contradiction group instead of only marking the newest item.
- Opposite-polarity memories no longer merge even when their text has high overlap.
- Both sides of a conflict now expose inspectable metadata, including contradiction status, forward links, backlinks, and newer-memory supersession hints.
- Editing or deleting a conflicting memory refreshes the affected group so stale contradiction links are cleared.
- Retrieval scoring now penalizes unresolved contradiction metadata, especially older memories contradicted by a newer item.
- Expanded the memory v2 API regression to prove contradiction backlinks and edit-based resolution work through real authenticated endpoints.
- Updated memory docs with the new contradiction behavior.

Commands run:
- `pytest tests/test_level2_state.py -q` from `apps/api` - passed; 11 tests.

Known limitations:
- Contradiction grouping remains deterministic and preference-pattern based; it does not yet detect arbitrary semantic conflicts.
- The API exposes contradiction metadata for inspection, but there is not yet a dedicated conflict-resolution UI beyond editing/deleting memory rows.

## World-class continuation - memory preference enforcement

Completed in this checkpoint:
- Made the character memory preference toggles real for automatic extraction.
- Added defensive backend preference parsing for `boundaries_json.memory_preferences`.
- `remember_preferences=false` now skips automatically learned preference memories from live chat and scheduled memory-extract jobs.
- `remember_emotional_notes=false` now skips automatic event and inside-joke memories.
- Boundary memories remain allowed because they encode safety, consent, and interaction limits.
- Manual memory creation remains available so the user can still save explicit notes by hand.
- Added live-chat and scheduled-job regression coverage for preference-aware extraction.
- Updated memory docs to describe automatic extraction controls and the boundary exception.

Commands run:
- `pytest tests/test_prompt_memory_relationship.py tests/test_jobs_proactive_export.py` from `apps/api` - passed; 26 tests.
- `ruff check .` from `apps/api` - first run caught import ordering; fixed it and reran successfully.
- `pytest` from `apps/api` - passed; 60 tests.
- `ruff format .` from `apps/api` - passed; 53 files unchanged.
- `ruff check .` from `apps/api` after formatting - passed.

Known limitations:
- Preference enforcement is deterministic and type-based; it does not perform semantic classification beyond the existing lightweight extractor.
- Manual memory creation is intentionally not blocked by these automatic extraction toggles.

## World-class continuation - relationship milestone anchors

Completed in this checkpoint:
- Added deterministic relationship milestone detection for first warmth, first trust, steady rhythm, and repair arcs.
- Milestones are stored once by id in relationship metadata to prevent duplicate timeline or memory writes.
- Milestone events are appended to the relationship timeline with human summaries and tags.
- Each milestone creates a durable `relationship_milestone` memory anchor with positive emotional weight so future prompts and the memory panel can surface meaningful progression.
- Added regression coverage proving milestone timeline events and memories are created once after thresholds are crossed.
- Updated relationship and memory docs to describe milestone metadata and memory anchors.

Commands run:
- `pytest tests/test_level2_state.py` from `apps/api` - passed; 11 tests.
- `ruff check .` from `apps/api` - passed.
- `pytest` from `apps/api` - passed; 58 tests.
- `ruff format .` from `apps/api` - passed; 53 files unchanged.
- `ruff check .` from `apps/api` after formatting - passed.

Known limitations:
- Milestones use deterministic thresholds and handwritten summaries rather than LLM-generated interpretation.
- Current milestone thresholds are intentionally modest MVP anchors and may need tuning after real usage.

## World-class continuation - delayed follow-up presence

Completed in this checkpoint:
- Added `proactive_delayed_double_text`, a SFW delayed follow-up job variant with type-aware content, label, away state, schedule, and response-planner label.
- Made delayed follow-ups stricter than normal check-ins: they only emit when the latest thread message is a normal assistant reply and skip if the user has already answered or the latest message is proactive.
- Threaded the new variant through character default proactive preferences, frontend character draft load/save, and the Presence controls as "Delayed follow-ups".
- Kept the new job under the existing anti-spam, snooze/disable, private-thread, and cooldown systems.
- Updated background-job, product-requirement, and data-model docs for the new job type.

Commands run:
- `pytest tests/test_jobs_proactive_export.py` from `apps/api` - passed; 17 tests.
- `npm run lint` from `apps/web` - passed.
- `npm run build` from `apps/web` - passed, then `apps/web/next-env.d.ts` was restored to the checked-in dev route reference.
- `ruff check .` from `apps/api` - passed.
- `ruff format .` from `apps/api` - passed; 53 files unchanged.
- `pytest` from `apps/api` - passed; 57 tests.
- `ruff check .` from `apps/api` after the full test run - passed.

Known limitations:
- Delayed follow-up copy is deterministic SFW fallback text, not generated per-thread by the LLM.
- The delay is fixed at 4 hours and uses the character-level presence controls rather than a per-thread schedule UI.

## World-class continuation - private conversation mode

Completed in this checkpoint:
- Added `metadata_json` to conversations through Alembic revision `0003_conversation_privacy`.
- Added `privacy_mode` support to conversation create/update APIs, response schemas, export JSON, and frontend conversation types.
- Implemented private-thread behavior: messages still persist in the thread, but chat skips memory extraction, memory recall timestamp updates, episodic journal updates, relationship mutation/decay, and proactive scheduling.
- Purges queued conversation jobs when an existing thread is switched private, with scheduler backstops for private proactive and memory jobs that still reach a worker.
- Stamps chat message metadata with the effective thread privacy mode for debug/audit visibility.
- Added rail controls for normal/private thread creation and a chat-header toggle/status that disables manual presence notes in private threads.
- Updated product, API, data model, safety/data-handling, and frontend UX docs for the private-thread contract.

Commands run:
- `pytest tests/test_level2_state.py tests/test_jobs_proactive_export.py tests/test_migrations.py` from `apps/api` - first run caught a test mismatch with privacy-mode job purging; adjusted the scheduler-backstop test and reran successfully; 26 tests. Reran after tightening read-side privacy behavior; passed.
- `ruff check .` from `apps/api` - first run caught import ordering; fixed it and reran successfully.
- `npm run lint` from `apps/web` - passed.
- `npm run build` from `apps/web` - passed, then `apps/web/next-env.d.ts` was restored to the checked-in dev route reference.
- `pytest` from `apps/api` - passed; 55 tests.
- `ruff format .` from `apps/api` - passed; 53 files unchanged.
- `ruff check .` from `apps/api` after formatting - passed.
- `alembic upgrade head` from `apps/api` - passed.

Known limitations:
- Private conversations still use existing character memories and journals during response planning; they only prevent new durable state from being written.
- Private mode is thread-level only. It is not yet a temporary per-message incognito toggle.

## World-class continuation - relationship-aware adult gates

Completed in this checkpoint:
- Added relationship-state awareness to the adult gate so repair-needed, strained, or high-tension relationships temporarily fall back to SFW even when structural age gates pass.
- Threaded the current relationship into chat message metadata, reasoning context, prompt assembly, debug previews, and `/characters/{character_id}/adult-status`.
- Kept the block reversible: normal repair language clears `repair_needed`, restores the clear relationship state, and makes adult mode available again once structural gates still pass.
- Added a regression test for the full API path: conflict creates a repair block, adult chat falls back to SFW, adult status explains why, and repair restores availability.

Commands run:
- `pytest tests/test_prompt_memory_relationship.py` from `apps/api` - passed; 7 tests.
- `pytest tests/test_auth_chat.py tests/test_prompt_memory_relationship.py` from `apps/api` - passed; 13 tests.
- `ruff check .` from `apps/api` - passed.
- `ruff format .` from `apps/api` - passed; 51 files unchanged.
- `ruff check .` from `apps/api` after formatting - passed.

Known limitations:
- Relationship-aware adult availability is intentionally conservative: it only blocks active repair, strained conflict, or high tension, not every low-trust or new-relationship state.
- The frontend already displays adult-status reasons, but there is not yet a dedicated repair CTA in the adult settings panel.

## World-class continuation - private response planner

Completed in this checkpoint:
- Added `app.services.response_planner`, a deterministic backend planner that creates a compact private response plan summary without chain-of-thought.
- The planner uses character persona, relationship state, retrieved memories, episodic journals, recent messages, current message, safety mode, time context, and pending proactive events.
- Threaded the response plan through live chat, reroll, prompt assembly, and the private debug character endpoint.
- Bumped the prompt version to `persona_memory_relationship_episode_plan_v3`.
- Added private debug visibility for `response_plan_summary` while keeping assistant message content and metadata clean.
- Added tests proving the prompt/debug context includes the private plan and normal chat responses do not leak it.

Commands run:
- `pytest tests/test_prompt_memory_relationship.py tests/test_auth_chat.py` from `apps/api` - passed; 12 tests.
- `npm run lint` from `apps/web` - passed.
- `npm run build` from `apps/web` - passed.
- `ruff check .` from `apps/api` - first run caught one line-length issue in the new planner; fixed it and reran successfully.
- `ruff format .` from `apps/api` - passed; 1 file reformatted, 50 unchanged.
- `ruff check .` from `apps/api` after formatting - passed.
- `git diff --check` - passed after restoring the generated `next-env.d.ts` route import.

Known limitations:
- The response planner is deterministic and compact; it is a state summary, not an LLM-generated strategy.
- Pending proactive context is summarized by job type labels rather than full scheduled-job payload details.

## World-class continuation - proactive presence controls

Completed in this checkpoint:
- Added character-level proactive presence preferences in `boundaries_json`, including enabled/disabled state, snooze-until timestamp, per-variant note controls, and bounded cooldown hours.
- Updated proactive job scheduling so disabled, snoozed, or variant-disabled characters do not receive new proactive jobs after chat.
- Updated due proactive job processing so already-queued jobs respect later pause/snooze settings and finish cleanly with debug metadata instead of emitting a message.
- Kept manual check-ins subject to the same user controls and updated the frontend notice for paused/snoozed/cooldown states.
- Added structural backend tests for disabled proactive scheduling and snoozed due-job skipping without explicit adult fixtures.
- Added Presence controls to the character builder for allowing notes, snoozing 24h/7d, clearing snooze, and choosing note variants.
- Updated the conversation rail to show presence paused/snoozed/on labels instead of raw intensity/debug state.

Commands run:
- `pytest tests/test_jobs_proactive_export.py` from `apps/api` - passed; 13 tests.
- `ruff check .` from `apps/api` - passed.
- `npm run lint` from `apps/web` - passed.
- `npm run build` from `apps/web` - passed.
- `git diff --check` - passed after restoring the generated `next-env.d.ts` route import.

Known limitations:
- Presence controls are character-level, not per-conversation.
- Snooze controls currently offer fixed 24-hour and 7-day options rather than a custom scheduler UI.

## World-class continuation - companion cognition panel polish

Completed in this checkpoint:
- Added a frontend cognition helper module for translating memory, journal, relationship, timeline, and overview state into concise user-facing summaries.
- Reworked the Memory panel around recall, anchors, emotional texture, resonance, freshness, and source labels while preserving add/edit/pin/delete/forget actions.
- Reworked the Journal panel around episodes, open loops, callbacks, and emotional markers while preserving manual journal creation.
- Reworked the Relationship panel around phase, temperature, momentum, repair state, and readable timeline copy instead of raw metric bars.
- Reworked the Overview panel into a compact companion-state snapshot for bond, memory, journal, and presence.
- Updated inspector badges and summaries so primary companion navigation no longer shows raw warmth values or job counts.
- Added `last_interaction_at` to the frontend relationship type and empty state after the production build caught the missing field.

Commands run:
- `npm run lint` from `apps/web` - passed.
- `npm run build` from `apps/web` - first run failed on missing `Relationship.last_interaction_at`; fixed the type/default state and reran.
- `npm run lint` from `apps/web` after the type fix - passed.
- `npm run build` from `apps/web` after the type fix - passed.
- `git diff --check` - passed.

Known limitations:
- This checkpoint is presentation-only; the underlying memory and relationship algorithms were not changed.
- Browser screenshot tooling is still not installed, so visual verification remains lint/build based.

## World-class continuation - deep character builder and adult memory rules

Completed in this checkpoint:
- Expanded the default Eidolon character into an authored SFW profile with relationship type, flaws, values, humor, interests, backstory, greeting, nicknames, scenario, and privacy-oriented memory preferences.
- Added prompt assembly support for the richer character profile without dumping raw JSON into the prompt.
- Added backend memory-storage rules so private mode blocks new memory extraction and adult-mode memory storage is disabled unless explicitly enabled in the character profile.
- Added a structural regression test proving adult-mode memory storage is blocked by default and can be enabled without explicit adult fixtures.
- Reworked the character builder UI to edit identity, explicit age, relationship type, personality, flaws, values, speech, humor, greeting, nicknames, interests, scenario, boundaries, and memory preferences.
- Reworked adult settings to expose age gate state, explicit character age, adult eligibility, intensity, private mode, and adult memory storage.
- Updated character save behavior to preserve unknown `boundaries_json` keys and defensively parse numeric draft values.
- Replaced primary rail raw age/intensity output with human readiness and memory posture labels.

Commands run:
- `cd apps/api && pytest tests/test_prompt_memory_relationship.py tests/test_auth_chat.py` - passed; 11 tests.
- `cd apps/web && npm run lint` - passed.
- `cd apps/web && npm run build` - passed.
- `cd apps/api && pytest` - passed; 47 tests.
- `cd apps/api && ruff check .` - passed.
- `cd apps/api && ruff format .` - passed; 1 file reformatted, 49 unchanged.
- `pytest tests/test_auth_chat.py` from `apps/api` after the delete-endpoint cleanup - passed; 6 tests.
- `ruff check .` from `apps/api` after the cleanup - passed.
- `npm run lint` from `apps/web` after restoring `next-env.d.ts` - passed.
- `git diff --check` - passed after restoring the generated `next-env.d.ts` route import.

Known limitations:
- Existing characters are not automatically backfilled with the richer default profile; editing and saving a character will persist the new builder fields.
- Private mode currently controls new deterministic memory extraction. It does not retroactively wipe existing memories.

## World-class continuation - immersive chat polish

Completed in this checkpoint:
- Replaced visible mock-provider reply prefixes with deterministic but natural SFW companion prose that uses prompt-derived style, memory, relationship, user name, and thread continuity without exposing `[mock]` or prompt internals.
- Added a protected single-message delete endpoint scoped through the existing conversation ownership check.
- Added frontend message deletion from the chat surface with confirmation, local state cleanup, and side-state refresh.
- Hardened frontend SSE parsing against malformed stream events.
- Rebuilt the primary chat surface with grouped messages, humanized companion presence, natural delivery labels, improved empty and streaming states, and no raw provider, prompt, relationship-number, or typing-millisecond display in the main chat.
- Added regression tests for mock marker cleanliness and cross-user message-delete isolation.

Commands run:
- `docker compose up -d postgres` - passed; `eidolon-postgres` running.
- `cd apps/api && pytest tests/test_auth_chat.py tests/test_llm_providers.py` - passed; 12 tests.
- `cd apps/web && npm run lint` - passed.
- `cd apps/api && pytest` - passed; 46 tests.
- `cd apps/api && ruff check .` - passed.
- `cd apps/web && npm run build` - passed.
- `cd apps/api && ruff format .` - passed; 50 files unchanged.
- `git diff --check` - passed.

Known limitations:
- Browser screenshot tooling is still not installed; UI validation for this checkpoint is lint/build rather than visual screenshot inspection.
- The mock provider remains deterministic and intentionally lightweight; it is more natural now, but it is still not a real local model.

## World-class continuation - final runtime smoke

Completed in this checkpoint:
- Restarted fresh API and web dev servers from the current working tree.
- Confirmed API, database, mock LLM, and web root health after the latest safety, migration, privacy, docs, and Makefile hardening.

Commands run:
- `cd apps/api && python -m uvicorn app.main:app --host 0.0.0.0 --port 8000` - running on port 8000.
- `cd apps/web && npm run dev` - running on port 3000.
- `curl -sS -i http://localhost:8000/health` - passed with HTTP 200.
- `curl -sS -i http://localhost:8000/health/db` - passed with HTTP 200.
- `curl -sS -i http://localhost:8000/health/llm` - passed with HTTP 200 and mock provider.
- `curl -sS -I http://localhost:3000` - passed with HTTP 200.

Known limitations:
- Browser screenshot tooling is still not installed; UI validation is lint/build plus HTTP runtime smoke.

## World-class continuation - local verify hardening

Completed in this checkpoint:
- Updated `make verify` to run Alembic migrations before backend tests.
- Added backend `ruff format --check` to local verification, matching CI's formatting gate.
- Added `api-migrate` and `api-format-check` Make targets.
- Proved the strengthened local verify chain end to end.

Commands run:
- `make verify` - first run hung at Alembic because the unapproved sandboxed `make` process could not reach local Postgres.
- `make verify` with approval - passed: Alembic upgrade, 45 backend tests, Ruff check, Ruff format check, frontend lint, and frontend build.
- `git diff --check` - passed before this progress-log update.

Known limitations:
- `make verify` needs local Postgres access; in this sandboxed environment that means running it with the approved `make verify` prefix.

## World-class continuation - memory extraction safety parity

Completed in this checkpoint:
- Centralized structural blocked-content detection in `app.services.safety`.
- Kept live chat behavior as a readable 400 while allowing non-HTTP callers to share the same safety predicate.
- Updated Memory v2 extraction so inline and scheduled/backfill extraction silently skip structurally blocked content instead of making it durable.
- Added a scheduled memory-extract regression proving blocked structural content is skipped and no memory row is created.
- Updated safety docs for memory extraction parity.

Commands run:
- `cd apps/api && pytest` - passed; 45 tests.
- `cd apps/api && ruff check .` - passed.
- `cd apps/api && ruff format .` - passed; 50 files unchanged.

Known limitations:
- The structural blocked-content screen remains pattern/term based; it is not a full moderation classifier.

## World-class continuation - export isolation coverage

Completed in this checkpoint:
- Added a cross-user export regression test proving one account export does not include another user's email, conversation id, or message/memory content.
- Kept the existing secret/hash exclusion test intact.
- Verified the migration-backed backend suite with the new privacy coverage.

Commands run:
- `cd apps/api && pytest` - passed; 44 tests.
- `cd apps/api && ruff check .` - passed.
- `cd apps/api && ruff format .` - passed; 50 files unchanged.

Known limitations:
- Export is account-scoped JSON only; richer selective export/import remains future UX polish.

## World-class continuation - docs consistency pass

Completed in this checkpoint:
- Updated memory docs so episodic journals, contradiction metadata, decay/forgetting, and edit/delete/clear controls are described as implemented Level 2 behavior rather than future work.
- Updated relationship docs so absence decay via reads and jobs is described as current behavior.
- Updated roadmap and risk docs for account erasure and memory edit/delete controls.
- Retitled the frontend original nice-to-have list to avoid implying implemented Level 2 controls are still missing.
- Rescanned docs outside the historical progress log for stale “later/not implemented/Level 2 needs” language.

Commands run:
- Stale-doc scan for obsolete “later/not implemented” phrases outside `docs/GOAL_PROGRESS.md` - no matches.
- `git diff --check` - passed before this progress-log update.

Known limitations:
- Historical checkpoint entries in `docs/GOAL_PROGRESS.md` intentionally preserve older known limitations and findings from the time they were written.

## World-class continuation - migration-backed test hardening

Completed in this checkpoint:
- Changed backend test setup to apply Alembic `upgrade head` at session startup instead of creating tables directly from SQLAlchemy metadata.
- Added a migration regression test that confirms the test database is at `0002_level2_state`, has Memory v2 columns, has Relationship v2 columns, and includes the `episodic_journals` table.
- Added Alembic `path_separator = os` configuration to remove the migration config deprecation warning from test runs.
- Updated testing docs so future tests keep migrations in the validation path.

Commands run:
- `cd apps/api && pytest` - initially passed with 43 tests and one Alembic config warning.
- `cd apps/api && ruff check . --fix` - fixed test import ordering.
- `cd apps/api && pytest` - passed after Alembic config update; 43 tests and no warnings.
- `cd apps/api && ruff check .` - passed.
- `cd apps/api && ruff format .` - passed; 50 files unchanged after the import fix.
- `git diff --check` - passed.

Known limitations:
- Migration tests assert the current head and critical Level 2 schema shape. They do not perform destructive downgrade/upgrade cycles against the shared local development database.

## World-class continuation - adult gate persistence hardening

Completed in this checkpoint:
- Added backend validation so character create/update requests cannot persist `adult_mode_allowed=true` without an explicit character age of 18 or older.
- Added structural minor-age pattern blocking before chat prompt assembly or memory extraction.
- Updated the adult settings panel so the adult-mode checkbox is disabled until the character has an explicit 18+ age, and lowering the age clears the draft adult-mode flag.
- Added API regression tests for invalid adult-mode character configuration and structural minor-age prompt rejection.
- Updated the safety and API contract docs.

Commands run:
- `docker compose up -d postgres` - initially blocked by Docker socket sandbox permissions; passed after approval, with `eidolon-postgres` running.
- `cd apps/api && pip install -e ".[dev]"` - passed.
- `cd apps/api && alembic upgrade head` - passed.
- `cd apps/api && pytest` - passed; 42 tests.
- `cd apps/api && ruff check .` - passed.
- `cd apps/api && ruff format .` - passed; 49 files unchanged.
- `cd apps/web && npm install` - passed; already up to date.
- `cd apps/web && npm run lint` - passed.
- `cd apps/web && npm run build` - passed after restoring the generated `next-env.d.ts` dev-route reference.
- `curl -sS -i http://localhost:8000/health` - passed with HTTP 200 after starting a fresh API server.
- `curl -sS -i http://localhost:8000/health/db` - passed with HTTP 200.
- `curl -sS -i http://localhost:8000/health/llm` - passed with HTTP 200 and mock provider.
- `curl -sS -I http://localhost:3000` - passed with HTTP 200 after starting a fresh web dev server.
- Forbidden dependency name scan across package/config/docs - no matches.
- `git diff --check` - passed.

Known limitations:
- Safety rejection is a structural term/pattern screen, not a comprehensive classifier. It is intentionally conservative and SFW-testable for the zero-cost MVP.

## World-class continuation - proactive message realism

Completed in this checkpoint:
- Added SFW message variants for inactivity, morning, goodnight, thinking-of-you, milestone, unresolved-thread, and manual proactive jobs.
- Added `proactive_type` and `proactive_label` metadata to proactive assistant messages and job result payloads.
- Updated the chat message metadata display to show the user-facing proactive label instead of a generic proactive marker.
- Preserved per-conversation cooldown across different proactive variants so queued morning/goodnight/thinking nudges cannot stack into spam.
- Updated debug proactive trigger to use the manual proactive variant.
- Added tests proving the scheduler creates the thinking-of-you variant and that cross-variant cooldown skips the second due proactive job.
- Updated proactive requirements and background-job docs.

Commands run:
- `cd apps/api && pytest` - passed; 41 tests.
- `cd apps/api && ruff check .` - passed.
- `cd apps/api && ruff format .` - passed; 49 files unchanged.
- `cd apps/web && npm run lint` - passed.
- `cd apps/web && npm run build` - passed after restoring the generated `next-env.d.ts` dev-route reference.
- `cd apps/api && alembic upgrade head` - passed.
- `curl -sS -i http://localhost:8000/health` - passed with HTTP 200.
- `curl -sS -i http://localhost:8000/health/db` - passed with HTTP 200.
- `curl -sS -i http://localhost:8000/health/llm` - passed with HTTP 200 and mock provider.
- `curl -sS -I http://localhost:3000` - passed with HTTP 200.
- `git diff --check` - passed.

Known limitations:
- Proactive text is deterministic SFW fallback text; it does not call the LLM in background jobs, keeping tests/Ollama optional and avoiding runtime dependency failures.
- Browser-level visual verification is still not installed; no browser binary was available in the workspace.

## World-class continuation - scheduled memory extraction

Completed in this checkpoint:
- Implemented `memory_extract` scheduled-job processing in the PostgreSQL-backed scheduler.
- Supports conversation-level recent user-message scans and single-message extraction through `conversation_id` plus `message_id` payloads.
- Reuses the existing Memory v2 extractor, including unsafe-term filtering, dedupe/merge, contradiction metadata, confidence, and scoring behavior.
- Adds safe failure handling when a memory-extract job references a missing, non-user, or cross-scope message.
- Added tests proving successful job extraction persists one memory and invalid message jobs fail with safe error text.
- Updated memory and background-job docs.

Commands run:
- `cd apps/api && pytest` - passed; 40 tests.
- `cd apps/api && ruff check .` - passed.
- `cd apps/api && ruff format .` - passed; 49 files unchanged.
- `cd apps/web && npm run lint` - passed.
- `cd apps/web && npm run build` - passed after restoring the generated `next-env.d.ts` dev-route reference.
- `cd apps/api && alembic upgrade head` - passed.
- `curl -sS -i http://localhost:8000/health` - passed with HTTP 200.
- `curl -sS -i http://localhost:8000/health/db` - passed with HTTP 200.
- `curl -sS -i http://localhost:8000/health/llm` - passed with HTTP 200 and mock provider.
- `curl -sS -I http://localhost:3000` - passed with HTTP 200.
- `git diff --check` - passed.

Known limitations:
- Chat still extracts obvious memories inline; scheduled extraction is now available for backlog or future async paths.
- Browser-level visual verification is still not installed; no browser binary was available in the workspace.

## World-class continuation - relationship decay persistence

Completed in this checkpoint:
- Added `get_current_relationship()` so relationship reads, debug prompt previews, and prompt reasoning context apply and persist absence decay before returning state.
- Queued one pending `relationship_decay` job per user-character pair after relationship updates.
- Added scheduler support for due `relationship_decay` jobs, with safe result metadata and automatic scheduling of the next future decay check.
- Preserved conversation cleanup semantics by deleting conversation-scoped jobs while leaving character-scoped relationship maintenance jobs intact.
- Added tests proving chat queues relationship decay, relationship reads persist absence drift, scheduler jobs apply decay, and recurring future decay is queued.
- Updated relationship, background-job, and acceptance docs.

Commands run:
- `cd apps/api && pytest` - first rerun exposed stale assumptions in conversation-job cleanup tests; fixed to check only conversation-scoped jobs.
- `cd apps/api && pytest` - passed after recurring relationship-decay scheduling; 38 tests.
- `cd apps/api && ruff check .` - passed.
- `cd apps/api && ruff format .` - passed; 49 files unchanged.
- `cd apps/web && npm run lint` - passed.
- `cd apps/web && npm run build` - passed after restoring the generated `next-env.d.ts` dev-route reference.
- `cd apps/api && alembic upgrade head` - passed.
- `curl -sS -i http://localhost:8000/health` - passed with HTTP 200 after starting a fresh API server.
- `curl -sS -i http://localhost:8000/health/db` - passed with HTTP 200.
- `curl -sS -i http://localhost:8000/health/llm` - passed with HTTP 200 and mock provider.
- `curl -sS -I http://localhost:3000` - initially found no web dev server; passed with HTTP 200 after starting `npm run dev`.
- `git diff --check` - passed.

Known limitations:
- Browser-level visual verification is still not installed; no browser binary was available in the workspace.

## World-class continuation - privacy action UX hardening

Completed in this checkpoint:
- Kept account-deleted, session-expired, and logged-out notices visible on the auth screen after app state is cleared.
- Converted privacy actions for proactive check-ins, chat clearing, export, and account deletion to report readable UI errors instead of allowing unhandled promise failures.
- Added a zero-argument public logout wrapper so React click events cannot be mistaken for internal reset options.
- Preserved real non-auth bootstrap errors as errors while using a session-expired notice only for 401 session failures.
- Added an export-ready notice after JSON export is prepared.

Commands run:
- `cd apps/web && npm run lint` - passed.
- `cd apps/web && npm run build` - passed after restoring the generated `next-env.d.ts` dev-route reference.
- `cd apps/api && pytest` - passed; 36 tests.
- `cd apps/api && ruff check .` - passed.
- `cd apps/api && ruff format .` - passed; 49 files unchanged.
- `curl -sS -i http://localhost:8000/health` - passed with HTTP 200.
- `curl -sS -i http://localhost:8000/health/db` - passed with HTTP 200.
- `curl -sS -i http://localhost:8000/health/llm` - passed with HTTP 200 and mock provider.
- `curl -sS -I http://localhost:3000` - passed with HTTP 200.
- `git diff --check` - passed.

Known limitations:
- Browser-level visual verification is still not installed.

## World-class continuation - refresh-token sessions

Completed in this checkpoint:
- Activated the existing `refresh_tokens` table with random opaque refresh tokens, SHA-256 token hashes, expiry validation, rotation, and revocation.
- Added `JWT_REFRESH_TOKEN_EXPIRE_DAYS` settings validation and a typed refresh lifetime helper.
- Updated register and login to return access plus refresh tokens.
- Added `POST /auth/refresh` rotation and `POST /auth/logout` refresh-token revocation.
- Wired the frontend to persist refresh tokens locally, rotate them after access-token 401s, and revoke them on logout.
- Added tests for refresh-token rotation, old-token reuse rejection, logout revocation, and invalid refresh-token lifetime config.
- Updated auth/data-model/tech-stack docs to reflect PostgreSQL-backed refresh-token sessions.

Commands run:
- `cd apps/api && pytest` - passed; 36 tests.
- `cd apps/api && ruff check .` - passed.
- `cd apps/api && ruff format .` - passed; 49 files unchanged.
- `cd apps/web && npm run lint` - passed.
- `cd apps/web && npm run build` - passed after restoring the generated `next-env.d.ts` dev-route reference.
- Local Node auth smoke for register, refresh rotation, old refresh-token rejection, logout revocation, login, and account deletion - first blocked by sandbox local-socket `EPERM`, rerun with approval passed.
- `cd apps/api && alembic upgrade head` - passed.
- `curl -sS -i http://localhost:8000/health` - passed with HTTP 200.
- `curl -sS -i http://localhost:8000/health/db` - passed with HTTP 200.
- `curl -sS -i http://localhost:8000/health/llm` - passed with HTTP 200 and mock provider.
- `curl -sS -I http://localhost:3000` - passed with HTTP 200.
- `git diff --check` - passed.

Known limitations superseded by later checkpoints:
- This checkpoint initially stored refresh tokens in browser localStorage. The
  later session-privacy checkpoint moved refresh tokens to HttpOnly cookies,
  deleted legacy browser-stored auth values during migration, and kept access
  tokens in memory only.
- Browser-level visual verification was still not installed at that point.

## World-class continuation - account erasure

Completed in this checkpoint:
- Added `DELETE /account` with current-password verification and exact `DELETE MY ACCOUNT` confirmation.
- Uses PostgreSQL cascades to remove the current user and dependent characters, conversations, messages, memories, journals, relationship state, refresh tokens, and scheduled jobs.
- Added endpoint tests for bad-password rejection, successful account erasure, stale-token invalidation, survivor-user preservation, and absence of erased user-scoped rows.
- Added the account deletion control to the data panel behind the existing destructive-action confirmation plus password and typed phrase.
- Documented the new endpoint in `docs/06_API_CONTRACT.md`.

Commands run:
- `cd apps/api && pytest` - passed; 34 tests.
- `cd apps/api && ruff check .` - passed.
- `cd apps/api && ruff format .` - passed; 49 files unchanged.
- `cd apps/web && npm run lint` - passed.
- `cd apps/web && npm run build` - passed after restoring the generated `next-env.d.ts` dev-route reference.
- `cd apps/api && alembic upgrade head` - passed.
- `curl -sS -i http://localhost:8000/health` - passed with HTTP 200 after restarting the API server.
- `curl -sS -i http://localhost:8000/health/db` - passed with HTTP 200.
- `curl -sS -i http://localhost:8000/health/llm` - passed with HTTP 200 and mock provider.
- `curl -sS -I http://localhost:3000` - passed with HTTP 200.
- `git diff --check` - passed.

Known limitations:
- Account deletion relies on database cascades rather than a visible deletion audit log.
- Browser-level visual verification is still not installed.

## World-class continuation - conversation wipe and job cleanup

Completed in this checkpoint:
- Updated conversation message clearing to also remove scheduled jobs scoped to that conversation payload.
- Updated conversation deletion to remove messages and scheduled jobs before deleting the conversation row.
- Fixed a SQLAlchemy delete edge case where ORM deletion attempted to null non-null `messages.conversation_id` values.
- Added tests proving clear-chat and delete-thread operations remove queued proactive jobs.

Commands run:
- `cd apps/api && pytest` - first rerun found the ORM nulling issue in conversation deletion.
- `cd apps/api && pytest` - passed after switching deletion to explicit message/job/conversation cleanup; 33 tests.
- `cd apps/api && ruff check .` - passed.
- `cd apps/api && ruff format .` - passed; 49 files unchanged.
- `curl -sS -i http://localhost:8000/health` - passed with HTTP 200 after restarting the API server.
- `curl -sS -i http://localhost:8000/health/db` - passed with HTTP 200 after restarting the API server.
- `curl -sS -I http://localhost:3000` - passed with HTTP 200.
- `git diff --check` - passed.

Known limitations:
- Conversation-scoped scheduled jobs are matched by JSON payload because the MVP schema does not give `scheduled_jobs` a first-class `conversation_id` column.
- Browser-level visual verification is still not installed.

## World-class continuation - production debug route hardening

Completed in this checkpoint:
- Added `ENABLE_DEBUG_ROUTES` config with production-default debug route lockout.
- Kept debug endpoints automatically available in development and testing so the local debug panel and test suite remain ergonomic.
- Added a shared debug-route guard returning a generic 404 when production debug routes are not explicitly enabled.
- Added config coverage proving production requires opt-in while testing remains available.
- Documented the production opt-in behavior in `.env.example` and `docs/06_API_CONTRACT.md`.

Commands run:
- `cd apps/api && pytest` - passed; 32 tests.
- `cd apps/api && ruff check . --fix` - fixed import ordering in `app/api/debug.py`.
- `cd apps/api && ruff check .` - passed.
- `cd apps/api && ruff format .` - passed; 49 files unchanged.
- `curl -sS -i http://localhost:8000/health` - passed with HTTP 200 after restarting the API server.
- `curl -sS -i http://localhost:8000/health/db` - passed with HTTP 200 after restarting the API server.
- `curl -sS -i http://localhost:8000/debug/jobs` - returned authenticated-only HTTP 401 in development, confirming the dev route remains reachable but private.
- `git diff --check` - passed.

Known limitations:
- There is still no admin role model; debug remains authenticated, owner-scoped, and environment-gated rather than role-gated.
- Browser-level visual verification is still not installed.

## World-class continuation - PostgreSQL scheduler runner

Completed in this checkpoint:
- Added APScheduler as the lightweight, approved wake-up mechanism for PostgreSQL-owned `scheduled_jobs`.
- Added scheduler settings for enablement, tick interval, job batch limit, proactive inactivity, and proactive cooldown with startup validation.
- Added `app.services.scheduler.process_due_jobs` for deterministic job processing without starting a background loop in tests.
- Wired FastAPI lifespan to start APScheduler only when `ENABLE_SCHEDULER=true`; tests keep `ENABLE_SCHEDULER=false`.
- Implemented safe processing for `maintenance_noop`, Level 2 proactive job types, and `proactive_message_create`; unsupported jobs are marked failed with bounded safe text.
- Fixed the queued proactive path so due jobs trust their `run_at` timing while cooldown rules still prevent repeated check-ins.
- Documented scheduler env vars and the PostgreSQL source-of-truth lifecycle in `docs/10_BACKGROUND_JOBS.md`.

Commands run:
- `cd apps/api && pip install -e ".[dev]"` - passed; installed APScheduler and tzlocal.
- `cd apps/api && alembic upgrade head` - passed.
- `cd apps/api && pytest` - passed; 31 tests.
- `cd apps/api && ruff check .` - passed.
- `cd apps/api && ruff format .` - passed; 49 files unchanged.
- `cd apps/web && npm run lint` - passed.
- `cd apps/web && npm run build` - passed after restoring the generated `next-env.d.ts` dev-route reference.
- `curl -sS -i http://localhost:8000/health` - passed with HTTP 200.
- `curl -sS -i http://localhost:8000/health/db` - passed with HTTP 200.
- `curl -sS -i http://localhost:8000/health/llm` - passed with HTTP 200 and mock provider.
- `curl -sS -i http://localhost:3000` - passed with HTTP 200.
- `git diff --check` - passed.

Known limitations:
- The scheduler is implemented and wired, but remains disabled by default until deployment sets `ENABLE_SCHEDULER=true`.
- Browser-level visual verification is still not installed.

## World-class continuation - privacy controls and operational debug

Completed in this checkpoint:
- Extracted proactive check-in, clear-chat, and account export actions into `components/eidolon/use-privacy-controller.ts`.
- Reduced the main controller hook to 302 lines while preserving export, proactive queueing, chat clearing, and side-state refresh behavior.
- Upgraded the data panel with account-scoped export language, message/memory/thread impact counts, current-thread context, and an explicit confirmation gate before destructive cleanup actions become available.
- Upgraded the debug panel with provider, pending-job, failed-job, prompt-version, prompt-size, job status, and conversation recency summaries while keeping prompt preview bounded and private.
- Upgraded the settings panel with local-account and age-gate context plus clearer logout semantics.

Commands run:
- `cd apps/web && npm run lint` - passed.
- `cd apps/web && npm run build` - passed after restoring the generated `next-env.d.ts` dev-route reference.
- `cd apps/api && alembic upgrade head` - passed.
- `cd apps/api && pytest` - passed; 29 tests.
- `cd apps/api && ruff check .` - passed.
- `cd apps/api && ruff format .` - passed; 48 files unchanged.
- `curl -sS http://127.0.0.1:8000/health && curl -sS http://127.0.0.1:8000/health/db && curl -sS http://127.0.0.1:8000/health/llm` - passed with API ok, DB ok, LLM mock ok after restarting dev servers.
- `curl -I http://127.0.0.1:3000` - passed with HTTP 200 after restarting dev servers.

Known limitations:
- The main controller still owns auth form state, session bootstrap, content mode, and global busy/error/notice state.
- Browser-level visual verification is still not installed.

## World-class continuation - companion state and inspector cockpit

Completed in this checkpoint:
- Extracted relationship, adult-status, jobs, debug payload, panel selection, timeline derivation, and side-state refresh into `components/eidolon/use-companion-state-controller.ts`.
- Reduced the main controller hook from 376 lines to 341 lines while preserving auth bootstrap, side-state refresh, memory/journal hydration, chat loading, and runtime state reset.
- Upgraded the inspector from a plain tab grid into grouped State/Memory/Control navigation with live badges for mood, warmth, memory count, journal count, content mode, provider, and conversation count.
- Added an active inspector header with concise summaries for the selected panel while keeping prompt/debug details confined to the debug panel.
- Kept the UI dependency-free and text-first.

Commands run:
- `cd apps/web && npm run lint` - passed.
- `cd apps/web && npm run build` - passed after Turbopack port-binding approval.
- `cd apps/api && alembic upgrade head` - passed.
- `cd apps/api && pytest` - passed; 29 tests.
- `cd apps/api && ruff check .` - passed.
- `cd apps/api && ruff format .` - passed; 48 files unchanged.
- `curl -sS http://127.0.0.1:8000/health && curl -sS http://127.0.0.1:8000/health/db && curl -sS http://127.0.0.1:8000/health/llm` - passed with API ok, DB ok, LLM mock ok.
- `curl -I http://127.0.0.1:3000` - passed with HTTP 200.

Known limitations:
- The main controller still owns auth/account, proactive trigger, data export, and clear-message orchestration.
- Browser-level visual verification is still not installed.

## World-class continuation - navigation controller and rail command surface

Completed in this checkpoint:
- Extracted character, conversation, title, and thread-search state plus selection/create/save/delete/search handlers into `components/eidolon/use-navigation-controller.ts`.
- Reduced the main controller hook from 571 lines to 376 lines while preserving auth bootstrap, chat loading, side-state refresh, character editing, thread creation, title saving, and search behavior.
- Upgraded the workspace rail with active-first character ordering, per-character thread counts, profile metadata, thread chronology, clearer current-character thread counts, enter-to-create character flow, and explicit search empty states.
- Kept the rail text-first and dependency-free; no new frontend libraries were added.

Commands run:
- `cd apps/web && npm run lint` - passed.
- `cd apps/web && npm run build` - passed after removing stale bootstrap setters and restoring generated `next-env.d.ts` churn.
- `cd apps/api && alembic upgrade head` - passed.
- `cd apps/api && pytest` - passed; 29 tests.
- `cd apps/api && ruff check .` - passed.
- `cd apps/api && ruff format .` - passed; 48 files unchanged.
- `curl -sS http://127.0.0.1:8000/health && curl -sS http://127.0.0.1:8000/health/db && curl -sS http://127.0.0.1:8000/health/llm` - passed with API ok, DB ok, LLM mock ok.
- `curl -I http://127.0.0.1:3000` - passed with HTTP 200.

Known limitations:
- The main controller still owns auth/account, relationship/debug side state, proactive trigger, data export, and clear-message orchestration.
- Browser-level visual verification is still not installed.

## World-class continuation - knowledge controller and continuity panels

Completed in this checkpoint:
- Extracted memory and journal form state plus add/edit/pin/delete/forget/clear/create handlers into `components/eidolon/use-knowledge-controller.ts`.
- Reduced the main controller hook from 690 lines to 571 lines while preserving auth, chat, persistence, memory, journal, and data-clear behavior.
- Upgraded the memory panel with stored/pinned/confidence stats, contradiction visibility, pinned-first ordering, recalled timestamps, and compact memory-quality metrics.
- Upgraded the journal panel with entry/open-thread/callback stats, emotional marker count, importance-first ordering, and unresolved-thread callouts.
- Kept the UI text-first, dependency-free, and free of prompt/debug internals.

Commands run:
- `cd apps/web && npm run lint` - passed.
- `cd apps/web && npm run build` - passed after Turbopack port-binding approval.
- `cd apps/api && alembic upgrade head` - passed.
- `cd apps/api && pytest` - passed; 29 tests.
- `cd apps/api && ruff check .` - passed.
- `cd apps/api && ruff format .` - passed; 48 files unchanged.
- `curl -sS http://127.0.0.1:8000/health && curl -sS http://127.0.0.1:8000/health/db && curl -sS http://127.0.0.1:8000/health/llm` - passed with API ok, DB ok, LLM mock ok.
- `curl -I http://127.0.0.1:3000` - passed with HTTP 200.

Known limitations:
- The main controller still owns auth, account, character, conversation, search, debug, relationship, and data export orchestration.
- Browser screenshot/visual regression tooling is still not installed.

## World-class continuation - chat/runtime controller split

Completed in this checkpoint:
- Extracted chat message state, SSE stream parsing, edit-message flow, reroll flow, and chat reset behavior into `components/eidolon/use-chat-controller.ts`.
- Extracted runtime API/DB/LLM health polling into `components/eidolon/use-runtime-status.ts`.
- Extracted the runtime status header UI into `components/eidolon/runtime-status-strip.tsx`.
- Extracted pure controller helpers into `components/eidolon/controller-utils.ts`.
- Reduced `eidolon-app.tsx` to 165 lines and the main controller hook to 690 lines, while preserving register/login/chat/SSE/persistence behavior.
- Restored generated `next-env.d.ts` churn after production builds switched it between dev/build route type references.

Commands run:
- `cd apps/api && pytest` - passed; 29 tests.
- `cd apps/api && ruff check .` - passed.
- `cd apps/web && npm run lint` - passed.
- `cd apps/web && npm run build` - passed after Turbopack port-binding approval.
- `curl -sS http://127.0.0.1:8000/health && curl -sS http://127.0.0.1:8000/health/db && curl -sS http://127.0.0.1:8000/health/llm` - passed with API ok, DB ok, LLM mock ok after restarting the dev server.
- `curl -I http://127.0.0.1:3000` - passed with HTTP 200 after restarting the web dev server.

Known limitations:
- The main controller still owns character, conversation, memory, journal, data, and account state. Further domain hook extraction is still warranted.
- Runtime smoke is HTTP-level; browser screenshot tooling is still not installed.

## World-class continuation - chat presence surface

Completed in this checkpoint:
- Upgraded the central chat surface with a compact context ribbon showing relationship mood/conflict, warmth/trust, memory/journal/message continuity, and effective content mode.
- Added clearer companion delivery metadata in message bubbles, including content mode, read state, typing latency, proactive markers, and away state when present.
- Improved chat header responsiveness, composer mobile layout, and streaming presentation while keeping the interface text-first and dependency-free.
- Kept debug and prompt metadata out of the chat surface; the new context ribbon uses only user-facing state.

Commands run:
- `cd apps/web && npm run lint` - passed.
- `cd apps/web && npm run build` - passed after Turbopack port-binding approval.
- `curl -sS http://127.0.0.1:8000/health && curl -sS http://127.0.0.1:8000/health/db && curl -sS http://127.0.0.1:8000/health/llm` - passed with API ok, DB ok, LLM mock ok.
- `curl -I http://127.0.0.1:3000` - passed with HTTP 200.

Known limitations:
- Visual validation remains HTTP/build-level rather than browser screenshot-based.
- The context ribbon is still compact; future passes can add richer timeline-aware affordances once more controller domains are split.

## Level 2 goal run - audit checkpoint

Started on 2026-06-17.

Files/docs read:
- `AGENTS.md`, `README.md`, all `docs/*.md`, env examples, backend app code, Alembic migration, tests, CI, and the current single-component web UI.

Findings:
- Register/login/chat/stream/persistence are already implemented with local auth, owner-scoped endpoints, mock default LLM, optional Ollama provider, safe generic errors, CORS normalization, and backend/frontend validation history.
- No forbidden runtime dependency was found in project manifests. The app remains text/state only.
- Memory v1 exists but needs Level 2 schema fields, edit/delete, dedupe/merge, contradiction metadata, forgetting/decay, richer retrieval scoring, and episodic journals.
- Relationship v1 is bounded and deterministic, but Level 2 needs mood/conflict/repair metadata, tags, decay, and a visible timeline.
- Proactive v1 can queue a cooldown-protected fallback message, but Level 2 needs scheduled-job helper coverage for inactivity, morning/goodnight, thinking-of-you, milestone, and unresolved-thread nudges.
- Adult gates are structural and SFW by default, but Level 2 needs clearer settings state and blocked-state explanations in API/UI.
- Debug APIs are authenticated and owner-scoped, but the frontend currently renders the full prompt in the debug panel; Level 2 should keep debug private, compact, and separate from chat.
- The frontend is a compact single-page MVP. Level 2 needs panels for conversations/search, memory edit/delete, journal, relationship timeline, adult settings, app settings, and data wipe controls without adding heavy UI dependencies.

Next checkpoint:
- Implement backend Level 2 state, services, APIs, migration, and tests while preserving existing auth/chat/persistence flows.

## Level 2 goal run - backend checkpoint

Completed in this checkpoint:
- Added Alembic migration `0002_level2_state` for Memory v2 fields, Relationship v2 fields, and `episodic_journals`.
- Upgraded `memory_items` support with `importance`, `pinned`, `contradiction_group`, dedupe/merge, contradiction metadata, recall scoring, decay/forgetting, edit/delete, and clear APIs.
- Added deterministic episodic journals with summaries, emotional tags, unresolved threads, callbacks, and adult-mode detail redaction for durable journal text.
- Added `reasoning_context_builder` to assemble active context, semantic memories, episodic journals, relationship state, adult gate status, and time/day context without exposing chain-of-thought.
- Upgraded prompt assembly to `persona_memory_relationship_episode_v2` with compact persona, relationship mood/repair, memories, journals, callbacks, safety gates, and private-context instructions.
- Upgraded relationship state with mood, conflict state, repair-needed flag, tags, deterministic decay, and timeline entries in metadata.
- Added proactive scheduled-job hooks for inactivity, morning, goodnight, thinking-of-you, milestone, and unresolved-thread nudges.
- Added adult gate status API, reroll endpoint, edit-message endpoint, clear/delete conversation endpoints, journal APIs, memory hygiene APIs, and export coverage for journals/new fields.
- Sanitized debug output from full raw prompt to bounded `prompt_preview` plus structured state.
- Added production env validation for placeholder JWT secret and invalid LLM providers.

Commands run:
- `docker compose up -d postgres` - passed after pulling `pgvector/pgvector:pg16`.
- `cd apps/api && python -m pip install -e ".[dev]"` - passed using user site packages because the existing `.venv` entrypoints were stale.
- `cd apps/api && alembic upgrade head && pytest -q` - passed; migration upgraded through `0002_level2_state`; 28 tests passed.
- `cd apps/api && ruff check . --fix` - fixed import ordering; remaining line-length issues were patched.
- `cd apps/api && ruff check . && pytest -q` - passed; 28 tests passed.

Known limitations:
- Embedding generation remains intentionally deferred; pgvector storage is available, retrieval is deterministic keyword/recency/importance scoring.
- APScheduler is still not started in tests; proactive Level 2 creates PostgreSQL scheduled jobs safely, but no live worker loop is enabled by default.
- Reroll creates an alternate assistant message with metadata rather than replacing history.

Next checkpoint:
- Expand the lightweight Next.js UI for Level 2 panels and controls without adding forbidden/heavy dependencies.

## Level 2 goal run - frontend checkpoint

Completed in this checkpoint:
- Reworked the single-page Next.js shell into a responsive Level 2 app layout with conversation rail, central streaming chat, and multi-panel state inspector/editor.
- Added UI coverage for conversations, chat search, reroll, edit-message, proactive check-in trigger, character editor, memory editor, journal view/create, relationship metrics/timeline, adult gate settings/status, app settings, debug preview, export, clear chat, clear memories, and delete conversation.
- Kept the frontend dependency set unchanged: Next.js, React, TypeScript, Tailwind only.
- Removed full raw prompt rendering from the UI; debug shows bounded `prompt_preview`, prompt version/provider, jobs, and scoped conversation state.
- Improved empty/error/notice states, timestamps, streaming display, mobile stacking, and relationship/adult blocked-state visibility.

Commands run:
- `cd apps/web && npm run lint` - passed.
- `cd apps/web && npm run build` - passed.

Known limitations:
- The UI remains a single App Router page rather than separate routes; this keeps the MVP light but makes the component large.
- Message editing updates the stored user message but does not automatically regenerate subsequent assistant messages.

Next checkpoint:
- Run full backend and frontend validation commands, apply formatting, and record final results.

## Level 2 goal run - final validation

Completed in this checkpoint:
- Updated docs for Level 2 data model, API contract, memory, relationship, proactive jobs, frontend UX, testing, and progress tracking.
- Confirmed no forbidden runtime dependency additions. No package manifests added Redis, Celery, Supabase, Firebase, LangChain, Pinecone, Chroma, Clerk, Auth0, NextAuth, Stripe, Socket.io, Three.js, Framer Motion, WebRTC, native mobile, Kubernetes, multimedia, paid APIs, or external vector DB.
- Preserved register/login/chat/SSE/persistence flows while adding Level 2 memory, journals, relationship timeline, adult-gate status, proactive hooks, privacy controls, and UI panels.

Commands run:
- `docker compose up -d postgres` - passed; `eidolon-postgres` running.
- `cd apps/api && python -m pip install -e ".[dev]"` - passed using user site packages because the checked-in `.venv` entrypoints were stale in this environment.
- `cd apps/api && alembic upgrade head && pytest && ruff check . && ruff format .` - passed; 28 tests passed; Ruff passed; 2 files formatted.
- `cd apps/api && pytest -q && ruff check .` - passed after formatting; 28 tests passed.
- `cd apps/web && npm install` - passed; 0 vulnerabilities.
- `cd apps/web && npm run lint && npm run build` - passed.
- `git diff --check` - passed.
- Forbidden-dependency text scan - no runtime/package-manifest forbidden additions found; hits were docs or ordinary export-related symbols.
- `cd apps/api && python -m uvicorn app.main:app --host 0.0.0.0 --port 8000` - started locally.
- `curl -sS http://localhost:8000/health` - passed with `{"status":"ok","service":"eidolon-api"}`.
- `cd apps/web && npm run dev -- --port 3000` - started locally.
- `curl -I -sS http://localhost:3000` - passed with HTTP 200.

Known limitations:
- Embeddings are still storage-ready but not generated; retrieval is deterministic keyword/recency/importance scoring.
- The scheduler worker loop remains disabled by default; proactive Level 2 creates PostgreSQL-backed jobs safely but does not run APScheduler in tests.
- The Level 2 web UI is still a single lightweight component/page. It is buildable and responsive, but a future pass could split panels into smaller components.
- `apps/web/next-env.d.ts` was updated by the production Next build from dev route types to build route types.

## World-class overhaul goal - product architecture pass

Started on 2026-06-17 after the broader end-product vision replaced the narrower Level 2 target.

Completed in this checkpoint:
- Treated the validated Level 2 app as the baseline rather than the finish line.
- Split the previous 1,804-line `eidolon-app.tsx` into focused frontend modules:
  - `components/eidolon/types.ts`
  - `components/eidolon/ui.tsx`
  - `components/eidolon/auth-screen.tsx`
  - `components/eidolon/workspace-rail.tsx`
  - `components/eidolon/chat-surface.tsx`
  - `components/eidolon/inspector.tsx`
- Reworked the app shell into a more deliberate workspace: character rail, thread rail, search, central chat surface, and inspector.
- Added frontend support for creating/selecting characters, creating/selecting threads per character, editing thread titles, and keeping inspector state in sync.
- Added backend `PATCH /conversations/{conversation_id}` and `ConversationUpdate` schema for conversation title edits.
- Added a backend test for conversation title updates.
- Improved global UI polish: font rendering, dark form controls, selection color, focus consistency, scrollbar color, and reduced-motion behavior.
- Fixed stale TypeScript config by removing invalid `ignoreDeprecations: "6.0"` from `apps/web/tsconfig.json`.

Commands run:
- `cd apps/web && npm run lint && npm run build` - initially failed on invalid TypeScript `ignoreDeprecations` value; fixed config.
- `cd apps/web && npm run lint && npm run build` - passed after config fix.
- `cd apps/api && pytest -q && ruff check .` - passed; 29 tests.
- `cd apps/web && npm run lint && npm run build` - passed after thread rename UI wiring.
- `cd apps/api && python -m uvicorn app.main:app --host 0.0.0.0 --port 8000` - restarted from current code for smoke testing.
- `curl -sS http://localhost:8000/health` - passed.
- `cd apps/web && npm run dev -- --port 3000` - restarted from current code for smoke testing.
- `curl -I -sS http://localhost:3000` - passed with HTTP 200.
- Authenticated API smoke test for conversation rename - passed.

Known limitations:
- The inspector module is still large and should be split further in a future product-quality pass.
- Visual verification is currently through build/runtime HTTP checks; no browser screenshot tooling is installed in this repo yet.

## Level 2 continuation - controller extraction and runtime status

Completed in this checkpoint:
- Extracted the frontend orchestration state/actions from `components/eidolon-app.tsx` into `components/eidolon/use-eidolon-controller.ts`.
- Kept `eidolon-app.tsx` as a small renderer that composes auth, workspace rail, chat surface, and inspector.
- Added typed runtime health state for API, DB, and LLM provider.
- Added a compact private runtime status strip to the authenticated header using only public health endpoints.
- Preserved debug prompt metadata inside the debug panel only; chat messages do not render debug context.
- Fixed the invalid `ignoreDeprecations` value in the web TypeScript config during the frontend build cleanup.
- Kept dependencies unchanged and within the zero-cost/text-only constraints.

Commands run:
- `docker compose up -d postgres` - passed after Docker daemon approval; `eidolon-postgres` was already running and healthy.
- `cd apps/api && pip install -e ".[dev]"` - passed after network approval for build dependencies.
- `cd apps/api && alembic upgrade head && pytest && ruff check . && ruff format .` - passed after localhost/Postgres approval; 29 backend tests passed, Ruff passed, 48 files unchanged by format.
- `cd apps/web && npm install` - passed; dependencies already up to date.
- `cd apps/web && npm run lint` - passed.
- `cd apps/web && npm run build` - passed after Turbopack port-binding approval.
- Forbidden-dependency scan across manifests, Docker Compose, GitHub workflows, and docs - no matches.
- `cd apps/api && python -m uvicorn app.main:app --host 0.0.0.0 --port 8000` - started current backend for smoke testing.
- `curl -sS http://127.0.0.1:8000/health && curl -sS http://127.0.0.1:8000/health/db && curl -sS http://127.0.0.1:8000/health/llm` - passed with API ok, DB ok, LLM mock ok.
- `cd apps/web && npm run dev` - started current frontend on port 3000.
- `curl -I http://127.0.0.1:3000` - passed with HTTP 200.

Known limitations:
- The controller hook is still large and should be split into domain hooks in a future pass.
- Browser visual regression tooling is still not installed; UI validation is lint/build plus HTTP smoke.
- The broader Level 2 goal remains active because the end-to-end product objective is ambitious and should not be marked complete from one checkpoint alone.

## World-class overhaul goal - inspector split and chat ergonomics

Completed in this checkpoint:
- Split the remaining large `components/eidolon/inspector.tsx` into focused panel modules under `components/eidolon/panels/`.
- Reduced `inspector.tsx` from 754 lines to a 227-line panel coordinator.
- Added standalone panel modules for overview, character, memory, journal, relationship, adult settings, account settings, debug, and data controls.
- Added chat auto-scroll to the newest message/streaming output.
- Added Enter-to-send and Shift+Enter-for-newline behavior in the composer without adding visible shortcut clutter.
- Kept frontend dependencies unchanged.

Commands run:
- `cd apps/web && npm run lint` - passed after panel split.
- `cd apps/web && npm run lint && npm run build` - passed after chat ergonomics update.
- `cd apps/api && pytest -q && ruff check .` - passed; 29 tests.
- `git diff --check` - passed.
- `cd apps/api && python -m uvicorn app.main:app --host 0.0.0.0 --port 8000` - started current backend for smoke testing.
- `cd apps/web && npm run dev -- --port 3000` - started current frontend for smoke testing.
- `curl -sS http://localhost:8000/health` - passed.
- `curl -I -sS http://localhost:3000` - passed with HTTP 200.
- Authenticated runtime smoke for register, character creation, conversation creation/rename, SSE chat, memory list, and debug prompt preview - passed.

Known limitations:
- Browser screenshot/visual regression tooling is still not installed; runtime validation is HTTP/API-level plus build/type/lint checks.
- The central app controller remains around 950 lines and could be split into hooks/state modules in a deeper architecture pass.

## Debug update - frontend registration `Failed to fetch`

Root cause inspected on 2026-06-17:
- Frontend register calls `POST /auth/register` with `{ email, password, display_name }`, which matches the backend `RegisterRequest` schema.
- Backend `POST /auth/register` works and returns a bearer token; cookies/credentials mode is not required.
- The likely Codespaces failure was browser reachability/CORS configuration: the frontend defaulted to `http://localhost:8000`, which a browser outside the Codespace may not reach, and backend CORS only allows configured `WEB_ORIGIN`/`CORS_ORIGINS`.
- Frontend network errors previously surfaced as raw browser `Failed to fetch`, hiding the API base URL and Codespaces/CORS guidance.

Fixes:
- Frontend API client now keeps `NEXT_PUBLIC_API_BASE_URL` as the explicit override, infers the matching `-8000.app.github.dev` API URL from a Codespaces `-3000.app.github.dev` frontend URL when no override is set, and shows actionable network/CORS errors.
- Streaming chat now uses the same API client error handling as JSON requests.
- Backend CORS origin parsing now trims whitespace and trailing slashes for `WEB_ORIGIN` and `CORS_ORIGINS`.
- `.env.example`, `apps/web/.env.example`, and `README.md` document Codespaces URL variables without hardcoding a specific Codespace URL.

## Debug update - mock LLM response behaviour

Root cause inspected on 2026-06-17:
- `Settings.llm_provider` defaults to `mock`, and `get_llm_provider()` routes to Ollama only when `LLM_PROVIDER=ollama`.
- The chat flow already passed the assembled prompt into the provider, including character, speech style, memories, recent messages, and relationship state.
- `MockLLMProvider` ignored almost all of that prompt and returned the shallow echo response `I'm here with you. I heard: ...`.

Fixes:
- `MockLLMProvider` now parses the assembled prompt for character name, speech style, first relevant memory, recent-message presence, and relationship summary.
- Mock responses are deterministic, short, SFW, explicitly marked with `[mock:<character>]`, and no longer echo the current user message.
- Mock streaming now emits natural phrase-like chunks that join back to the exact generated response.
- Ollama provider remains available for `LLM_PROVIDER=ollama`; HTTP failures or invalid responses now raise a controlled provider-unavailable error that the chat API returns cleanly.
- Debug prompt context now includes `llm_provider`, and persisted assistant message metadata already stores `provider: mock`.
- README now documents switching between mock and Ollama mode.

## Checkpoints

| # | Checkpoint | Status | Notes |
|---|---|---|---|
| 1 | Repo scaffolding sanity check | complete | Existing `.env.example`, `.gitignore`, `docker-compose.yml`, `Makefile`, CI placeholder, deployment templates, and database init script inspected. PostgreSQL pgvector container starts locally. |
| 2 | Backend health endpoint | complete | FastAPI app created with exact `GET /health` response and `/health/db`, `/health/llm`. |
| 3 | Database foundation | complete | Async SQLAlchemy 2, settings, Alembic, UUID models/migration for users, refresh tokens, characters, conversations, messages, memory items, relationship states, scheduled jobs. |
| 4 | Mock chat endpoint | complete | Mock LLM provider, `POST /chat/messages`, persisted user/assistant messages, `GET /conversations/{id}/messages`. |
| 5 | Frontend chat shell | complete | Next.js App Router, TypeScript, Tailwind, auth-first screen, dark mobile-friendly chat UI. |
| 6 | SSE streaming | complete | `POST /chat/stream` emits `message_start`, `token`, `message_done`; frontend progressively renders chunks and persists final assistant once. |
| 7 | Ollama provider | complete | `LLM_PROVIDER=mock\|ollama`; Ollama HTTP adapter tested with mocked HTTP only. |
| 8 | Persona prompt assembly | complete | Central prompt service includes safety boundaries, character profile, recent messages, memories, relationship, content mode. |
| 9 | Memory v1 | complete | `memory_items` table, manual memory API, conservative extraction, cheap text retrieval, prompt injection. pgvector extension and nullable vector column are present; embeddings are deferred. |
| 10 | Relationship state v1 | complete | Bounded deterministic trust/intimacy/warmth/tension/familiarity/attachment service and prompt injection. |
| 11 | Background jobs | complete | `scheduled_jobs` table and service for create/claim/done/failed with PostgreSQL `SKIP LOCKED`. Scheduler loop remains disabled/not started in tests. |
| 12 | Proactive messages | complete | Inactivity/proactive message service with SFW fallback and cooldown duplicate prevention; debug trigger exists. |
| 13 | Auth v1 | complete | Local register/login/me/logout, Argon2 password hashing, JWT bearer auth, protected user data endpoints. |
| 14 | Adult mode gates | complete | User age gate, explicit character age, `adult_mode_allowed`, requested content mode, structural SFW fallback; tests avoid explicit adult samples. |
| 15 | Debug/admin panel | complete | Private debug APIs plus frontend panel for prompt context, relationship, jobs, conversations, memories. |
| 16 | Export/backup | complete | Protected JSON export excludes password/token hashes/secrets/other users. `scripts/backup-db.example.sh` added for `pg_dump` backups. |
| 17 | Deployment templates | complete | Caddy/systemd templates existed; SSH deploy script corrected; GitHub Actions deploy skeleton added using secrets only. |
| 18 | Production hardening | complete | Env CORS, safe generic 500 handler, `/health/db`, `/health/llm`, strict `make verify`, clean frontend production audit. |
| 19 | MVP polish | complete | Mobile dark chat, timestamps, loading/streaming states, readable errors, memory/relationship/debug/export controls. |

## Commands run

- `docker compose up -d postgres` - passed.
- `cd apps/api && pip install -e ".[dev]"` - initial packaging config failed because setuptools discovered both `app` and `alembic`; fixed package discovery to `app*`, rerun passed.
- `cd apps/api && alembic upgrade head` - passed.
- `cd apps/api && pytest` - initial helper import issue and asyncpg pooled event-loop issue found; fixed test helper module and test `NullPool`, rerun passed: 15 tests.
- `cd apps/api && ruff check .` - initial style/line-length issues found; fixed, rerun passed.
- `cd apps/api && ruff format .` - passed.
- `cd apps/api && pytest && ruff check .` - passed after formatting.
- `cd apps/web && npm install` - passed. Initial Next 14 install produced production audit findings; upgraded to Next 16/React 19 and added a PostCSS override. Final install reports 0 vulnerabilities.
- `cd apps/web && npm run lint` - initial ESLint config needed Next 16 flat config and React effect cleanup; fixed, rerun passed.
- `cd apps/web && npm run build` - passed.
- `docker compose up -d postgres` - final run passed; container already running.
- `cd apps/api && pip install -e ".[dev]" && alembic upgrade head && pytest && ruff check . && ruff format .` - final run passed; 15 backend tests.
- `cd apps/web && npm install && npm run lint && npm run build` - final run passed; npm audit during install found 0 vulnerabilities.
- `make verify` - passed.
- `cd apps/api && uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload` - started locally.
- `curl -sS http://localhost:8000/health` - passed with `{"status":"ok","service":"eidolon-api"}`.
- `cd apps/web && npm run dev` - started locally on port 3000.
- `curl -I -sS http://localhost:3000` - passed with HTTP 200.
- `cd apps/api && pytest tests/test_auth_chat.py tests/test_health.py && ruff check .` - passed after removing raw exception text from stream error events.
- `cd apps/api && pytest && ruff check . && ruff format .` - final hardening rerun passed; 15 backend tests.
- `cd apps/web && npm run lint && npm run build` - final hardening rerun passed.
- `cd apps/api && pytest && ruff check . && ruff format .` - rerun passed after making test cleanup clear the local database after each test too.
- `cd apps/api && source .venv/bin/activate && pytest && ruff check . && ruff format .` - passed after registration/Codespaces fix; 16 backend tests.
- `cd apps/web && npm install && npm run lint && npm run build` - passed after registration/Codespaces fix.
- `curl -sS http://localhost:8000/health` - passed.
- `curl -i -sS -X OPTIONS http://localhost:8000/auth/register -H 'Origin: http://localhost:3000' -H 'Access-Control-Request-Method: POST' -H 'Access-Control-Request-Headers: content-type'` - passed with `access-control-allow-origin: http://localhost:3000`.
- `curl -i -sS http://localhost:8000/auth/register -H 'Content-Type: application/json' -H 'Origin: http://localhost:3000' --data '{"email":"debug-register@example.com","password":"good-password","display_name":"Debug"}'` - passed with HTTP 201.
- `cd apps/api && source .venv/bin/activate && pytest && ruff check .` - final rerun passed and cleared the throwaway curl-created user from the test database.
- `git diff --check` - passed.
- `cd apps/api && source .venv/bin/activate && pytest && ruff check . && ruff format .` - initial LLM-provider rerun found a mock streaming trailing-space assertion and Ruff import ordering; both fixed.
- `cd apps/api && source .venv/bin/activate && ruff check . --fix && ruff format . && pytest && ruff check .` - passed after formatting provider tests.
- `cd apps/api && source .venv/bin/activate && pytest && ruff check . && ruff format .` - final LLM-provider validation passed; 22 backend tests.

## Known limitations

- `rg` is not installed in this Codespace, so file discovery is using `find`.
- APScheduler itself is not wired to a running loop yet; the PostgreSQL-backed job foundation is implemented and scheduler remains disabled in tests.
- Memory embeddings are not generated yet. The database has pgvector support and a nullable vector column, while MVP retrieval uses lightweight text matching.
- The frontend is a compact single-page MVP rather than a multi-route settings/debug area.
