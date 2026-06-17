# Prompt Assembly

## Purpose

Prompt assembly converts database state into a compact instruction packet for the LLM.

The prompt service must be centralized and unit-tested.

## Rule

The backend decides what matters. The LLM does not rummage through the database like a raccoon in a filing cabinet.

## Prompt sections

### 1. System role

Define the assistant as a fictional character in Eidolon.

### 2. Safety boundaries

Always include structural hard boundaries:

- no minors or ambiguous age in sexual contexts
- no coercion/exploitation/abuse
- no illegal sexual content
- no real-world harm instructions
- respect SFW/adult mode gates

### 3. Character profile

Include:

- name
- age if explicit
- personality_core
- speech_style
- description
- boundaries
- adult_mode_allowed only as structural context

### 4. Relationship state

Include numeric state in compact prose.

Example:
```text
Relationship state: familiarity 12/100, trust 4/100, warmth 8/100, tension 0/100.
```

### 5. Memories

Include only retrieved relevant memories.

Each memory should include:
- content
- type
- confidence

Example:
```text
Relevant memories:
- [preference, confidence 0.8] User likes quiet late-night conversations.
```

### 6. Recent messages

Include a bounded recent history window.

### 7. Current message

The latest user message.

### 8. Response style instruction

Keep concise unless context calls for detail. Match character style. Do not claim false memories.

## Prompt rules

- Keep prompts compact.
- Never include secrets.
- Never include password/token data.
- Do not include every memory.
- Do not include every message.
- Do not inject explicit adult examples.
- Do not let adult mode override hard boundaries.
- If model refuses or errors, return a safe readable fallback.

## Prompt versioning

Prompt assembly should expose a prompt_version string for debugging.

Recommended initial value:

```text
persona_memory_relationship_v1
```

## Testing prompt assembly

Tests should verify:

- character fields are included
- relationship state is included
- selected memories are included
- unrelated memories are omitted
- safety boundaries are included
- secrets are not included
- explicit sample content is not required
