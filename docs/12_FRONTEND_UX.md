# Frontend UX

## UX principle

The frontend is a lightweight, intimate text interface. It should feel like a
private place shared with a long-term companion: cinematic and emotionally
specific, but never like a game engine, CRM, database viewer, or chatbot demo.

## Current experience - full frontend reset

The active product is one full-height companion room. Chat owns most of the
viewport, with a persistent composer, atmospheric initial-based companion
portrait, natural streaming choreography, and only five primary destinations:

- Chat
- Memories
- Relationship
- Moments
- Settings

Past conversations open in a focus-contained shared-history drawer. The active
interface never calls them threads. Companion switching, conversation creation,
owner-scoped search, unread presence, and exact-message focus remain backed by
the existing validated controllers.

The primary screens translate backend-owned state into human experience:

- Memories is a private archive organised around people, promises, moments,
  inside jokes, and patterns. It preserves add/edit/pin/fade/restore/delete and
  conflict-resolution actions without exposing importance/confidence/decay
  values or database terms.
- Relationship uses natural phases, prose about trust/shared language/closeness,
  repair guidance, milestones, boundaries, and a dated change story. It contains
  no affinity bar, raw metric, or numeric score.
- Moments is a dated shared journal of generated episodes and user-authored
  reflections. Generated summaries are rewritten into `You shared` / companion
  language before rendering; callbacks and unresolved moments expand on demand.
- Settings contains companion profile and theme, proactive timing, memory
  posture, conversation privacy, private adult age/consent/intensity/memory
  gates, export, cleanup, account deletion, and logout. Adult mode is never a
  header control.

First-use onboarding is a five-stage guided introduction: emotional welcome,
presence/name/appearance/theme, personality/voice, relationship expectations and
boundaries, then an authored opening line. It persists through the real character
profile API. The same experience can create additional companions.

The visual system uses layered near-black surfaces, warm off-white type, one
restrained terracotta accent, editorial serif hierarchy, ambient gradients/grain,
minimal borders, generous spacing, and persisted Ember/Cedar/Rain/Plum companion
themes. Motion uses CSS only and collapses under `prefers-reduced-motion`.
Desktop uses a narrow icon rail; mobile uses a five-item bottom destination bar.
Both preserve safe areas and keyboard-resizing behavior.

Attachments and voice are not runtime features in the text-only MVP. The
composer includes disabled, explicitly labelled attachment and microphone
affordances so the layout is voice-ready without pretending to upload or record.

All active dialogs/drawers contain keyboard focus, Escape closes dismissible
layers, visible focus styling is shared, fields have programmatic labels, and
the document remains free of horizontal overflow at tested 390px and 1440px
widths. The implementation was also exercised through real registration,
onboarding persistence, SSE chat, generated Moments, all destinations, and the
conversation drawer in Chromium at both sizes.

The controller/reliability record below is retained because those API guards and
mutations still power the reset. Older references to Inspector, Debug/Data
panels, three-pane workspaces, or visible thread/content-mode controls describe
historical presentation only and are not part of the active information
architecture.

## Preserved behavior and API-controller guarantees

MVP pages:

- login/register
- chat
- character settings
- memory viewer
- relationship/debug panel
- account/export settings

### Chat behavior

Must include:

- message list
- input box
- send button
- streaming indicator
- error display
- message timestamps
- character name

Original MVP nice-to-haves:

- reroll button
- edit last user message
- conversation search
- relationship stats drawer

Level 2 implemented:

- conversation rail
- search results
- reroll assistant message
- edit latest user turn with regenerated companion reply and stale-turn cleanup
- delete latest user turn with dependent companion-reply cleanup while older
  user turns hide destructive controls
- memory edit/delete/pin/forget/conflict resolution, with separate Active and
  Forgotten views, reversible restore, and permanent deletion kept distinct
- journal viewer with visibly distinct transcript-owned episodes and personal
  notes, inline personal-note edit/delete controls, preserved failed drafts, and
  anniversary, inside-joke, shared-moment, repair, callback, and open-thread labels
- relationship phase, temperature, momentum, recent shifts, and timeline
- adult gate status/settings
- adult readiness checklist with relationship-repair guidance
- adult consent-profile controls
- adult boundary-posture cue that separates hard-limit refusal language from
  clean scenario and identity text
- character-bound, fail-closed content-mode control with a visible locked state,
  blocked/loading routing to Adult settings, and mode changes frozen during sends
