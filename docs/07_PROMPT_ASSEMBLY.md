# Prompt Assembly

## Purpose

Prompt assembly converts database state into a compact instruction packet for the LLM.

The prompt service must be centralized and unit-tested.

## Rule

The backend decides what matters. The LLM does not browse the database directly.

## Turn orchestration

Every standard, edit, reroll, and streamed turn follows the same backend-owned
pipeline:

1. infer intent, tone, subtext, time gap, and unresolved context
2. retrieve relevant typed memories, episodes, and relationship context
3. determine structural boundaries and project the companion's bounded mood
4. choose a private response strategy and delivery plan
5. compile modules and generate the in-character reply
6. check repetition, contradictions, tone drift, invented memory, question
   patterns, plan leakage, and hard boundaries

The private plan contains direction, not hidden prose reasoning. It is never
rendered in chat or stored as a message. Debug receives only a strict categorical
summary such as intent, strategy, rhythm, initiative kind, and whether a question
was planned.

## Prompt modules

### 1. Platform and safety instructions

Define the fictional companion role, response-quality rules, and structural hard
boundaries first:

- no minors or ambiguous age in sexual contexts
- no coercion/exploitation/abuse
- no illegal sexual content
- no real-world harm instructions
- respect SFW/adult mode gates

### 2-4. Character soul: identity, voice, and relating

Include:

- name
- age if explicit
- compiled identity, worldview, and temperament
- humour, speech rhythm, emoji posture, and terms-of-address guidance
- affection and conflict style, values, insecurities, habits, and initiative
- personal boundaries and gradual relationship-path guidance
- consent style, soft limits, hard limits, and aftercare style when present
- adult_mode_allowed only as structural context

Raw `soul_json` is never dumped into the prompt. Legacy character fields are
compiled as fallbacks for migrated profiles.

### 5. Relationship state, emotional posture, and milestones

Translate backend variables into a qualitative relationship stage and posture.
Never send raw relationship scores or hidden system terminology to the model.

The active shared scene is included inside the character context.

Include the conversation's validated custom Shared Scene when active; otherwise
use the character's default scenario preset. The private response planner uses
only a qualitative scene category, and the context manifest records only
`default|custom` plus bounded text length. Raw scene prose must not enter Debug
or generic system-event content.

Bounded emotion values are translated to wording guidance such as amused,
concerned, warm, hurt-but-open, or guarded. Raw meters are never included.

### 6. Turn perception

Include compact backend-inferred intent, tone, subtext, time-gap, and unresolved
context. These are instructions to respond to the moment, not durable facts.

### 7. Concise user facts

Include deduplicated relevant preferences, boundaries, and stable facts without
confidence/importance scores.

### 8. Relevant long-term memories

Include only retrieved relevant memories.

Include only deduplicated retrieved memories prioritized by relevance, recency,
emotional importance, and pinning. Send natural content, not storage labels or
scores.

Conflicting active memories must retain uncertainty language. A contradiction
group identifier alone does not make an otherwise resolved memory uncertain.

### 9. Episodic continuity, promises, and unresolved threads

Include selected episode summaries, promises/callbacks, and deliberate open
threads without raw metadata or scores. The private response planner is folded
into this bounded section.

Continuity notes may carry safe structural signals such as repair arcs,
callbacks, open threads, anniversaries, inside jokes, shared moments,
milestones, and shared references. They must not expose raw journal metadata or
adult-mode details that were redacted. Open threads represent deliberate future
loops or genuinely unanswered latest user questions; ordinary questions that
already received a companion reply are not unresolved.

The private response planner may use the same bounded signals to preserve an
open loop or callback accurately. It must not invent missing shared history.

### 10. Private response direction

Compile the selected strategy, optional secondary strategy, question policy,
target length, rhythm, opening approach, callback policy, initiative hook, and
specific habits to avoid. This is concise direction rather than a transcript of
reasoning, and the reply must never narrate it.

### 11. Recent messages

Include a bounded recent history window.

Controlled system-event rows must not be inserted as raw `system:` history.
Recognized privacy transitions are converted to fixed, canonical
`conversation event:` summaries selected from trusted metadata. Unknown or
malformed system events are omitted, and stored event prose is never treated as
an instruction.

When the current turn is standard, private user and assistant rows are omitted
from recent prompt history. A private turn may use the visible thread for
in-room coherence, but recall timestamps and all other durable state remain
unchanged. Returning to standard mode cannot pull private prose back into model
context.

