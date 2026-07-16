# Roadmap

## Current baseline

The MVP is implemented and deployed with authentication, multi-companion and
multi-thread chat, SSE streaming, persona prompts, semantic/episodic memory,
evidence-grounded witnessed continuity with claim correction and turn receipts,
first-class living plans/promises/follow-ups, relationship continuity,
PostgreSQL-backed jobs, earned proactive notes, separately scoped adult
continuity, privacy gates, debug visibility, export/erasure, migrations, CI, and
managed production builds.

The roadmap now prioritizes reliability and operational confidence over adding
more surface area.

## Near-term priorities

1. Production safeguards
   - protect `main` with pull requests and required CI checks
   - verify Cloudflare and Cloud Build branch/path filters
   - confirm budget/quota notifications and bounded instance settings
   - document the actual production service/project ownership outside source
     without committing identifiers or credentials

2. Backup and recovery
   - establish an encrypted production database backup routine
   - perform and record a restore drill against a disposable database
   - define rollback steps for an application revision paired with an additive
     migration

3. Release confidence
   - add a small deterministic production smoke checklist
   - verify deployed commit/revision visibility without exposing internals
   - decide whether local testing is sufficient or a genuinely isolated staging
     API/database is worth its operational and cost overhead

4. Product polish
   - add deterministic browser smoke coverage for authenticated mobile and
     desktop journeys, responsive layout, keyboard focus, and scroll restoration
   - add visual-regression and screen-reader checks around the design system,
     onboarding dialog, chat composer, and destructive confirmations
   - build a consented SFW evaluation set for cognition precision/recall,
     correction accuracy, moment worthiness, and natural callback quality
   - tune prompt budgets and repetitive-response checks from real SFW evidence
   - tune living-thread extraction precision and closure language from real SFW
     usage evidence without widening automatic capture speculatively
   - review earned proactive timing, callback phrasing, and cooldown behaviour
     under Cloud Run wake-up limitations

## Later, only with evidence

- same-site custom frontend/API subdomains for more reliable refresh cookies
- path-filtered independent frontend/backend deployments
- replaceable higher-fidelity embeddings if deterministic retrieval proves
  insufficient and resource/cost limits are understood
- a dedicated worker or always-on host only if proactive delivery needs become
  stricter than Cloud Run catch-up behaviour
- alternate inference or PostgreSQL hosting through the existing interfaces
- browser notifications after consent, privacy, and proactive anti-spam behaviour
  are proven

## Explicitly deferred

- voice, audio, avatar, video, image, AR, or Live2D features
- native mobile apps
- fine-tuning
- social/community features
- distributed queues or Kubernetes
- manipulative attachment, jealousy, or engagement mechanics
- large dependency additions without a measured problem

## Roadmap rule

Do not mark work complete merely because code exists. A roadmap item is complete
only when its tests, migration/deployment implications, documentation, and safe
failure behaviour are verified.