- authored SFW scenario preset picker with custom scenario editing
- per-thread Shared Scene disclosure with preset selection, bounded custom text,
  reset-to-character behavior, persisted/current-scene summary, preserved failed
  drafts, dedicated save state, and stale-navigation guards
- authored character greeting in genuinely empty threads, with a safe fallback
- per-message Remember/Saving/Remembered controls backed by source-linked memory
- data export plus typed scoped confirmations for destructive cleanup, with
  clear-chat scope copy distinguishing transcript/journal/queued-note removal
  from separately managed memories and relationship history
- active reply cancellation before clear-chat so streamed text cannot visibly
  race with a successful wipe
- successful clear-chat resets stale edit, draft, one-turn privacy, and sending
  state before the empty room is reloaded
- active-thread deletion that stays in the same companion context and opens a
  fresh room when no sibling thread remains
- private thread creation/toggle
- one-shot composer privacy with accepted-turn reset and private message labels
- timestamped privacy-transition system event cards with defensive fallbacks
- subtle presence event cards for proactive notes
- per-thread and per-character unread presence counts
- durable exact-message read receipts with sent/read user-line posture
- lightweight visible-tab presence refresh with stale-load protection
- connecting, composing, and streaming presence phases
- conversation-bound stream cancellation with premature-close errors
- natural deterministic mock replies with no provider badge, prompt label,
  hidden score, response-strategy narration, or full current-message echo
- actual last-assembly context manifest plus current retrieval summary in Debug,
  without raw prompt or message prose
- debug-only memory pipeline view for active-thread learning decisions
- debug-only raw relationship metrics and current active-memory snapshots;
  memory prose stays collapsed until requested, is bounded inside the panel,
  and missing legacy snapshots render explicit empty states
- companion-first mobile workspace tabs for threads, conversation, and
  companion state
- full-bleed phone conversation framing with the thread title on its own stable
  row, paired privacy/note commands, and complete workspace labels down to a
  320px viewport
- an internally scrollable, snap-aligned phone context strip that keeps the
  opening line and recent exchange near the first viewport while returning to
  a five-column summary grid on wide screens
- two-line companion-panel navigation items so qualitative badges never force
  Overview, Account, or other primary labels into clipped fragments
- humanized shell relationship/privacy posture with segmented content mode
- API, database, provider, prompt, and job status confined to authenticated Debug
- debug-only scheduler configured/running posture plus readable job outcomes,
  retry timing, and safe failure text
- character-scoped recent generation errors in authenticated Debug, using only
  safe operation/code/provider/timestamp fields and clearing stale Debug context
  when a character refresh fails or is superseded
- private session opening state while the app exchanges the HttpOnly refresh
  cookie for an in-memory access token
- sign-in/register forms without fixture identities or persistent tokens in
  JavaScript-readable storage
- full-viewport, brand-first entry with an unframed semantic form, accessible
  segmented auth modes, checkbox password visibility, and live status feedback
- browser-native email validation and a visible, programmatically associated
  12-character minimum for new passphrases, with server validation authoritative
- IANA timezone, note cooldown, morning, goodnight, and quiet-hours presence
  controls in creation and later Persona editing, with a device-timezone command
- four-stage companion creation for presence, inner life, shared world, and trust
- authored SFW profile foundation instead of an empty or name-only quick-create
- field-level creation validation with stage error markers and first-error focus
- creation draft retention after recoverable API failures
- duplicate-submission prevention when creation persisted but navigation failed
- modal focus containment, Escape/backdrop close, scroll lock, and focus restoration

## Visual style

- dark mode by default
- clean readable typography
- responsive mobile layout
- no document-level horizontal overflow at 320px, 390px, or wide desktop;
  intentionally scrollable context remains bounded inside its labeled region
- standalone web-app metadata with viewport-fit safe areas and keyboard-resizing
  behavior for installed/mobile browser use
- no heavy animations
- no avatars except optional initials/text labels
- no image generation
- no audio recording or playback; the disabled voice-ready affordance is labelled
  as unavailable in this text-only version

The private app shell must advertise `noindex`, send no-referrer and anti-framing
headers, and deny unused camera, microphone, geolocation, payment, USB, and
browsing-topics browser capabilities. The manifest and brand mark are lightweight
static shell assets; no conversation, token, memory, or API response is cached by
a service worker.

