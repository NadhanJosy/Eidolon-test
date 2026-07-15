# Testing and Acceptance

## Testing philosophy

Tests should verify product-critical behaviour without requiring expensive or unavailable infrastructure.

## Backend tests

Use pytest.

The test fixture applies Alembic migrations to the test database at session
startup. It must not create tables directly from SQLAlchemy metadata, because
that would hide broken migrations.

Test categories:

- health endpoints
- database models
- migration revision/schema checks
- chat endpoints
- streaming endpoint
- stream event order plus bounded deterministic mock cadence across measured,
  brisk, conflicting, missing-style, short-response, long-response, and
  punctuation cases
- provider selection
- natural mock cue, continuity, repair, empty-context, and hidden-state
  non-disclosure behavior at provider and persisted API boundaries
- prompt assembly
- modular companion orchestration: perception, typed soul compilation,
  qualitative emotion, strategy/question/length/rhythm planning, private-plan
  non-disclosure, and completed-response checks
- multi-turn first meeting, banter, support, celebration, advice, conflict,
  apology, recurring interest, contradiction, natural callback, long absence,
  boundary, initiative, and gradual progression scenarios
- response evaluation scores for consistency, memory precision, emotional fit,
  naturalness, repetition, initiative, and safety
- memory creation/retrieval, deterministic normalized feature embeddings,
  hybrid related-phrase ranking, edit recomputation, legacy-null backfill, and
  raw-vector API non-disclosure
- relationship updates
- auth access control
- HttpOnly refresh-cookie issuance, rotation, logout/account-deletion clearing,
  legacy body-token migration, untrusted-Origin rejection, and access responses
  without refresh tokens in JSON
- masked JWT secret configuration with UTF-8 byte bounds and production weak-key
  rejection; HS256 access-token claim requirements for issuer, audience, type,
  issued/not-before/expiry times, subject UUID, and token UUID; wrong-key,
  wrong-algorithm, missing, expired, premature, and mismatched token rejection
- canonical email and display-name normalization, malformed mailbox rejection,
  canonical duplicate detection, bounded new-passphrase validation, dummy Argon2
  work for unknown accounts, and safe malformed-password-hash failure
- PostgreSQL login throttling across canonical identity and changing-email client
  attempts, generic threshold/block responses with `Retry-After`, successful
  reset, elapsed-window recovery, HMAC-only persistence, bounded configuration,
  and concurrent request serialization
- pre-Argon registration client throttling, committed accounting across
  duplicate conflicts, no quota use for schema/Origin rejection, independent
  login/registration scopes, elapsed-window recovery, HMAC-only persistence,
  bounded configuration, and concurrent request serialization
- adult mode gates
- adult profile hard-block validation for direct create/update bypass attempts,
  with protective boundary language allowed
- canonical adult-dependent persistence across create and merged partial update:
  disable-only intensity/storage clearing, private-by-default storage clearing,
  eligible-setting retention, strict known memory-control types, and atomic
  rejection of an ineligible age transition
- export access control
- memory v3 edit/delete/dedupe/contradiction plus owner-scoped, idempotent
  forget/restore state; pinned automatic-forget protection; active retrieval,
  prompt, debug, and conflict exclusion; re-learning revival; export continuity
- episodic journal creation, generated/manual source ownership, manual-note
  survival across later conversation refresh, nonblank update validation,
  generated-row mutation rejection, and owner-scoped edit/delete
- intentional open-thread detection so answered questions do not create
  unresolved-thread nudges
- relationship v2 timeline metadata
- source-linked relationship effects and latest-turn edit recalculation
- proactive scheduled-job hooks
- proactive local-provider generation with deterministic SFW fallback for
  unavailable, malformed, oversized, blocked, or hidden-context output
- qualitative proactive relationship posture, score non-disclosure,
  repair-sensitive authored fallback, and queue/delivery suppression for
  pressure-prone notes