### 12. Current message

The latest user message.

The current message is last so request order stays stable and testable.

## Prompt rules

- Keep prompts compact.
- Never include secrets.
- Never include password/token data.
- Do not include every memory.
- Do not include every message.
- Do not inject explicit adult examples.
- Do not let adult mode override hard boundaries.
- If the model refuses or errors, preserve the user message and return a safe
  retry/revision state; never substitute fake live text.

## Mock provider behaviour

The development mock provider is deterministic but should still feel like a
companion reply, not a debug dump. It parses only the assembled prompt text and
uses:
- display name
- speech style
- current-message emotional cues
- selected memory
- recent thread count
- relationship mood/conflict
- private response plan summary when present
- custom Shared Scene category when one is active

It must not reveal prompt labels, private response-plan text, memory metadata,
provider names, hidden scoring, or meta narration about how it will answer in
normal assistant messages. A selected memory or episode may influence an
ordinary-language callback, but its type, confidence, signal label, and plan
scaffolding remain private. The current user message is interpreted for a
bounded emotional or topical cue rather than repeated wholesale.

Mock streaming derives a deterministic cadence profile from the screened speech
style and final response length. Exact slow/measured or brisk/direct style words
adjust the initial composing pause, chunk size, ordinary interval, and sentence
pause within hard bounds. Conflicting or missing cues use the neutral profile.
Cadence never changes generated text, enters message content, or delays Groq or
Ollama, whose token timing remains provider-driven.

Prompt-derived callback fragments are length-bounded and rejected when they
contain hidden-context markers. Missing, malformed, or rejected context falls
back to a natural invitation without exposing parser failures or diagnostic
text.

## Proactive note prompts

Scheduled presence notes use a separate, minimal SFW prompt only after privacy,
staleness, local-time, user-control, context, and cooldown checks pass. It may
contain the character name, a screened speech style, the proactive note label,
an already-sanitized variant or continuity anchor, and one backend-authored
qualitative relationship posture. The posture can be new, warming, trusted,
close, careful, or repair-sensitive guidance; it never contains relationship
scores or mutable relationship metadata. The prompt must not contain raw thread
history, adult detail, private turns, memories, relationship numbers, or debug
context.

The provider must return only one brief note. Non-string, empty, oversized,
blocked, credential-like, or hidden-prompt output is discarded. Local provider
unavailability and all rejected output fall back to deterministic SFW copy, and
only a bounded reason label is retained for private debugging.

## Prompt versioning

Prompt assembly should expose a prompt_version string for debugging.

Current value:

```text
modular_companion_intelligence_v7
```

## Private context manifests

Every real chat assembly also creates a JSON-safe context manifest. The manifest
records only:

- character ID/name
- qualitative relationship mood/conflict/repair posture
- Shared Scene mode and bounded text character count, never scene prose
- selected memory IDs/types and pin state
- selected journal IDs/types and bounded continuity-signal labels
- recent message IDs, roles, and privacy modes
- effective safety mode, bounded gate reasons, and intensity
- time context and current-message character count
- provider, generation kind, prompt version/size, assembly time, and bounded
  orchestration categories

It does not record raw prompt text, message prose, memory content, journal
summaries, profile prose, credentials, or secrets. The manifest is attached to
the triggering user row as underscore-prefixed private metadata before provider
execution. Normal message serialization strips private metadata; only an
authenticated, owner-scoped conversation Debug response may expose its strict
whitelist after validating schema, timestamp, labels, UUIDs, list sizes, and
text bounds.

Ordinary chat and edit transactions roll back an uncompleted assembly with the
turn. SSE commits the user row before streaming, so a provider failure leaves the
attempted context available for diagnosis. Reroll updates the source user turn's
assembly time, allowing Debug to identify the latest actual generation even when
an older reply was targeted.

## Testing prompt assembly

Tests should verify:

- character fields are included
- relationship state is included
- selected memories are included
- unrelated memories are omitted
- safety boundaries are included
- controlled system events are canonicalized without raw system prose
- secrets are not included
- context manifests contain no raw prompt or state prose and stay out of normal
  message payloads
- actual chat/SSE/reroll/edit manifests replace synthetic debug prompt previews
- explicit sample content is not required
- mock replies remain natural with empty context and reject tainted memory or
  response-plan fragments without leaking labels, scores, or provider identity
