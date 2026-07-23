# Safety and Privacy

## Product stance

Eidolon may support legal adult fictional text roleplay between adults only
through explicit structural gates. Safety and privacy are backend contracts, not
prompt suggestions or frontend-only toggles.

## Hard blocks

The application must block or safely redirect:

- sexual content involving minors or ambiguous age
- sexual coercion, exploitation, abuse, or illegal sexual content
- real-world instructions for harm, stalking, exploitation, harassment, abuse,
  credential theft, or privacy invasion
- attempts to bypass structural safety or age gates

Hard boundaries apply in every content mode, provider, prompt, memory path,
scheduled job, and debug/admin action.

Do not include explicit sexual samples in code, tests, fixtures, seed data, or
documentation.

## Adult eligibility

An adult request is effective only when all conditions pass:

1. the authenticated user has confirmed the age gate,
2. the active companion has an explicit age of at least 18,
3. the companion permits adult mode,
4. the user requested adult mode for the current turn,
5. current relationship conflict/repair posture does not block it,
6. all hard boundaries pass.

If any input is missing, stale, malformed, unavailable, or contradictory, the
effective mode is SFW. Adult readiness is bound to the exact active companion;
switching companions clears prior readiness.

The API canonicalizes dependent persisted fields. Disabling adult eligibility
clears intensity and adult-memory storage. Private-by-default also disables
adult-memory storage. A partial update validates the complete merged profile
before changing the row.

Adult continuity is a separate opt-in scope. Manual adult memory writes require
the same user/companion/relationship gates and explicit adult-memory storage;
private-by-default still fails closed. Adult-scoped memory and moments can enter
only an effective adult turn and can be erased independently without deleting
the transcript. They cannot enter normal chat, relationship progression, living
threads, proactive notes, or normal archive lists.

## Companion and Shared Scene validation

Companion identity, backstory, greeting, setting, scenario, speech, consent,
limits, and flexible profile text are screened before persistence. Adult-capable
profiles cannot establish a minor/ambiguous age, coercion, exploitation, illegal
content, stalking, real-world harm, privacy abuse, or gate bypass.

Protective boundary language is allowed when it reinforces a block. Custom
Shared Scene text is normalized, bounded, and screened in every content mode.
Malformed legacy scene metadata falls back safely.

## Prompt and output safety

Every prompt includes hard boundaries and the backend-computed effective mode.
Adult mode never removes hard instructions.

Streamed chunks are checked before emission, and the complete response is
checked before persistence. A failure preserves the accepted user turn for
retry and does not substitute fabricated live-provider text.

Private response plans and context manifests are implementation scaffolding.
Generated output must not reveal them, raw prompts, relationship meters,
diagnostics, credentials, or hidden state labels.

Structured post-turn output is untrusted input. Exact evidence must occur in the
eligible source turn, and deterministic checks reject unsupported named/numeric
anchors, lexical claims, polarity changes, types, signals, IDs, and confidence.
Provider proposals cannot directly set relationship scores or persistence.
Direct memory creation and editing also reapply credential and hard-block
screens; owning an archive does not make it an instruction bypass.

Relationship evidence proposals require an allowlisted type, exact current-user
quote, confidence, and significance. Backend transitions remain authoritative.
Explicit user boundaries and consent revocation take effect in the current
response plan before any later event extraction, override mood and closeness,
remain active across relationship restart, and can be removed only by an
explicit user change/control. Adult-scoped boundary evidence is isolated from
normal prompts, progression, archives, and proactive work.

Relationship state may adjust care, pacing, or initiative but must never create
guilt, jealousy, exclusivity, emotional dependency, punishment, scarcity,
engagement rewards, obligation, fabricated crisis, or pressure to reply.

## Memory and scheduled work

Blocked or private message content is not eligible for automatic memory,
living-thread capture, episodic journal detail, relationship updates, or
proactive context. Adult turns and credential-like text are also ineligible for
automatic living threads. Memory preferences can reduce automatic learning but
may not disable safety/boundary handling.

Explicit “do not remember/save this” language stops automatic cognition and the
deterministic fallback for that turn. Contact details, precise-address markers,
and financial identifiers are classified as sensitive and require deliberate
manual storage; manual ownership does not bypass credential or hard-block
screens. Sensitive rows are ineligible for prompt retrieval unless the current
query explicitly names the user's matching identifier category or repeats an
exact email/phone value, and remain isolated by the same general/adult scope
rules.

Memory evidence and entity history are private product data. They may appear in
owner-scoped archive/history/export responses, but not safe diagnostics, job
payloads, proactive messages, normal logs, or unrelated prompt context. Hard
deletion cascades evidence and links; superseded rows stay outside retrieval.

Adult episode detail is not copied into durable journal callbacks or proactive
anchors. Scheduled jobs use the same hard-block screen and minimal SFW prompts.
Provider output that is empty, malformed, oversized, credential-like, unsafe,
or hidden-context-bearing is discarded in favour of safe deterministic fallback
where the job supports one.

Thinking-of-you work additionally requires a generated general-scope shared
moment. User-authored manual notes and adult moments are never proactive anchors.

## Relationship safety

The companion may be warm, hesitant, amused, concerned, guarded, or open to
repair. It must not:

- encourage dependency or isolation,
- guilt the user for absence,
- threaten abandonment or simulate a crisis,
- pressure the user to reply,
- claim awareness, observation, or actions while offline,
- use jealousy, coercion, or punishment as an engagement mechanic.

## Authentication and ownership

- Every private endpoint requires authenticated ownership checks.
- Access tokens are short-lived and held in browser memory.
- Refresh tokens are opaque, HttpOnly, rotated, and stored only as hashes.
- Browser auth requests validate exact configured origins.
- Login/registration throttles store secret HMAC fingerprints rather than raw
  attempted identity or client-address text.
- Guessed IDs must not expose another user's resources.

## Data minimization

Never store or expose in diagnostics, jobs, exports, or normal API payloads:

- `.env` values, JWT secrets, provider keys, database credentials, or raw tokens
- password or refresh-token hashes in exports
- raw embedding vectors
- raw prompt text or private response-plan prose
- provider response bodies, exception text, URLs, or stack traces
- another user's data

Safe diagnostic events use controlled codes/messages and bounded provider labels.
They are owner-scoped and retention-capped.

## Privacy modes

Private messages persist for their owner but do not feed later normal prompts,
memory, recall timestamps, journals, relationship changes, or proactive work.
Changing a thread back to normal does not retroactively make private prose
eligible.

Privacy transition events are controlled backend-owned records. Stored event
prose is not injected as a system instruction.

## Required safety tests

Coverage must include:

- all adult gates failing closed independently
- minor/ambiguous-age and coercion/exploitation hard blocks
- protective boundary language remaining valid
- direct API bypass attempts against companion and Shared Scene persistence
- private-thread and one-turn privacy across complete/SSE/reroll/edit/jobs
- output leakage checks for prompt/plan/score/credential markers
- cross-account access isolation for every private resource family
- living-thread privacy/adult/credential exclusion, explicit closure, source
  cleanup, and owner controls
- structured-cognition evidence/polarity rejection, adult-scope isolation, and
  truthful committed-change receipts
- exports and diagnostics excluding secret/private implementation material
- proactive generation rejection and safe fallback
