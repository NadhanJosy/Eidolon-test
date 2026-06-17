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

## Memory

GET /characters/{character_id}/memories

POST /characters/{character_id}/memories

GET /characters/{character_id}/memories/search?q=term

## Relationship

GET /characters/{character_id}/relationship

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