## Error copy

Avoid corporate sludge like:

```text
Something went wrong. Please try again later.
```

Prefer product-language copy that protects the stable experience:

```text
Eidolon cannot reach its private service right now. Check that it is running and
try again.
```

Keep error messages helpful and not too cute.

## State handling

Avoid adding Zustand/TanStack Query unless the app needs them.

Native React state is acceptable for early MVP.

The app stores access tokens in React state only. On first open it removes
legacy `localStorage` auth values, attempts one cookie refresh, and then marks
the session ready so the auth screen does not flash during a valid resume.
Refresh calls are deduplicated in-tab, guarded by Web Locks when available
across tabs, retried after transient network failures, and treated as logout
only after a `401`. Every refresh snapshots the local session generation and
expected user. Logout invalidates that ownership synchronously and queues server
revocation behind any accepted cookie rotation, so a late response cannot
restore local state or leave its replacement cookie active on reload.

Passwords exist in React state only while the user composes an auth request.
Changing auth mode, authenticating successfully, logging out, or resetting an
expired session clears the password. Logout also returns the entry form to
sign-in, clears account-scoped display state, and restores SFW content mode.
Sign-in and registration share one synchronous action owner that captures the
mode, canonical email, local session generation, and normalized payload before
I/O. Repeated same-turn submission issues one request, ordinary failures retain
the recoverable form, and stale responses or `finally` paths cannot enter or
unlock another session. The server remains authoritative for email and display
name rules; a dependency-free frontend contract mirrors them to validate every
accepted `AuthResponse`, complete user, bearer token shape, UUID, and timestamp
before state is stored. The decoded, untrusted token claims must also cohere with
the returned user and Eidolon's known HS256 issuer, audience, access type, token
ID, and temporal ordering; API signature validation remains authoritative.

An accepted auth response that is malformed or non-JSON performs one cookie
refresh to recover a complete canonical response. Bootstrap then verifies
`/auth/me`, owned companion and thread collections, and the active companion
under the same session identity. A first-room POST with an unreadable successful
response performs exactly one canonical thread-list read and accepts only one
new matching normal empty room. The entry surface remains visible with accurate
Signing in, Creating account, or Opening room copy until bootstrap settles, so
the authenticated shell never flashes in an incomplete state.

Background presence refresh must avoid overlapping requests, pause in hidden
tabs, and ignore stale history responses after a thread switch. A failed read
receipt must not hide already loaded message history.

Presence collections and read receipts use the same complete owner-scoped
Conversation contract as foreground navigation. A background list must contain
the exact active room and companion before it can merge; malformed, missing,
wrong-owner, wrong-companion, aborted, or superseded snapshots are ignored.
Presence merges preserve rooms missing from that background snapshot and advance
each summary field-wise: title/privacy/scene follow the newest `updated_at`, while
last-message and read-cursor timestamps advance independently. Unread count may
fall only when the incoming snapshot covers both the latest known message and an
equally new read cursor, so an older presence response cannot roll back a newer
foreground title, privacy, scene, message, or receipt.

History remains canonical even when its follow-up receipt is unavailable or
malformed. A receipt must match the authenticated owner, exact room, and expected
companion before merging. A companion profile fetched as a navigation fallback
must similarly match both the current session owner and requested companion ID;
otherwise the last stable room is restored with a readable error.

Companion-state hydration treats every endpoint as an untrusted runtime boundary.
Memory and journal lists require unique IDs and exact companion provenance;
relationship, adult readiness, scheduled jobs, character Debug, conversation
Debug, and runtime-health payloads require their complete bounded shapes before
entering React state. Metrics must be finite and in range, timestamps offset-aware,
JSON bounded by depth/fan-out/key/string/byte limits, and adult `allowed` state
must agree with effective mode, reasons, and intensity. A malformed health payload
is degraded rather than healthy, and a malformed adult response fails closed.

The slices settle independently: unavailable private Debug routes cannot block
chat, memory, relationship, journals, or adult readiness. Switching companions
clears the previous companion's cognition before requests settle; request-version
and caller ownership guards reject delayed navigation or logout results. A
transient same-companion failure may retain the last complete user-facing memory,
journal, or relationship snapshot, while malformed/failed Debug, jobs, and adult
readiness are cleared so stale operational or eligibility state is never shown.

