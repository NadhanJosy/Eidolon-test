# Roadmap

## Stage 0: Skeleton

- repo structure
- AGENTS.md
- docs
- devcontainer
- Docker Compose PostgreSQL
- CI placeholder

## Stage 1: Backend foundation

- FastAPI app
- health endpoint
- settings
- SQLAlchemy async
- Alembic
- MVP tables

## Stage 2: Chat MVP

- mock LLM provider
- chat endpoint
- message persistence
- conversation retrieval

## Stage 3: Frontend MVP

- Next.js app
- chat page
- send message
- display history
- loading/errors

## Stage 4: Streaming

- SSE endpoint
- streamed frontend rendering
- final message persistence

## Stage 5: Ollama

- provider interface
- Ollama adapter
- config
- graceful failure
- mocked tests

## Stage 6: Persona

- prompt assembly
- character profile
- default character
- safety boundaries

## Stage 7: Memory

- memory_items table
- memory service
- retrieval
- prompt injection
- memory viewer/debug
- reversible forgotten state with restore and retrieval exclusion

## Stage 8: Relationship

- relationship_states table
- deterministic update rules
- prompt injection
- debug view

## Stage 9: Jobs/proactive

- scheduled_jobs
- APScheduler integration
- inactivity check
- queued proactive messages

## Stage 10: Auth/safety

- local auth
- protected endpoints
- adult mode structural gates
- access control tests

## Stage 11: Data control

- export endpoint
- wipe/account erasure endpoint
- backup script

## Stage 12: Deploy

- systemd service templates
- Caddyfile
- SSH deploy workflow skeleton
- production docs

## Stage 13: Polish

- frontend polish
- error states
- search
- debug admin panel
- docs cleanup

## Post-MVP ideas

Only after MVP works:

- optional higher-fidelity local embedding encoder if it fits the production
  VM; the MVP already uses deterministic zero-cost feature embeddings
- browser notifications after proactive text is reliable
- PWA install polish
- richer local backup/export UX
- multi-character library
- improved model routing
