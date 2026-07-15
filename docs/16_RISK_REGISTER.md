# Risk Register

## Risk: free-tier instability

Cloudflare, Google Cloud, Supabase, Groq, and GitHub free tiers may change,
throttle, reclaim, or limit resources.

Mitigation:
- design as zero-cost personal MVP, not guaranteed free-at-scale platform
- keep deployment portable
- backup data

## Risk: managed-service limits or outage

Groq, Cloud Run, or Supabase may throttle, pause, exhaust quota, or become
temporarily unavailable.

Mitigation:
- preserve the provider abstraction and portable PostgreSQL schema
- use bounded retries and readable failure states
- keep prompts compact and stream responses
- cap Cloud Run instances and SQLAlchemy pool connections
- back up user data and monitor `/ready`

## Risk: Codex overbuilds

Goal Mode may add unnecessary services.

Mitigation:
- AGENTS.md forbids specific dependencies
- docs define exact stack
- validation commands
- progress log

## Risk: memory pollution

System may store too many bad memories.

Mitigation:
- conservative extraction
- memory viewer/editor
- confidence score
- edit/delete/clear/forget controls
- do not store every message

## Risk: unsafe adult mode

Adult content support can become unsafe if ungated.

Mitigation:
- structural gates
- explicit age requirements
- no minors/ambiguous age
- hard boundaries in prompt
- no explicit tests/fixtures

## Risk: prompt bloat

Large prompts slow inference.

Mitigation:
- bounded recent history
- top-k memories
- compact relationship summary
- prompt versioning

## Risk: multi-user leakage

Data isolation bugs could expose data.

Mitigation:
- user ownership checks
- access control tests
- debug endpoints scoped to current user

## Risk: scheduler spam

Proactive jobs may create repeated messages.

Mitigation:
- cooldowns
- metadata markers
- job status checks
- tests for duplicate prevention

## Risk: repository becomes unreviewable

Long goal runs can create huge diffs.

Mitigation:
- checkpoint progress log
- small commits if Codex supports them
- clear stopping condition
- review with /review afterward