Character and thread selection must return an explicit success result. Mobile
navigation enters the conversation only after success. Overlapping selection
requests use a monotonic version, and a failed active request restores the last
fully loaded character/thread pair.

Conversation search is owned by the current thread, normalized, and bounded to
the API's 120-character limit. It has distinct idle, searching, no-match,
results, and inline-error states; typing alone must not claim there are no
matches. A synchronous request owner suppresses duplicate submission, and query
changes or navigation invalidate delayed success and failure responses. Results
use human author labels and timestamps. Activating one opens the Conversation
workspace on mobile, scrolls to the exact ordinary, proactive, or system message,
and moves keyboard focus there with reduced-motion behavior respected.
Every result uses the complete Message/transcript contract, including exact room
provenance, unique UUIDs, ordered offset timestamps, bounded content/metadata,
and known role/privacy/content modes. A malformed result fails the inline search
without inserting or focusing untrusted content.

Character creation and profile saves share one synchronous session-owned action
lock in addition to their rendered progress state. Each action snapshots the
authenticated owner, access token, session generation, navigation version,
target where applicable, canonical payload, and authored draft. Logout or a
replacement account invalidates ownership before paint, so an older response or
`finally` path cannot replace the new account's character list, draft, feedback,
room, or action lock. Room navigation remains available; a same-session save may
update its character summary but can replace the active draft and refresh
readiness only while that character and the captured current room still match.

Successful character entities must carry the complete API shape, exact owner and
target, valid UUIDs and timestamps, bounded profile JSON, consistent adult gates,
and the submitted canonical fields. A malformed or non-JSON successful create
uses one canonical character-list read and accepts only one newly persisted exact
match. A malformed successful save uses one canonical target read and verifies
the exact payload. Failed persistence and accepted-but-unverifiable writes retain
the authored draft and use distinct copy. Persona and Adult edit inputs carry the
same native bounds as the builder. Chat, content mode, creation, account/privacy,
and Inspector mutation commands use native disabled semantics while companion
work is active; panel and room navigation may remain available for reading.

New and Private thread creation share one synchronous session-owned action.
The request snapshots the current owner, access token, session generation,
companion, privacy mode, navigation version, and known thread IDs. A failed
request keeps the current room stable and restores both commands. Successful
responses must contain a complete owner-scoped empty thread with the expected
companion, privacy/default-scene metadata, UUIDs, read state, and ordered
timestamps. A malformed or non-JSON success performs exactly one canonical
thread-list read and accepts only one unambiguous new matching room.

Ordinary character and thread navigation remains available while creation is
settling. If navigation overtakes an accepted create, the new summary may appear
in its owning session's rail, but it cannot replace the active room or publish
stale feedback. Logout and replacement login invalidate ownership before paint;
an older response or `finally` cannot insert into, navigate, notify, or unlock a
newer account. New, Private, companion creation, Chat, content mode, account/
privacy, and Inspector mutations use native disabled semantics, and the owning
rail command shows a stable Opening state.

Selecting a companion with no existing room uses a separate session-owned
provision action rather than trusting an incidental creation response. It
captures the owner, token, session generation, navigation version, companion,
and known thread IDs. The action may nest only under the exact companion-create
mutation that owns it; every unrelated companion, explicit-room, deletion, and
provision mutation is excluded. Same-target reactivation is synchronously
ignored and that companion row alone exposes native disabled and Opening room
state, while other room and companion navigation remains available.

The provisioned room must satisfy the complete normal empty-thread contract. A
malformed or non-JSON success performs one canonical owner-scoped list read and
accepts only one new exact match. Failed or unverifiable creation restores the
last fully loaded companion/room pair and never activates untrusted response
data. Navigation overtaking may merge a verified same-session summary but cannot
replace the newer selection or publish feedback. Logout and account replacement
invalidate provision custody before paint, including a nested parent mutation,
so an old response or `finally` path cannot alter or unlock the newer session.

Thread-title saves follow the same ownership rule. The title input is bounded to
the API's 200-character limit and blank input deliberately clears the title. A
request snapshots its thread, title, and navigation version, preserves the draft
on failure, and cannot be submitted twice before the busy render commits. A
delayed success may update that thread's title in navigation, but it must not
replace the active conversation or title editor after a newer selection wins.