- scheduler lifespan ownership, retry backoff/cap, and lock release
- IANA timezone validation, DST-safe local note scheduling, quiet-hour
  deferral, proactive cooldown validation, and pending-job rescheduling after
  preference changes
- conversation clear/reroll controls, including target-only message, journal,
  and queued-job removal with sibling-thread and durable-memory preservation,
  plus delayed assistant-completion cancellation after a successful wipe
- owner-scoped conversation deletion, queued-job cleanup, and conversation-local
  message/journal removal
- latest-user-turn editing with regenerated companion replies, stale assistant
  removal, source-linked memory refresh, conversation-local journal refresh,
  queued-job replacement, older-turn rejection, and cross-account `404`
- latest-user-turn deletion with dependent companion-reply removal, relationship
  effect reversal, user-and-reply source-linked memory cleanup, safe
  remaining-journal rebuild, guarded proactive-job rebuild, empty-thread
  no-requeue behavior, and older-turn rejection
- companion-reply deletion with source-linked memory cleanup, remaining-journal
  reconstruction, stale-job replacement for safe assistant-ending threads, and
  no proactive requeue for user-ending threads
- monotonic, account-scoped conversation read receipts and unread counts
- idempotent privacy-transition events and canonical prompt labeling
- one-turn privacy across SSE, reroll, recall timestamps, later prompt/journal
  filtering, batch extraction, and proactive-job suppression
- complete authored character creation and relationship initialization
- whitespace-only character names plus pathological profile size/depth rejection
- foreground generation diagnostics across message, stream, reroll, and edit;
  post-rollback durability, fixed client error text, provider-label
  sanitization, bounded retention, unchanged-history rollback, and cross-account
  Debug isolation
- conversation-owned Shared Scene normalization, safety rejection, concurrent
  idempotency, generic event non-disclosure, sibling-thread and cross-account
  isolation, prompt/mock influence, Debug prose exclusion, and reset semantics

## Frontend checks

Use:

- npm run lint
- npm run build

Frontend acceptance also includes source review for responsive display
invariants, humanized primary-shell copy, and operational-state confinement to
the debug panel. Navigation actions must compile with explicit success results
and stale-selection guards. Auth state must keep access tokens in memory, remove
legacy localStorage tokens, fetch with credentials included, show a non-jarring
session-opening state, and avoid fixture email/name defaults on the sign-in
screen.

Companion-state contract acceptance must exercise both canonical and malformed
responses for active memories, relationship, journals, adult readiness, jobs,
character Debug, conversation Debug, and runtime health. Canonical payloads must
hydrate the expected companion and thread. Mixed provenance, duplicate IDs,
invalid UUIDs/timestamps, non-finite or out-of-range metrics, oversized/deep JSON,
contradictory adult status, malformed Debug manifests, and a non-string provider
must not enter visible state. Adult readiness must fail closed, malformed health
must render degraded, optional Debug failure must not block the workspace, and
no delayed request may apply after companion navigation, logout, or caller
invalidation. A companion switch must not show the previous companion's memory,
journal, relationship, adult, or Debug state while the new refresh is pending.

When a temporary headless browser is available, rendered acceptance should cover
320px and 390px phone viewports plus a 1440px desktop viewport. Auth, empty chat,
populated chat, Threads, Companion, and the character builder must have no
document-level horizontal overflow. The browser pass should exercise one real
mock-stream exchange, reject provider/prompt markers in visible chat, distinguish
the expected anonymous refresh `401` from unexpected console errors, fail on
page errors or request failures, and erase its temporary account afterward.

Debug acceptance must prove that current retrieval is labeled separately from
the last real generation, no synthetic prompt is assembled, raw prompt/message
text is absent, private context metadata is stripped from every normal message
surface, and validated manifests update across chat, SSE, reroll, and edited
turns while remaining owner-scoped and bounded under malformed legacy data.
Recent errors must remain character-scoped, use only approved safe fields, and
clear with failed or stale character refreshes rather than showing old context.
The character Debug endpoint must return an owner-scoped relationship snapshot
and at most 10 bounded active-memory snapshots without embeddings. The Debug UI
must keep memory prose collapsed by default, tolerate absent or malformed
snapshot fields, and confine long content to internal scrolling. Browser checks
at 390px and 1440px must prove that these details are inspectable in Debug,
create no horizontal overflow, and do not appear in the primary conversation.

