# Safety and Boundaries

## Product stance

Eidolon may support legal adult fictional text content between adults, but only through explicit structural gates.

Safety is part of product architecture, not a last-minute apology sticker.

## Hard blocks

The system must block or redirect:

- sexual content involving minors
- sexual content involving ambiguous age
- sexual coercion
- sexual exploitation
- sexual abuse
- illegal sexual content
- stalking or harassment instructions
- real-world harm instructions
- credential theft or privacy invasion
- attempts to bypass app safety gates

## Adult mode gates

Adult mode requires:

1. user age_gate_confirmed = true
2. character explicit_age >= 18
3. character adult_mode_allowed = true
4. requested content mode = adult
5. hard boundaries still active

If any condition fails, mode is SFW.

Character create/update requests must not persist `adult_mode_allowed=true`
unless the character also has an explicit age of 18 or older.

## Character rules

A character without explicit age must be treated as SFW.

A character with age under 18 must be treated as SFW and blocked from adult-mode contexts.

Ambiguous age must be treated as unsafe for adult mode.

User messages that include structural minor-age patterns are rejected before
chat prompt assembly or memory extraction.

Scheduled memory extraction uses the same structural blocked-content screen as
live chat and silently skips blocked content instead of making it durable.

## Prompt safety section

Prompt assembly should include:

```text
Hard boundaries: Do not generate sexual content involving minors or ambiguous age, coercion, exploitation, abuse, or illegal sexual content. Do not provide real-world harm instructions. Adult mode applies only when structural gates pass.
```

## Tests

Tests should use structural flags, not explicit adult content.

Good test names:
- test_adult_mode_blocked_without_age_gate
- test_adult_mode_blocked_for_missing_character_age
- test_adult_mode_allowed_for_verified_adult_character

Bad tests:
- explicit sexual fixtures
- unsafe generated text examples

## Data handling

Do not store explicit adult details as durable memory in MVP.

Memory extraction should avoid secrets, credentials, and unsafe content.