Thread-privacy changes are backend-confirmed rather than optimistic and have
synchronous single-request ownership. A failed request leaves the visible mode
unchanged. A delayed success may update only the matching thread's privacy and
monotonic activity fields after navigation; it cannot replace the active thread
or launch obsolete history and companion-state refreshes. A current success
reloads history immediately so its backend-owned privacy event is visible. If
that refresh fails after persistence, the UI reports the saved and unavailable
outcomes separately.

Shared Scene changes also have synchronous single-request ownership in addition
to their dedicated rendered save state. Custom text is normalized and checked
against the 1,200-character API bound before submission. Failed persistence
retains the draft. A stale success updates only that room's canonical scene and
monotonic activity fields; it cannot replace the active draft or refresh an old
history. A current success uses one guarded companion/history refresh, renders
its backend event immediately, and reports a persisted scene separately from a
failed follow-up refresh.

Latest-turn edit regeneration is owned by its conversation and has a synchronous
single-request lock in addition to the rendered sending state. The request
snapshots the account owner, access token, local session generation, thread,
character, message, and exact bounded draft. Failed persistence retains the
active edit draft. Thread navigation clears composer text, edit mode, and
one-turn privacy so content cannot travel into another room; logout invalidates
all message work before the next account can render. A delayed old response or
`finally` path cannot alter new-session or new-thread messages, notices, errors,
side state, or action locks. A direct response must contain the exact edited
user text and a complete subsequent assistant reply. A malformed/non-JSON
accepted response performs exactly one complete canonical history read and must
verify that same turn before local application. The normal guarded companion and
history refresh remains separate. Persisted but unverifiable edits and failed
post-save refreshes instruct the user to reload instead of claiming persistence
failed. Save and Cancel are natively disabled while regeneration owns the edit.

Reroll and single-message deletion share a conversation-owned synchronous action
lock. Their requests snapshot the account owner, access token, local session
generation, operation, thread, character, message identity, and known message
IDs; reroll also snapshots content mode and deletion snapshots the original role.
Same-frame repeated actions cannot create duplicate generations or deletes.
Navigation releases the new room immediately and invalidates old local ownership
without cancelling an accepted backend operation. A delayed old response cannot
append a reply, remove content, refresh old side state, or publish feedback in the
new room. Current rerolls verify assistant role, conversation, and `reroll_of`
provenance before optimistic insertion; current deletes verify a positive count.
Malformed/non-JSON accepted rerolls and deletes perform exactly one complete
canonical history read and require an unambiguous new reroll or proven target
absence. Both then perform the normal guarded companion/history refresh, retain
safe local changes when that refresh fails, and report persistence separately
from refresh availability.
Composer, content-mode, message-action, and Inspector mutation controls use
native disabled semantics while the current room owns one of these actions.

Every transcript boundary is runtime-validated before entering React state. A
message must have valid UUID provenance, an allowed role, nonempty bounded
content, an offset timestamp, and bounded JSON metadata with known privacy and
content modes. Canonical histories reject duplicate IDs, mixed conversation
ownership, malformed metadata, and decreasing timestamps. Account reset aborts
the active stream and invalidates edit, reroll, and delete ownership together.

Manual check-ins and clear-chat share a separate synchronous, session-owned
conversation action. Each request captures the account owner, access token,
session generation, operation, room, companion, and known message IDs before
I/O. Navigation releases the new room before paint, and logout or account
replacement invalidates old custody. Delayed responses and `finally` paths may
not append or reset messages, publish feedback, refresh obsolete state, or
unlock a newer account or room.

A readable JSON `null` from a manual check-in is the valid paused, snoozed, or
cooling-down outcome. A direct note must satisfy the complete Message contract,
belong to the owned room, be a new proactive assistant message, and remain within
the API's 600-character bound. A malformed or non-JSON accepted result performs
exactly one complete canonical history read and accepts only one unambiguous new
proactive message. The verified note appears locally before the ordinary guarded
side/history refresh, so refresh failure reports saved state separately.

Clear chat remains available from Data while a reply is streaming and first
cancels the owned stream. Other destructive, account, export, and memory controls
remain disabled during streaming. A direct delete count must be a nonnegative
integer at least as large as the known local transcript; otherwise exactly one
complete canonical history read must prove that the room is empty. Local chat is
reset only after either proof. Contradictory or unverifiable accepted responses
preserve the transcript and ask for reload instead of claiming success. The
`CLEAR CHAT` phrase is retained after failed persistence. It is consumed after
verified current-room persistence or after an accepted action is overtaken by
navigation, because the old panel is no longer eligible to recover or publish
its result. The ordinary guarded side/history refresh is separate from canonical
recovery and cannot weaken that proof.