The auth entry must retain its brand-first, unframed responsive layout, semantic
labels, polite live status, and reduced-motion behavior. Busy state must disable
mode and submit actions, password visibility must use a labeled checkbox, and
password/session-scoped UI state must reset on mode change, successful auth,
logout, and session expiry as appropriate.
Registration must expose the API's 12-character new-passphrase minimum through
native form validation and an associated text description without weakening the
server-side rule.

Auth concurrency acceptance must submit the same valid form twice in one turn
and observe one login or registration POST. A failed request must restore native
controls and retain the email and password; a successful auth or logout must
remove the password. Complete auth and `/auth/me` responses must match canonical
email, immutable user identity, bearer token shape, UUID, boolean, normalized
display-name, and offset-timestamp contracts before entering state. Its decoded
claims must identify that same user and the expected HS256 issuer, audience,
access type, token UUID, and ordered issue/not-before/expiry times.

Malformed or non-JSON successful login/registration must use exactly one
cookie-refresh recovery and bootstrap only from its complete expected-user
response. Empty-account bootstrap must validate owned companion/thread lists;
an unreadable successful initial-room POST may use exactly one canonical list
read and accept only one unambiguous new normal empty room. Signing in and
Opening room states must not reveal an incomplete authenticated shell.

A controlled refresh/logout race must hold an accepted refresh response, log out
locally, then release it. The old completion must not restore user/token state,
publish stale feedback, or clear a newer action. Server logout must occur after
the held cookie rotation, and a full reload must remain signed out. A newer auth
attempt started while revocation is pending must wait for that serialization.

Adult-mode source acceptance must prove that readiness has active-character
provenance, stale/missing/failed readiness derives SFW, character changes reset
requested mode, same-character thread changes do not, blocked attempts route to
Adult settings with readable feedback, and controls cannot change during a send.
Adult-settings browser acceptance must also cover strict rejection of malformed
age text, immediate intensity/storage reset after eligibility closes, storage
reset when private-by-default opens, dependent-control disabled states, one-way
eligibility disable while the account gate is closed, canonical persistence
after save/reload, and no responsive overflow or unexpected browser errors.

PWA-style shell acceptance includes a parseable standalone manifest, served SVG
mark, disallow-all robots route plus no-index metadata, viewport-fit and safe-area
rules, interactive keyboard resizing, and live no-referrer, anti-framing,
no-sniff, same-origin isolation, and unused-capability response headers. No
service worker may cache authenticated application or API state.

The staged character builder must compile with field and cross-field validation,
age-gated adult controls, retained failure state, persisted-result duplicate
protection, and keyboard-contained modal behavior.
Cross-surface character-draft acceptance must prove that Builder, Persona, Adult
settings, and payload construction apply the same adult-dependent invariants.
In particular, private-by-default clears and disables adult-memory storage,
malformed or ineligible age clears eligibility and intensity, switching panels
does not resurrect cleared values, and the created/updated API response remains
canonical after reload.

Conversation-search acceptance must cover trimmed, bounded, case-insensitive
literal matching, including `%`, `_`, and `\\` without wildcard expansion. The
frontend must distinguish idle, loading, empty, result, and error states; prevent
same-tick duplicate requests; retain a recoverable query after failure; and
discard delayed success or failure after query or thread ownership changes.
Result activation must switch the mobile workspace and focus the exact rendered
ordinary, proactive, or system message. Browser diagnostics may contain only
the explicitly controlled search failure and anonymous refresh response.
Malformed search rows must be rejected by the complete Message-list contract,
including wrong-room IDs, duplicate IDs, unordered timestamps, invalid roles,
and oversized or malformed metadata, without rendering injected content.

