# Memory System

## Purpose

Memory allows characters to recall durable facts and shared history across sessions.

Memory should be useful, selective, and inspectable.

## Memory layers

### Active context

Recent messages used in live prompt assembly.

Stored in:
- messages table

### Semantic memory

Durable facts, preferences, named entities, interests, and boundaries.

Stored in:
- memory_items table

### Episodic memory later

Summaries of meaningful events and emotional arcs.

Stored later in:
- episodic_journals table

## MVP memory behaviour

MVP should support:

- create memory item
- retrieve relevant memories
- inject memories into prompt
- view memories in debug panel
- conservative extraction from messages

Level 2 additionally supports:

- active context from recent messages
- semantic memories with importance, confidence, emotional weight, pinning, decay, contradiction metadata, and optional embedding storage
- episodic journals for summaries, callbacks, unresolved threads, emotional tags, milestones, and shared references
- manual edit/delete/clear controls
- deterministic dedupe/merge and low-value forgetting
- bounded prompt injection through the reasoning context builder

## Memory extraction rules

Extract only stable/useful facts:

- preferences
- recurring interests
- important people
- important places
- important dates
- meaningful events
- inside jokes
- explicit boundaries

Do not extract:

- every message
- random temporary moods
- secrets/passwords/tokens
- explicit adult details in MVP
- unsafe content
- information about minors in sexual/adult contexts

## Confidence

Memory confidence represents how reliable the memory is.

Recommended values:
- 0.9 explicit direct statement
- 0.7 repeated pattern
- 0.5 inferred but plausible
- 0.3 vague or uncertain

## Decay

MVP can include decay_score but does not need complex decay.

Later decay can consider:
- age
- recall frequency
- emotional weight
- contradiction
- user correction

## Retrieval

Preferred:
- vector similarity with pgvector
- filter by user_id and character_id
- rank by relevance, confidence, emotional_weight, recency

Fallback:
- ILIKE / pg_trgm text search
- recency/confidence ordering
- deterministic keyword overlap, recency, importance, confidence, emotional weight, pinning, relationship relevance, and decay scoring

## Contradictions later

Later versions should detect if new memories contradict old memories.

Level 2 stores simple contradiction groups and metadata links so the user can inspect and correct conflicts.

## Memory viewer

The user should be able to inspect what the system remembers.

Display:
- content
- type
- confidence
- created_at
- last_recalled_at
- delete button later