Thread title, privacy mode, and Shared Scene writes share one synchronous,
session-owned metadata action. It captures the owner, token, session generation,
target room and companion, and canonical intent before I/O, and is mutually
exclusive with companion and room create/delete/provision work. Every successful
response must be a complete owned Conversation matching the exact submitted
title, privacy mode, or scene. A malformed/non-JSON accepted PATCH performs one
canonical owner-scoped thread-list read and selects that exact room; unverifiable
persistence retains authored title/scene input and fails closed.

A verified same-session result may update its room summary after another room is
selected, but only the still-active target may canonicalize its draft, refresh
side state, or publish feedback. Logout or account replacement invalidates the
action before paint, and an old response or `finally` branch cannot unlock or
alter the newer session.

Whole-thread deletion has its own synchronous, session-owned action. It captures
the authenticated user, token, session generation, navigation version, room,
and companion before issuing one DELETE. Failed persistence keeps the current
room and typed `DELETE THREAD` phrase intact. A malformed successful response
must be verified by one complete owner-scoped thread-list read; target absence
proves deletion, while a list that still contains the target fails closed.

After verified deletion, an existing room for the same companion is selected.
If none remains, replacement creation uses the same complete conversation
contract and one-list-read malformed-success recovery as New and Private.
Thread navigation remains available while deletion settles: canonical removal
may update the rail, but an overtaken response cannot replace the newer room,
publish feedback, or refresh obsolete state. Logout and account replacement
invalidate custody before paint, so an old response or `finally` path cannot
alter or unlock a newer session. A valid positive delete count remains
authoritative if the follow-up list is temporarily unavailable; the target is
removed locally and persistence is reported separately from refresh failure.

Memory mutations share one synchronous character-owned action lock across manual
add/edit/pin/delete/forget/restore, conflict resolution, message Remember,
low-value fading, and clear-all. The request snapshots its character, optional
conversation, target, and authored input before awaiting. A character change
invalidates local ownership before paint; a thread change invalidates only
message-owned Remember work, while other character-wide changes may finish
without refreshing the old thread. Delayed responses cannot clear a newer lock
or publish stale errors and notices.

Every mutation response is runtime-checked for complete memory shape, character
provenance, finite bounded scores, timestamps, forgotten state, source-message
linkage, delete counts, or conflict-resolution IDs as appropriate. Malformed
successful responses recover from validated canonical Active and Forgotten lists
before the UI claims the result. Failed persistence retains add/edit drafts and
the `CLEAR MEMORIES` phrase. Any parsed successful clear is authoritative,
empties both active and forgotten local state, consumes the phrase, and remains
empty if its guarded companion/history refresh fails. Clear-all stays available
when active recall is empty because forgotten memories are still durable account
data. Chat, content-mode, and Inspector mutation controls are natively disabled
while the current character owns memory work; thread navigation remains usable.

Personal journal add, edit, and delete share one synchronous character-owned
action lock. Each request snapshots the companion, optional source room, target,
normalized title and summary, and known journal IDs before awaiting. Room
navigation remains available because the journal is companion-wide and cannot
change the captured source-room association. Companion navigation invalidates
local ownership and clears journal forms before paint; an older completion cannot
replace the new companion's list, publish feedback, or clear a newer action.

Successful journal entities are runtime-checked for complete ownership,
conversation provenance, manual-note source, bounded importance, collections,
metadata, timestamps, target identity, and normalized authored text. Delete
responses require a positive integer count. Malformed successful responses
recover through one validated canonical journal-list read and verify a newly
created matching row, an exact updated target, or target absence before claiming
success. Persistence failures preserve add and edit drafts. Accepted persistence
that cannot be verified is reported separately and asks for a reload. Add fields
carry accessible labels and the API's 200/2,000-character limits. Chat,
content-mode, proactive/data actions, and Inspector mutations use native disabled
semantics while journal work is active; thread navigation remains usable.

Account profile saves, private export, and account erasure share one synchronous
session-owned action lock. Every action snapshots the authenticated user ID,
immutable email, access token, and a local session generation before awaiting.
Logout and account replacement invalidate that generation synchronously, so a
delayed old-session response cannot replace the current user, create a download,
publish feedback, clear a newer lock, or erase the newer local session.