Background-presence acceptance must hold a complete conversation-list response,
persist a newer foreground title/privacy/scene mutation, and then release the
older response; no foreground field may roll back. A malformed owner-scoped list
or a list missing/mismatching the active room and companion must not alter the
rail or active room. Read receipts must be complete, owner/room/companion exact,
and field-wise monotonic; malformed or unavailable receipts must leave canonical
history visible. Token rotation may complete in the same account, while thread
switch, logout, and replacement-account guards must discard delayed work.

Character-mutation concurrency acceptance must cover creation and profile save
under one synchronous session-owned lock. Same-tick create or save activation
must issue one write; Chat, content mode, Create, account/privacy, and Inspector
mutation controls must become natively disabled while ordinary room navigation
remains usable. Persona and Adult inputs must expose native API-aligned bounds.
A controlled failed write must retain its authored draft, restore controls, and
allow a later successful operation.

Every successful entity must be rejected unless its complete shape, immutable
owner, expected target, UUIDs, timestamps, bounded profile tree, adult invariants,
and submitted canonical payload are valid. Malformed or non-JSON successful
creation must perform exactly one canonical list GET and identify one new exact
profile before closing the builder; malformed successful save must perform one
canonical target GET and verify the exact persisted draft. Failed canonical
verification must distinguish accepted persistence from request failure and keep
authored input. A delayed save overtaken by character or room navigation may
update only its same-session character summary; it cannot replace the active
draft, feedback, or start obsolete side/history refreshes.

Logout followed by a newer login must invalidate delayed old-session create and
save ownership synchronously. A newer account must be able to start its own
companion operation before the old response settles, and the old response and
`finally` path must not insert an old profile, publish feedback, navigate, or
unlock the newer operation. Post-save side refresh must remain room-version
guarded and expose a distinct saved-but-refresh-unavailable error instead of
claiming that persistence failed. Browser diagnostics may contain only the
explicitly controlled failures and anonymous refresh responses.

Thread-creation concurrency acceptance must cover New and Private under one
synchronous session-owned lock. Same-turn repeated activation must issue one
POST; both creation commands, Chat, content mode, companion creation, account/
privacy, and Inspector mutations must be natively disabled while existing
thread and companion navigation remains usable. A controlled failed POST must
leave the active room and thread list unchanged and restore commands.

A successful response must be rejected unless it has the complete current owner,
expected companion/privacy/default-scene state, unique UUID, empty unread/message
state, bounded metadata/title, and valid ordered timestamps. Malformed or
non-JSON `2xx` must perform exactly one canonical list GET and identify one new
unambiguous match before navigation. A delayed same-session create overtaken by
navigation may add only its summary; it cannot replace the selected room or
publish stale feedback. Logout/relogin must let a newer account begin creation
before the old response settles, and the old response and `finally` must not
insert, navigate, notify, or unlock newer work. Browser diagnostics may contain
only the controlled create failure and anonymous refresh responses.

Thread-metadata concurrency acceptance must cover title, privacy, and Shared
Scene under one synchronous session-owned lock. Same-turn repeated activation
must issue one PATCH; these writes and companion/room create, provision, and
delete actions must be mutually exclusive before disabled state renders. A
failed write must restore controls and retain authored title or scene text.

Every accepted metadata response must be a complete owned Conversation for the
exact target and match the canonical title, privacy mode, or Shared Scene. A
malformed/non-JSON success must perform exactly one owner-scoped collection GET
and find that exact target with matching persistence. Navigation overtaking may
update only the verified same-session rail summary; active drafts, side refresh,
and feedback stay with the original active room. Logout/relogin must invalidate
older response and `finally` branches without affecting a newer account action.

Companion-selection room provisioning must cover a profile with no existing
thread, including provisioning nested beneath a newly persisted companion.
Same-turn repeated target selection must issue one POST. Only the target row may
be disabled with an Opening room state; other existing room and companion
navigation remains usable while conflicting mutations are natively disabled.

