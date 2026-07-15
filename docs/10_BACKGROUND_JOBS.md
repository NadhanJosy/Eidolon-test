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

Extract memories from recent user messages through the same deterministic
Memory v2 extractor used by chat completion. Jobs may provide a
`conversation_id` to scan recent user messages or both `conversation_id` and
`message_id` to process one specific user message. Existing dedupe/merge,
unsafe-term filtering, contradiction metadata, and confidence rules still
apply. Missing or non-user messages fail the job with safe bounded text.

Completed memory extraction jobs record:
- `messages_checked`
- `extracted_count`
- `skipped_count`
- `accepted_types`
- `skip_reasons`

Skip reasons are bounded labels such as `no_trigger`, `unsafe_term`,
`blocked_content`, or `disabled_by_preferences`; rejected message text is not
copied into job metadata.

### relationship_decay

Apply persisted relationship drift for a user-character pair after absence.
Chat updates queue one pending relationship-decay job per pair. Relationship
reads also apply decay so the visible state and prompt context do not wait for a
new user message.

### proactive_inactivity_check

Check whether a conversation has been inactive long enough for a queued message.
Creates a SFW quiet check-in when cooldown rules allow it.

### proactive_message_create

Create a manual queued assistant message.

Level 2 proactive hooks also create PostgreSQL-backed pending jobs for:

- proactive_morning_check
- proactive_goodnight_check
- proactive_thinking_of_you
- proactive_milestone_check
- proactive_unresolved_thread_nudge
- proactive_delayed_double_text

These are safe queued records. When due, the scheduler creates a
type-aware SFW assistant message with `proactive_type` and `proactive_label`
metadata. A per-conversation cooldown prevents different proactive variants
from stacking into spam. If the user has already returned with a newer message
after the job was queued, the scheduler marks the proactive job skipped instead
of sending a stale away-note. The scheduler remains optional and disabled in
tests.

After all delivery guards pass, the scheduler asks the configured text
provider for one bounded SFW note. The prompt contains only the character name,
a screened speech-style fragment, the proactive label, and an already-safe
variant/context anchor plus a fixed qualitative relationship posture. It does
not include raw chat history, adult text, private turns, memory metadata,
relationship scores, or debug state. Generated text is accepted only when it is
a non-empty string of at most 600 characters and passes SFW-label, structural
safety, credential, and hidden-prompt screens.

Provider unavailability, unexpected provider failures, malformed responses,
oversized output, or rejected content use the deterministic type-aware SFW
anchor instead of failing the job. Message and job metadata record only safe
provenance: `generation_source` (`llm` or `fallback`) and a bounded
`generation_reason` for fallback. Internal exception text and rejected output
are not persisted.

Relationship state is re-read before queueing and again before delivery. New,
warming, trusted, and close postures tune the note without exposing numbers.
Careful or repair postures suppress delayed double-texts and milestone notes;
remaining check-ins use spacious authored copy and do not pull unresolved-thread
details into the prompt. This recheck prevents a note queued during warmth from
becoming tone-deaf after later tension. A suppressed due row completes with
`skipped_by_relationship_state`, a bounded `relationship_careful` or
`relationship_repair` reason, and no assistant message.

`proactive_unresolved_thread_nudge` is context-aware. Chat completion only
queues it when the latest journal contains an intentional follow-up/open-thread
cue, and the worker rechecks that journal context before sending. Ordinary user
questions that already received a companion reply do not schedule open-thread
nudges.

Morning and goodnight jobs are queued for the next configured local wall-clock
target with at least four hours of lead time. Their delivery window remains open
for three hours so a temporarily sleeping VM can recover without producing a
midday greeting. If that window has passed, the row returns to `pending` for the
next local target.

Other automatically queued presence jobs are shifted out of the configured
quiet period at creation. The worker checks the quiet period again when a
time-aware row becomes due, covering preference changes and delayed runtime
wake-up. Deferral clears claim locks and leaves `retry_count` unchanged because
waiting for local time is not a failure. Matching quiet start and end times
disable the quiet period.

The character profile can set `proactive_preferences.cooldown_hours` from 1 to
168 hours. New and rescheduled proactive jobs copy that value into their
payload, and the worker uses it as the per-conversation cooldown before writing
another presence note. Legacy rows without the field keep the 24-hour default.

Private turns create no new proactive jobs. A queued proactive job also skips
when the newest accepted turn is private, and delayed double-text logic cannot
use a private assistant reply as its trigger. Batch memory jobs exclude private
messages even after the thread is standard again.

Because proactive output is stored as a normal assistant message, it increments
the conversation's derived unread count. The visible web client refreshes
conversation summaries only while the tab is visible and loads an unread active
thread without marking any concurrently arriving note it has not rendered.

`proactive_unresolved_thread_nudge` can use the latest safe episodic journal
callback or unresolved-thread excerpt for the conversation. The excerpt is
bounded, screened for unsafe/secret terms, and omitted when only adult-mode or
otherwise unsafe details are available.

`proactive_delayed_double_text` is stricter than normal check-ins: it only
creates a delayed follow-up when the latest thread message is a normal assistant
reply and the user has not answered yet. It skips if the latest message is from
the user, is private, or is already proactive.

`proactive_milestone_check` is relationship-state-aware. It is only queued when
the relationship timeline contains an unnoted milestone, writes a bounded SFW
note using that milestone summary, and records the milestone id in relationship
metadata so the same marker is not repeated.

## Scheduler config

Use env:

```text
ENABLE_SCHEDULER=true
SCHEDULER_INTERVAL_SECONDS=60
SCHEDULER_JOB_LIMIT=10
SCHEDULER_MAX_RETRIES=3
SCHEDULER_RETRY_BASE_SECONDS=30
PROACTIVE_COOLDOWN_HOURS=24
```

The personal development runtime defaults to enabled. Tests explicitly set
`ENABLE_SCHEDULER=false`.

When `ENABLE_SCHEDULER=true`, FastAPI starts an APScheduler interval job that
claims due `scheduled_jobs` rows, processes them, and writes `done` or `failed`
state back to PostgreSQL. The scheduler is only a wake-up mechanism; job state,
locks, retry counts, and safe error text live in the database.

Unexpected execution failures return to `pending` with exponential backoff
starting at `SCHEDULER_RETRY_BASE_SECONDS`, capped at 24 hours and
`SCHEDULER_MAX_RETRIES`. Internal exception text is not persisted. Invalid
payloads and unsupported job types fail immediately because repeating them
cannot repair the input. Terminal and retry transitions clear `locked_at` and
`locked_by`.

Every background tick first takes a PostgreSQL transaction-scoped advisory
lock. `SKIP LOCKED` still protects individual rows, while the advisory lock
prevents overlapping batches across API processes. Tests hold the matching
session lock for the suite so an independently running development API cannot
claim fixture jobs; direct service-level job processing remains available to
deterministic tests.

Authenticated Debug shows whether the scheduler is configured, whether the
lifespan-owned instance is actually running, safe job outcomes, retry number,
next due time, and bounded `last_error`. This state remains absent from
companion-facing screens.

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
- transient retry and terminal retry cap
- local-time scheduling, DST conversion, quiet-hour deferral, and preference
  rescheduling without retry consumption
- scheduler lifespan startup/shutdown
- cross-process tick exclusion and live-server test isolation
- completed/retried/failed lock cleanup
- duplicate prevention
- memory extract job processing
- relationship decay job processing

Tests must not start infinite background loops.
