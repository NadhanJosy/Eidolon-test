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

These fields are deterministic backend state. They should explain tone and continuity without turning the system into a manipulative dependency loop.

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

## Prompt injection

Prompt assembly should summarize state compactly:

```text
Relationship state: familiarity is low, warmth is mildly positive, tension is low, trust is new but growing.
```

Use qualitative labels instead of raw numbers if better for model behaviour.

## Do not implement yet

MVP should not overbuild:

- jealousy engine
- trauma engine
- complex attachment simulation
- manipulative dependency loops
- LLM-heavy emotion classification

## Safety note

Relationship simulation must not encourage dependency, self-harm, isolation, manipulation, or coercive emotional pressure.

The system can simulate closeness without being predatory. An astonishingly low bar, yet here we are.