The response must satisfy the same complete owner, companion, normal privacy,
default scene, empty state, UUID, metadata, title, and timestamp contract as
explicit creation. Malformed or non-JSON `2xx` performs exactly one recovery
list GET after the initial discovery GET and accepts one unambiguous new room.
Failure restores the last fully loaded pair. A delayed accepted provision
overtaken by navigation may merge only its summary and cannot replace selection
or publish feedback. Logout/relogin must allow a newer account to provision
before the older response settles; the old response and `finally` cannot insert,
navigate, report, or clear the newer provision lock.

Thread-title concurrency acceptance must cover a controlled failed PATCH with
draft retention and recovery, native title-control disabling, same-tick duplicate
suppression, and a delayed successful response overtaken by thread navigation.
The older response may update its thread-list title but must not replace the
newer active conversation or editor draft.

Thread-privacy concurrency acceptance must prove backend-confirmed failure
behavior, same-tick duplicate suppression, native in-flight disabling, and a
delayed success overtaken by thread navigation. The stale response may update
the old thread's private marker but must not change the newer active mode, append
its event to the newer history, or start old-thread side/history refreshes. A
current successful transition must render its backend-owned privacy event
without requiring a reload, and a post-save refresh failure must not be reported
as failed persistence.

Shared Scene concurrency acceptance must cover retained drafts after a failed
PATCH, same-tick Set/Reset duplicate suppression, native control disabling, and
a delayed success overtaken by thread navigation. The stale response may update
only its room summary and must start no old-thread history or side refresh. A
current transition must perform one history reload, render its generic backend
event immediately, and retain the persisted scene or reset state when that
reload fails, with a distinct refresh error and recovery after reload.

Latest-turn edit concurrency acceptance must prove retained edit ID/text after a
failed PATCH, native Save/Cancel disabling, same-tick duplicate suppression, and
a delayed persisted response overtaken by thread navigation. Navigation must
clear old composer ownership, and the stale response must not insert its turn,
show old notices/errors, or launch old-thread side/history refreshes. A current
direct response must match the exact submitted text and replace the stale reply.
A malformed/non-JSON accepted edit must perform exactly one validated canonical
history read, verify the exact edited turn and following assistant reply, and
then perform the ordinary guarded side/history refresh. A persisted edit followed
by ordinary refresh failure must keep the canonical local turn, report refresh
failure separately, and recover from PostgreSQL after reload.

Reroll and message-delete concurrency acceptance must cover a controlled failed
request, native in-flight disabling, and same-tick duplicate suppression before
React commits its busy render. A delayed accepted operation overtaken by thread
navigation must remain durable in its original room while causing no stale
message insertion/removal, feedback, old-room side/history refresh, or lock in
the newer room. Current reroll responses must have matching conversation and
`reroll_of` provenance; delete responses must report a positive integer count.
Malformed/non-JSON accepted results must perform exactly one complete canonical
history read and prove one unambiguous new reroll or target absence. Each verified
success then performs the ordinary guarded side/history refresh. If that refresh
fails after persistence, the safe local reroll or removal remains visible, the
error distinguishes saved state from unavailable refresh, and reload recovers
the same PostgreSQL result. Logout/account replacement must invalidate stream,
edit, reroll, and delete ownership together so old completions and `finally`
paths cannot mutate or unlock the new session.

Frontend transcript contract acceptance must reject wrong-conversation rows,
unknown roles, empty or oversized content, invalid UUIDs or offset timestamps,
duplicate message IDs, decreasing history timestamps, reserved/internal metadata
keys, invalid content/privacy modes, and metadata over the depth, fan-out, string,
key, or byte bounds. SSE acceptance must enforce one exact new user boundary,
ignore tokens before it, reject malformed or oversized fragments, require one
new complete assistant boundary after it, stop local application after malformed
JSON/error/completion, and report premature EOF. A malformed start must preserve
the submitted draft and one-turn privacy choice.

