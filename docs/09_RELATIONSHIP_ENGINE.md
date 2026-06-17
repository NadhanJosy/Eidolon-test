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

## Update rules v1

Start deterministic.

Example:
- every user message: familiarity +0.2
- positive keywords: warmth +0.3
- apology/repair keywords: tension -0.5, trust +0.1
- conflict keywords: tension +0.5, warmth -0.2
- long absence later: warmth/tension can shift via jobs

Clamp all values to bounds.

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
