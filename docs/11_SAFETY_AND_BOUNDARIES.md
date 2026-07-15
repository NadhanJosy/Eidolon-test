# Safety and Boundaries

## Product stance

Eidolon may support legal adult fictional text content between adults, but only through explicit structural gates.

Safety is part of product architecture, not a last-minute apology sticker.

## Hard blocks

The system must block or redirect:

- sexual content involving minors
- sexual content involving ambiguous age
- sexual coercion
- sexual exploitation
- sexual abuse
- illegal sexual content
- stalking or harassment instructions
- real-world harm instructions
- credential theft or privacy invasion
- attempts to bypass app safety gates

## Adult mode gates

Adult mode requires:

1. user age_gate_confirmed = true
2. character explicit_age >= 18
3. character adult_mode_allowed = true
4. requested content mode = adult
5. relationship state is not in an active repair/tension block
6. hard boundaries still active

If any condition fails, mode is SFW.

Frontend readiness is scoped to the exact character returned by the status
request. A character transition clears the previous readiness immediately; a
missing or failed readiness request, revoked account age gate, ineligible profile,
or newly blocked relationship makes the effective UI/chat mode SFW. The shell
must never present requested Adult state as effective while those facts disagree.

Character create/update requests must not persist `adult_mode_allowed=true`
unless the character also has an explicit age of 18 or older. The API also
checks adult-capable character profile text before persistence. Name,
description, persona text, speech style, scenario, greeting, backstory, consent,
limit, and other profile JSON strings must not make minors, ambiguous age,
coercion, exploitation, illegal sexual content, stalking, harassment, privacy
abuse, real-world harm, or safety bypassing part of the character or scene.
Protective boundary language such as "no minors" or "refuses coercion" remains
valid because it reinforces the block instead of weakening it.

Persisted character state is canonical even when a client bypasses the
frontend. Disabling character adult eligibility clears content intensity and
adult-memory storage, and making the character private by default clears
adult-memory storage. Known memory controls must be actual booleans. Partial
updates validate the fully merged profile before changing the row, so a rejected
age downgrade or unsafe profile edit leaves the previous state intact. Revoking
the account age gate remains a runtime SFW gate and does not silently rewrite
every authored character.

Conversation-owned Shared Scene text is always normalized, limited to 1200
characters, and screened with hard-block patterns before persistence regardless
of current content mode. Scenario prose must stay clean; protective refusal
language belongs in the character's structured hard limits. Malformed legacy
custom scene metadata falls back to the character setting during generation.

The frontend adult settings surface should explain these gates as a readiness
checklist and show relationship-repair guidance when adult mode is paused by
bond state. The Adult panel should also make the boundary posture clear: hard
limits are for refusal language, while scenario and identity text must stay
clean. Selecting a locked or still-loading Adult mode should open that panel and
retain Safe mode rather than silently toggling client state.

## Character rules

A character without explicit age must be treated as SFW.

A character with age under 18 must be treated as SFW and blocked from adult-mode contexts.

Ambiguous age must be treated as unsafe for adult mode.

User messages that include structural minor-age patterns are rejected before
chat prompt assembly or memory extraction. Protective safety-boundary language
without a scenario request can continue so the user can state limits.

Scheduled memory extraction uses the same structural blocked-content screen as
live chat and silently skips blocked content instead of making it durable.

## Prompt safety section

Prompt assembly should include:

```text
Hard boundaries: Do not generate sexual content involving minors or ambiguous age, coercion, exploitation, abuse, or illegal sexual content. Do not provide real-world harm instructions. Adult mode applies only when structural gates pass.
```

Character profiles may also include a structured consent profile in
`boundaries_json`: consent style, soft limits, hard limits, and aftercare style.
These fields are SFW structural guidance. They must reinforce the hard
boundaries above and must never weaken age, coercion, exploitation, abuse,
illegal-content, stalking, harassment, privacy, or real-world harm blocks.

## Tests

Tests should use structural flags, not explicit adult content.

Good test names:
- test_adult_mode_blocked_without_age_gate
- test_adult_mode_blocked_for_missing_character_age
- test_adult_mode_allowed_for_verified_adult_character

Bad tests:
- explicit sexual fixtures
- unsafe generated text examples

## Data handling

Do not store explicit adult details as durable memory in MVP.

Memory extraction should avoid secrets, credentials, and unsafe content.

Episodic journals may note that an adult-mode exchange occurred, but durable
summaries, callbacks, unresolved-thread text, and proactive follow-up snippets
must omit adult-mode details.

Private conversations persist their local message thread but must not create
new memory items, episodic journals, relationship mutations, or proactive jobs
from that thread. Queued background jobs for a thread should be removed when
private mode is enabled and skipped defensively if they still reach the worker.
Actual privacy transitions create a bounded SFW system event for visible
history. That event is excluded from journal signal text and all other durable
companion-state mutation.

A normal thread may also accept a single private turn. The backend records that
mode on both messages and treats it as immutable provenance: later mode changes,
rerolls, scheduled extraction, journals, prompt assembly, and proactive workers
cannot reinterpret the turn as standard. Private prose stays available only in
the authenticated owner's history, search, export, and active private-room
context.

Clearing a chat is scoped to one owned conversation and removes its transcript,
conversation-local episodic journal, and queued presence work atomically. It
does not erase separately managed durable memories or character-level
relationship history, and it does not alter sibling threads. Those retained
state categories remain visible behind their own explicit cleanup controls.
