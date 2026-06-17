# Background Jobs

## Purpose

Background jobs make the app feel alive without slowing live chat.

Use them for:
- memory extraction
- relationship decay
- proactive check-ins
- scheduled maintenance
- future episodic summaries

## Architecture

APScheduler wakes periodically.
PostgreSQL owns job state.

Never rely on in-memory scheduler state as the source of truth.

## scheduled_jobs lifecycle

Statuses:
- pending
- running
- done
- failed
- cancelled

Flow:

1. create pending job
2. worker claims due job
3. worker sets status running and lock fields
4. worker executes
5. worker marks done or failed

## Claiming jobs

Prefer PostgreSQL row locking:

```sql
SELECT ... FOR UPDATE SKIP LOCKED
```

This prevents duplicate work when there are multiple workers later.

## MVP job types

### maintenance_noop

A harmless test job.

### memory_extract

Extract memories from recent messages.

### proactive_inactivity_check

Check whether a conversation has been inactive long enough for a queued message.

### proactive_message_create

Create a queued assistant message.

Level 2 proactive hooks also create PostgreSQL-backed pending jobs for:

- proactive_morning_check
- proactive_goodnight_check
- proactive_thinking_of_you
- proactive_milestone_check
- proactive_unresolved_thread_nudge

These are safe queued records by default. The scheduler remains optional and disabled in tests.

## Scheduler config

Use env:

```text
ENABLE_SCHEDULER=false
```

Default false in tests.

## Anti-spam rules

Proactive jobs must not create repeated messages every tick.

Use:
- metadata_json
- last proactive timestamp
- job statuses
- per-conversation cooldown

## Testing

Tests should cover:
- create job
- claim due job
- mark done
- mark failed
- duplicate prevention

Tests must not start infinite background loops.