Manual-check-in and clear-chat concurrency acceptance must prove same-tick
duplicate suppression, synchronous account/session ownership, and native
current-room control disabling. A controlled check-in failure must create no
local event; readable JSON `null` must show the intentional paused/cooling-down
state. Direct notes must pass the complete Message contract, room/assistant/
proactive provenance, new-ID check, and 600-character bound. A malformed or
non-JSON accepted result must perform exactly one complete canonical history GET
and find exactly one unambiguous new proactive note. A verified note followed by
ordinary side/history refresh failure must stay visible and recover after reload.
A delayed saved note overtaken by navigation must remain only in its original
room and start no old-room refresh. Logout or account replacement must prevent
every old completion and `finally` path from changing or unlocking the new
session.

Clear-chat failure must preserve the transcript and typed `CLEAR CHAT` phrase for
retry. Data > Clear chat must remain reachable during an active reply, cancel the
stream before DELETE, and keep unrelated destructive/account controls disabled.
A direct count is proof only when it is a nonnegative integer covering every
known local message; malformed, non-JSON, or undersized accepted results must use
exactly one complete canonical history GET and require an empty list. A
contradictory or unverifiable accepted result must retain local history and report
the uncertain persistence state. A verified clear overtaken by navigation must
consume the phrase, leave the newer room intact and unlocked, publish no stale
feedback, and reveal the empty original room when reopened. The ordinary
side/history refresh remains separate from recovery; if it fails, verified local
emptiness remains and the error distinguishes saved state. Browser diagnostics
may contain only explicitly controlled failures, the anonymous refresh response,
and normal cancelled-stream teardown.

Whole-thread deletion acceptance must prove same-tick duplicate suppression,
session-owned mutation custody, and phrase retention after request failure or a
canonical list that still contains the target. Malformed successful DELETE
output must perform exactly one validated owner-scoped list read and accept only
target absence. Verified deletion selects an existing same-companion room or
creates exactly one contract-valid normal replacement, with one recovery list
read when that creation response is malformed or non-JSON.

A delayed accepted delete overtaken by thread navigation may remove only its
target summary; it must preserve the newer selection, publish no stale feedback,
and start no obsolete room refresh. Logout or account replacement must release
local ownership before paint. An older session's completion and `finally` path
must not alter a newer account's list, confirmation, feedback, selection, or
deletion lock. A valid positive delete count followed by list-refresh failure
removes the target locally, consumes the phrase, and reports persisted deletion
separately from unavailable remaining-room state.

Memory-mutation concurrency acceptance must prove synchronous duplicate
suppression before the busy render, native Chat/content-mode/Inspector disabling,
and character-change release before paint. Successful entity responses must be
rejected unless they carry the complete expected shape, character provenance,
state, target identity, and source-message linkage where relevant. Malformed
successful entity/count/conflict responses must recover from validated canonical
Active and Forgotten lists; a failed canonical recovery must report accepted
persistence separately and retain authored drafts where applicable.

Message Remember must not apply its result, feedback, or error after thread
navigation, and the newer room must unlock before the delayed response returns.
Clear-memory persistence failure must retain both memory state and the typed
`CLEAR MEMORIES` phrase. Any parsed successful clear must consume the phrase and
empty both active and forgotten recall, including when active recall was already
empty. A current accepted clear followed by refresh failure must keep the local
empty state, report persistence separately, and remain empty after reload.
Browser diagnostics may contain only controlled failures, the anonymous refresh
response, and normal completed-SSE teardown.

Journal-mutation concurrency acceptance must prove synchronous same-tick
duplicate suppression and native Chat/content-mode/Inspector disabling. Failed
add or edit persistence must retain authored text. Successful add/edit entities
must be rejected unless their complete shape, companion and optional room
provenance, manual source, target, normalized text, timestamps, and bounded
importance are valid; delete requires a positive integer count. Malformed
successful results must perform exactly one validated canonical journal GET and
verify the intended create, update, or deletion before clearing a draft or
claiming success. Failed canonical verification must distinguish accepted
persistence from a failed request.

