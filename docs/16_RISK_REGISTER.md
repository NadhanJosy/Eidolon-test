# Risk Register

## Risk: free-tier instability

Oracle/Vercel/GitHub free tiers may change, throttle, reclaim, or limit resources.

Mitigation:
- design as zero-cost personal MVP, not guaranteed free-at-scale platform
- keep deployment portable
- backup data

## Risk: CPU inference too slow

Ollama on ARM CPU may produce slow responses.

Mitigation:
- stream responses
- keep prompts compact
- use mock/small model for background jobs
- limit concurrency
- accept slower texting-like cadence

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
- memory viewer
- confidence score
- delete/edit later
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
