# API Contract

## General conventions

- JSON API
- Auth required for all user data endpoints after auth is implemented
- Error responses should be readable and not leak stack traces
- Use UUID strings in JSON
- Timestamps should be ISO 8601

## Health

GET /health

Response:
```json
{
  "status": "ok",
  "service": "eidolon-api"
}
```

GET /health/db

Response:
```json
{
  "status": "ok"
}
```

GET /health/llm

Response should not fail app if Ollama unavailable. It may return degraded.

## Auth

POST /auth/register

Request:
```json
{
  "email": "user@example.com",
  "password": "password",
  "display_name": "Nadhan"
}
```

Response:
```json
{
  "user": {
    "id": "uuid",
    "email": "user@example.com",
    "display_name": "Nadhan"
  }
}
```

POST /auth/login

GET /auth/me

POST /auth/logout

## Characters

GET /characters

POST /characters

GET /characters/{character_id}

PATCH /characters/{character_id}

## Conversations

GET /conversations

POST /conversations

GET /conversations/{conversation_id}/messages

GET /conversations/{conversation_id}/search?q=term&limit=20

PATCH /conversations/{conversation_id}/messages/{message_id}

DELETE /conversations/{conversation_id}/messages

DELETE /conversations/{conversation_id}

## Chat

POST /chat/messages

Request:
```json
{
  "conversation_id": "uuid",
  "content": "Hello"
}
```

Response:
```json
{
  "user_message": {
    "id": "uuid",
    "role": "user",
    "content": "Hello",
    "created_at": "timestamp"
  },
  "assistant_message": {
    "id": "uuid",
    "role": "assistant",
    "content": "Mock response",
    "created_at": "timestamp"
  }
}
```

POST /chat/stream

Use SSE or streaming response.

Events:
- message_start
- token
- message_done
- error

POST /chat/reroll

Creates an alternate assistant message for the previous user turn and records `reroll_of` metadata.

## Memory

GET /characters/{character_id}/memories

POST /characters/{character_id}/memories

GET /characters/{character_id}/memories/search?q=term

PATCH /characters/{character_id}/memories/{memory_id}

DELETE /characters/{character_id}/memories/{memory_id}

DELETE /characters/{character_id}/memories

POST /characters/{character_id}/memories/forget

## Episodic Journals

GET /characters/{character_id}/journals

POST /characters/{character_id}/journals

## Relationship

GET /characters/{character_id}/relationship

Relationship response includes numeric state, mood, conflict state, repair-needed flag, tags, and timeline metadata.

## Adult Gate Status

GET /characters/{character_id}/adult-status

Returns requested/effective mode, gate allowance, blocked reasons, and content intensity.

## Debug

GET /debug/character/{character_id}

GET /debug/conversation/{conversation_id}

GET /debug/jobs

Debug endpoints must be authenticated and scoped to current user.

## Export

GET /account/export

Response should exclude:
- password_hash
- token hashes
- secrets
- environment variables