A room switch during journal work must remain usable without changing the
captured room association, while the character-owned lock remains active until
that operation settles. A companion switch must clear old journal state and
release local ownership before paint. A newer companion action may start before
the delayed old response returns; the old response and `finally` path must not
alter the newer journal list, drafts, feedback, or lock. Reload must recover every
accepted operation from PostgreSQL, and browser diagnostics may contain only the
explicitly controlled failures and anonymous refresh response.

Account-action concurrency acceptance must cover profile save, private export,
and erasure under one synchronous session lock. Same-tick duplicate requests
must be suppressed before React commits its disabled render, and Chat,
content-mode, Settings, Data, and Inspector mutation controls must use native
disabled semantics. A failed display-name save must retain the draft; blank input
must clear the canonical profile. Malformed successful profile output must use
exactly one `/auth/me` recovery read and verify immutable identity, requested
values, and timestamp before applying it.

Export acceptance must reject wrong-owner links, missing collections, invalid
timestamps, and credential-bearing keys without creating a blob URL or download.
A valid export must create exactly one download and revoke its object URL. A
failed account DELETE must preserve password and confirmation. Any parsed
successful DELETE must close its owning session even when its count is malformed.
Logout followed by a newer login must invalidate delayed old profile, export,
and erasure completions synchronously; none may update, download into, publish
feedback in, unlock, or clear the newer session. Browser diagnostics may contain
only explicitly controlled failures and anonymous refresh responses.

The repository does not require a browser-automation runtime dependency for the
MVP. Temporary local tooling may be used for release evidence without adding it
to application manifests.

## LLM tests

Do not require GroqCloud or Ollama in automated tests.

Use:
- mock provider
- mocked Groq streaming/non-streaming HTTP responses
- mocked HTTP responses for Ollama provider
- an opt-in `live` Groq smoke test excluded from CI

Cover context order/trimming/deduplication, exactly-once persistence, stop and
disconnect cancellation, timeout, 429/5xx retries, malformed chunks, provider
fallback, safe error classification, generation telemetry, and asynchronous
memory-job failure isolation. The same checks must exercise ordinary, reroll,
edit, and Groq-compatible SSE paths without buffering or replacing provider
streaming.

Mock-provider assertions must reject diagnostic markers such as provider
prefixes, prompt labels, response-plan narration, memory metadata, relationship
scores, and malformed hidden-context fragments. They must also verify that the
same clean final text is persisted after ordinary and streamed chat.

## Acceptance criteria for MVP

MVP is acceptable when:

- local PostgreSQL starts
- backend starts
- frontend starts
- user can authenticate or documented dev mode exists
- auth refresh tokens are browser-protected cookies rather than JSON/localStorage
- user can send message
- assistant response appears
- response streams if streaming implemented
- message persists after refresh
- unread companion messages persist until their rendered boundary is marked read
- character profile affects prompt
- character soul is editable and compiled without raw JSON
- memory can be stored/retrieved
- unresolved memory contradictions preserve uncertainty and invented memories
  are rejected
- relationship state updates
- emotional continuity decays and conflict repair remains gradual
- relationship absence decay persists on reads and jobs
- debug panel exposes state safely
- tests pass
- lint/build pass
- no forbidden dependencies
- no secrets committed

## Commands

Backend:
```bash
cd apps/api
pip install -e ".[dev]"
alembic upgrade head
pytest
ruff check .
ruff format .
```

Frontend:
```bash
cd apps/web
npm install
npm run lint
npm run build
```

All:
```bash
docker compose up -d postgres
make verify
```

## Goal progress log

For long `/goal` runs, Codex must update:

```text
docs/GOAL_PROGRESS.md
```

This file should describe what has been completed and what remains.
