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

### Episodic memory

Summaries of meaningful events and emotional arcs.

Stored in:
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

Level 2 stores `decay_score`, `last_recalled_at`, `importance`, `confidence`,
`emotional_weight`, and `pinned`. Retrieval and forgetting use these fields to
keep durable memory useful without treating every old note as equally relevant.

Decay considers:
- age
- recall frequency
- emotional weight
- contradiction
- user correction

## Background extraction

The `memory_extract` scheduled job processes recent user messages for a
conversation, or one specific user message when `message_id` is provided. It
uses the same extraction, unsafe-term filtering, dedupe/merge, contradiction,
and scoring logic as inline chat memory extraction.

## Retrieval

Implemented:
- filter by user_id and character_id
- deterministic keyword overlap
- recency, importance, confidence, emotional weight, pinning, relationship relevance, and decay scoring
- pg_trgm/ILIKE-friendly text search endpoints

Prepared for future model-backed retrieval:
- nullable pgvector embedding storage
- vector similarity ranking once a zero-cost embedding path is chosen

## Contradictions

Level 2 stores simple contradiction groups and metadata links so the user can
inspect and correct conflicts.

## Memory viewer

The user should be able to inspect what the system remembers.

Display:
- content
- type
- confidence
- importance
- pinned state
- contradiction metadata
- created_at
- last_recalled_at
- edit/delete/clear controls
