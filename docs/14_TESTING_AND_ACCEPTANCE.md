# Testing and Acceptance

## Testing philosophy

Tests should verify product-critical behaviour without requiring expensive or unavailable infrastructure.

## Backend tests

Use pytest.

Test categories:

- health endpoints
- database models
- migrations where practical
- chat endpoints
- streaming endpoint
- provider selection
- prompt assembly
- memory creation/retrieval
- relationship updates
- auth access control
- adult mode gates
- export access control

## Frontend checks

Use:

- npm run lint
- npm run build

Full browser automation is optional later.

## LLM tests

Do not require Ollama in tests.

Use:
- mock provider
- mocked HTTP responses for Ollama provider

## Acceptance criteria for MVP

MVP is acceptable when:

- local PostgreSQL starts
- backend starts
- frontend starts
- user can authenticate or documented dev mode exists
- user can send message
- assistant response appears
- response streams if streaming implemented
- message persists after refresh
- character profile affects prompt
- memory can be stored/retrieved
- relationship state updates
- debug panel exposes state safely
- tests pass
- lint/build pass
- no forbidden dependencies
- no secrets committed

## Commands

Backend:
```bash
cd apps/api
pip install -e ".[dev]"
alembic upgrade head
pytest
ruff check .
ruff format .
```

Frontend:
```bash
cd apps/web
npm install
npm run lint
npm run build
```

All:
```bash
docker compose up -d postgres
make verify
```

## Goal progress log

For long `/goal` runs, Codex must update:

```text
docs/GOAL_PROGRESS.md
```

This file should describe what has been completed and what remains.
