# Architecture

## High-level diagram

```text
Browser / PWA
  ↓
Next.js frontend
  ↓ HTTP/SSE
FastAPI backend
  ↓
PostgreSQL + pgvector
  ↓
Ollama or mock LLM provider
```

## Main architectural rule

The backend owns state. The LLM produces prose.

This prevents personality drift, memory hallucination, and provider lock-in.

## Frontend responsibilities

The frontend handles:

- chat layout
- input box
- message list
- streaming display
- login/register screens
- character panel
- memory/debug views
- settings toggles

The frontend must not handle:

- memory selection
- relationship calculations
- model calls directly
- safety gates
- heavy rendering
- local ML

## Backend responsibilities

The backend handles:

- auth
- database access
- prompt assembly
- LLM provider routing
- message persistence
- memory storage/retrieval
- relationship state updates
- scheduled jobs
- adult mode gates
- debug endpoints
- data export/wipe

## Database responsibilities

PostgreSQL stores all durable state.

Core tables:
- users
- characters
- conversations
- messages
- memory_items
- relationship_states
- scheduled_jobs
- refresh_tokens

PostgreSQL extensions:
- pgvector for embeddings
- pg_trgm for fuzzy search

## LLM provider abstraction

Provider interface should support:

- generate(prompt) -> text
- stream(prompt) -> async chunks

Providers:

1. Mock provider
   - deterministic
   - used by tests
   - no external dependency

2. Ollama provider
   - HTTP client to local Ollama server
   - configurable base URL and model
   - graceful failure when unavailable

Tests must not require Ollama.

## Chat flow

1. User submits message.
2. Backend authenticates user.
3. Backend validates conversation ownership.
4. Backend stores user message.
5. Backend loads character.
6. Backend loads relationship state.
7. Backend retrieves relevant memories.
8. Backend assembles prompt.
9. Backend calls LLM provider.
10. Backend streams response to frontend.
11. Backend stores assistant message.
12. Backend updates relationship state.
13. Backend schedules memory extraction/proactive jobs as needed.

## Prompt assembly

Prompt assembly must be centralized and testable.

Prompt sections:

1. System identity and behaviour rules
2. Safety boundaries
3. Character profile
4. Relationship state
5. Relevant memories
6. Recent conversation history
7. Current user message
8. Response instructions

## Background jobs

APScheduler may wake the worker, but PostgreSQL is the source of truth.

`scheduled_jobs` table supports:
- job_type
- run_at
- status
- locked_at
- locked_by
- retry_count
- payload_json

Job claiming should use database locking where practical.

## Scaling path

MVP:
- one VM
- one backend process
- one PostgreSQL
- one Ollama

Later:
- split workers
- split inference host
- managed database
- queue system
- model router
- paid inference if user demand exists

Do not build later-stage infrastructure into MVP.