Display names are normalized and bounded to 120 characters before persistence;
blank input explicitly clears the stored name. Successful profile responses must
contain the complete expected user, immutable identity, requested values, and a
valid creation timestamp. Malformed successes recover through one canonical
`/auth/me` read. The authored name remains available after failed persistence,
and accepted-but-unverifiable changes are reported separately. Companion
readiness refresh follows the current loaded room, retries once if navigation
overtakes it, and never refreshes an obsolete room.

Private export validates its timestamp, account identity, required collections,
unique character/thread identities, cross-collection ownership links, and the
absence of credential-bearing keys before creating a JSON file. Invalid exports
fail closed without a download. The temporary anchor is attached only for the
click and the object URL is revoked asynchronously after the browser receives
it. Account erasure still requires the current password and exact phrase; any
parsed successful DELETE is treated as authoritative and closes only its owning
session, while a failed request preserves both fields. Chat, content mode, and
Inspector mutation controls are natively disabled during account work, while
navigation remains available.

Adult readiness carries the character ID it was fetched for. Effective content
mode is Adult only when that ID matches the active character, the current account
and profile remain eligible, and the backend status is allowed. Character changes
reset requested mode; same-character thread changes preserve it. Failed status
refreshes and newly closed gates reset to Safe without waiting for another send.
Loading and failed readiness are distinct UI states so a failed request cannot
leave the Adult panel claiming that a check is still in progress.

Adult settings use the same strict whole-number age parser as character
creation; partial numeric strings, decimals, negatives, and values above 150 do
not open eligibility. Draft transitions remain canonical before save: an
ineligible age or eligibility-off action resets intensity to Off and disables
adult-memory storage, while private-by-default clears adult-memory storage.
Intensity and storage controls remain unavailable while their prerequisites are
closed. A revoked account age gate locks enabling and dependent edits but still
allows an already eligible character to be turned off; revocation itself does
not silently erase authored character configuration.

Character creation, Persona editing, Adult settings, and final API payload
construction share one pure character-draft canonicalizer. Switching surfaces
must not reveal a stale eligibility, intensity, or adult-memory value that a
previous surface already closed. Private-by-default disables and clears adult
memory storage in the staged builder and Persona editor as well as in Adult
settings. Validation still preserves malformed text long enough to explain it;
canonicalization closes permissions but does not disguise invalid input.

Character creation returns a structured result that distinguishes a recoverable
request failure from a profile that persisted but could not be verified or
selected. The builder flips a synchronous submit ref before awaiting, remains
open with its draft after recoverable failures, and disables resubmission after
verified persistence so neither same-turn activation nor a transient navigation
failure can create a duplicate companion.

## Streaming

For SSE/fetch streaming:

- show partial assistant message as chunks arrive
- show a stable composing state before the first chunk
- let deterministic mock cadence reflect authored speech pace and reply length
  while keeping composing and token delays tightly bounded
- disable duplicate sends while generating and replace the send affordance with
  a working stop control
- disable edit, reroll, remember, and delete actions while generation owns the thread
- expose edit only for the latest user turn and replace its stale companion
  replies with the regenerated response after save
- expose user-turn deletion only on the latest user turn and remove dependent
  companion replies from local state after backend acceptance
- store final message only once
- avoid duplicate partial messages after refresh
- abort and ignore late events when the user switches conversations
- report EOF without a final or error event as an incomplete reply
- preserve the draft and one-shot privacy selection until `message_start`
- render a transient pending user bubble immediately on send, then replace it
  with the canonical user row at `message_start` without creating a local
  duplicate or clearing a pre-acceptance draft
- accept `message_start` only once for a new user-message ID whose content and
  conversation exactly match the submitted turn
- ignore token events before a valid start, reject malformed fragments, and
  enforce the same 24,000-character bound used by complete stored messages
- accept `message_done` only after a valid start and only for a new, complete
  assistant message in the owned conversation; later events cannot reopen it
- treat malformed JSON, invalid boundaries, and bounded server error events as
  terminal for local stream application, then reconcile from canonical history
- clear one-shot privacy on accepted send, thread switch, logout, or app reset
- keep a stopped/failed final user turn visible with a retry control; refresh
  reconstructs this state from canonical message metadata
- disclose the configured inference provider discreetly near the composer

## Accessibility

- readable contrast
- keyboard submit
- form labels where practical
- button disabled state
- no animation-dependent interactions
