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

## Memory and scheduled work

Blocked or private message content is not eligible for automatic memory,
episodic journal detail, relationship updates, or proactive context. Memory
preferences can reduce automatic learning but may not disable safety/boundary
handling.

Adult episode detail is not copied into durable journal callbacks or proactive
anchors. Scheduled jobs use the same hard-block screen and minimal SFW prompts.
Provider output that is empty, malformed, oversized, credential-like, unsafe,
or hidden-context-bearing is discarded in favour of safe deterministic fallback
where the job supports one.

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
- exports and diagnostics excluding secret/private implementation material
- proactive generation rejection and safe fallback
