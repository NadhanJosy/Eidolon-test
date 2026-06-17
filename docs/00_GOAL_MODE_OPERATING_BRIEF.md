# Goal Mode Operating Brief

This repository is intentionally prepared for Codex Goal Mode.

## How Goal Mode should work here

Codex should work toward one durable objective: produce a working MVP of Eidolon within the strict constraints in this repository.

Codex must:

1. Read this repository's docs first.
2. Build in ordered checkpoints.
3. Keep changes small enough to review.
4. Run validation commands after each major checkpoint.
5. Maintain `docs/GOAL_PROGRESS.md` while working.
6. Stop when the verifiable end state is reached, or when blocked.

## The durable objective

Build a private, text-only AI companion MVP that works locally in Codespaces with a mock LLM and is structured to run on Oracle Cloud Always Free with Ollama later.

## Stopping condition

Stop when the MVP can be run locally and the user can:

- start PostgreSQL with Docker Compose
- start the FastAPI backend
- start the Next.js frontend
- register/login or use a documented dev user
- send a chat message
- receive a streamed assistant response
- persist messages in PostgreSQL
- view basic character info
- store/retrieve simple memories
- update relationship state after messages
- inspect debug state
- run backend tests and frontend lint/build successfully

## Work checkpoints

Codex should proceed in this exact order unless a blocker requires a safe adjustment:

1. Repo scaffolding sanity check
2. Backend health endpoint
3. PostgreSQL, SQLAlchemy, Alembic, models
4. Mock chat endpoint
5. Frontend chat shell
6. SSE streaming
7. Ollama provider adapter
8. Persona prompt assembly
9. Memory v1
10. Relationship state v1
11. Background jobs foundation
12. Proactive messages v1
13. Auth v1
14. Adult mode structural gates
15. Debug/admin panel
16. Export/backup basics
17. Deployment templates
18. Production hardening
19. MVP polish

## Checkpoint reporting

After each checkpoint, update `docs/GOAL_PROGRESS.md` with:

- checkpoint name
- files changed
- commands run
- tests/checks passed
- known limitations
- next checkpoint

## Autonomy rules

Codex may make reasonable local implementation decisions if they preserve constraints.

Codex must not:

- switch stack
- add paid services
- add forbidden dependencies
- build multimedia features
- skip tests without saying why
- hide known failures
- invent secrets or cloud credentials

## If the task becomes too large

Codex should stop after producing a stable MVP slice rather than continuing into messy half-complete features.

A smaller working MVP beats a huge broken shrine to ambition.
