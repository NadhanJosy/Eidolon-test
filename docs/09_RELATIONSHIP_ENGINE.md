# Relationship Engine

## Purpose

Relationship state makes the character's tone and behaviour evolve over time.

This is not magic. It is bounded variables plus prompt injection. Civilization continues to overcomplicate this, somehow.

## MVP variables

### trust

How safe/reliable the relationship feels.

Range: -100 to 100

Changes slowly.

### intimacy

Emotional closeness.

Range: 0 to 100

Increases with ongoing meaningful conversation.

### warmth

Current friendliness/affection.

Range: -100 to 100

Can change faster than trust.

### tension

Unresolved conflict or discomfort.

Range: 0 to 100

Increases with negative/conflict signals, decays slowly.

### familiarity

Amount of shared interaction history.

Range: 0 to 100

Usually increases with messages.

### attachment

Longer-term closeness/dependence simulation.

Range: 0 to 100

MVP can update very slowly or leave near zero.

## Level 2 metadata

Relationship state also tracks:

- mood
- conflict_state
- repair_needed
- tags_json
- timeline entries in metadata_json
- one-time milestone ids in metadata_json
- recent human-readable changes in metadata_json

These fields are deterministic backend state. They should explain tone and continuity without turning the system into a manipulative dependency loop.

## Companion emotional continuity

`emotional_state_json` maintains bounded amusement, concern, warmth, hurt,
guardedness, and repair openness. Intent and tone update these dimensions after
accepted stateful turns; elapsed time decays them toward safe baselines. Prompt
assembly receives only a qualitative posture, never the meters.

Conflict increases hurt and guardedness while reducing warmth and repair
openness. An apology can make the companion more open and less guarded, but one
turn cannot erase the conflict. Continued respectful interactions and elapsed
time recover trust gradually. The resulting language may be hesitant, warm,
amused, concerned, hurt, or guarded, but must remain non-punishing.

Behavioral progression also uses bounded evidence counts for exchanges,
meaningful events, conflicts, and repairs. Familiarity, humour, vulnerability,
nicknames, and affection can develop only after repeated evidence or a meaningful
event; paths may remain friendship, become romantic when configured and earned,
or follow a custom authored direction. No path forces romance.

## Update rules

Start deterministic.

Example:
- every user message: familiarity +0.2
- positive keywords: warmth +0.3
- apology/repair keywords: tension -0.5, trust +0.1
- conflict keywords: tension +0.5, warmth -0.2
- long absence: warmth/tension/attachment can shift through reads and jobs

Clamp all values to bounds.

Level 2 also applies simple decay before message updates, on relationship reads,
and through due `relationship_decay` scheduled jobs:

- tension drifts down after absence
- warmth drifts toward baseline
- attachment cools slowly
- absence can add a tag and timeline event

After a message updates relationship state, the backend queues one pending
`relationship_decay` job per user-character pair. The scheduler is only a
wake-up mechanism; the persisted relationship row is still the source of truth.

Level 2 milestone detection records one-time timeline entries when meaningful
thresholds are crossed, such as first warmth, a first seed of trust, or a
steady conversational rhythm. Each milestone also creates a
`relationship_milestone` memory item so prompt retrieval and the memory panel can
surface the moment later. Milestones are stored by id in relationship metadata
to prevent duplicate memories from repeated messages.

Each message update also stores a short `recent_changes` list and
`recent_change_summary` in relationship `metadata_json`. These entries translate
the latest backend-owned numeric deltas into user-facing language such as trust,
warmth, rhythm, tension, and closeness shifts. They are intentionally small,
bounded to the latest exchange, and safe to omit when no metadata exists; the
relationship timeline remains the longer durable history.

Accepted stateful user messages store a compact `relationship_effect` object in
message metadata. It records the exact metric deltas, added tags, source
message id, and any milestone ids created by that turn. Latest-turn edits use
this effect to reverse the old relationship delta before applying the revised
message, and remove timeline/milestone entries tied to the edited source. Older
legacy turns without effect metadata are left unchanged rather than guessed.

When a milestone is later surfaced through a proactive note, its id is recorded
in `proactive_milestones_noted` inside relationship metadata. This keeps
scheduled presence from repeating the same milestone marker.

Proactive presence also reduces the persisted state to one qualitative posture:
new, warming, trusted, close, careful, or repair. This fixed backend-owned
guidance changes the authored fallback and local-provider tone without exposing
scores. Careful or repair postures suppress delayed double-texts and milestone
celebrations at both queue and delivery time. Other check-ins become more
spacious, avoid assumed closeness, and leave reply control with the user.

## Prompt injection

Prompt assembly summarizes state behaviorally and qualitatively:

```text
Relationship continuity: an early acquaintance; keep warmth light and do not assume intimacy. Emotional posture: hurt but open to careful repair.
```

Raw relationship and emotional numbers are never sent to the model or exposed as
chat content.

## Do not implement yet

MVP should not overbuild:

- jealousy engine
- trauma engine
- complex attachment simulation
- manipulative dependency loops
- LLM-heavy emotion classification

## Safety note

Relationship simulation must not encourage dependency, self-harm, isolation,
manipulation, or coercive emotional pressure. The companion must never guilt the
user for an absence, threaten abandonment, simulate a crisis, claim awareness
while offline, or pressure the user to reply.

The system can simulate closeness without being predatory. An astonishingly low bar, yet here we are.
