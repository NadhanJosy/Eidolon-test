# Operations

## Environments

| Environment | Frontend | API | Database | Provider |
| --- | --- | --- | --- | --- |
| Local/Codespaces | Next dev server | Uvicorn reload | Docker Compose PostgreSQL | mock by default |
| Production | Cloudflare Pages | Google Cloud Run | Supabase Session pooler | Groq |

The local environment exercises the same API, persistence, prompt, relationship,
memory, and SSE paths without requiring a live provider.

## Local setup

Requirements:

- Git
- Docker with Docker Compose
- Python 3.12+
- Node.js 22 and npm

Create local configuration only when it does not already exist:

```bash
test -f .env || cp .env.example .env
test -f apps/web/.env.local || cp apps/web/.env.example apps/web/.env.local
```

The examples select local PostgreSQL and the deterministic mock. Never commit
the created files.

Start and install:

```bash
docker compose up -d postgres
cd apps/api
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
alembic upgrade head
```

In another terminal:

```bash
cd apps/web
npm ci
```

Run the API:

```bash
cd apps/api
source .venv/bin/activate
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

Run the web app:

```bash
cd apps/web
npm run dev
```

Local endpoints:

- web: `http://localhost:3000`
- API docs: `http://localhost:8000/docs`
- liveness: `http://localhost:8000/health`
- readiness: `http://localhost:8000/ready`

Stop PostgreSQL with `docker compose down`. Do not use `-v` unless local database
deletion is intended.

## Validation

Start PostgreSQL first, then run the combined target:

```bash
docker compose up -d postgres
make verify
```

Equivalent backend checks:

```bash
cd apps/api
pip install -e ".[dev]"
alembic upgrade head
pytest -m "not live"
ruff check .
ruff format --check .
```

Equivalent frontend checks:

```bash
cd apps/web
npm ci
npm run lint
npm run typecheck
npm run build
```

Container check:

```bash
docker build -t eidolon-api:local-check ./apps/api
docker run --rm --network host --env-file .env -e PORT=8080 eidolon-api:local-check
```

The live Groq smoke test is opt-in and excluded from CI:

```bash
cd apps/api
RUN_GROQ_LIVE_TEST=1 pytest -q -m live tests/test_groq_live.py
```

Never enable it in routine automation or without an intentionally configured
provider key/quota.

## Git and release workflow

`main` is the production branch. Normal work should use a feature branch and a
pull request:

```bash
git switch main
git pull --ff-only
git switch -c feature/short-description
```

After implementation and validation:

```bash
git add <specific-files>
git diff --cached
git commit -m "Describe the change"
git push -u origin HEAD
```

The repository owner has given coding agents standing permission to perform this
completed-task commit and push flow. For every completed user task, the agent
must:

1. add one concise outcome/validation entry to `docs/GOAL_PROGRESS.md`,
2. confirm the working tree contains no unrelated user changes,
3. stage all task-owned modifications, additions, and deletions,
4. inspect `git diff --cached` and run `git diff --cached --check`,
5. commit with a terse task-level message,
6. push the current feature branch with upstream tracking,
7. open or update a pull request when repository access permits.

This standing permission does not authorize a direct push to `main`, merging a
pull request, changing cloud configuration, or manually deploying production.
Those actions require an explicit request. If authentication or an external
service blocks publication, preserve the local commit and report the exact
blocker.

Open a pull request, wait for the `Backend checks` and `Frontend checks`, review
the diff, and merge through GitHub. Protect `main` with required pull-request and
CI checks where repository settings permit.

GitHub Actions CI and hosting deploys are independent systems. The checked-in CI
workflow validates pull requests and `main`; Cloudflare and Cloud Build triggers
are configured outside this repository. Confirm their production branch,
include/ignore paths, and latest deployment in their dashboards.

### Preview warning

A Cloudflare branch preview contains a separate frontend build only. If
`NEXT_PUBLIC_API_BASE_URL` is the production Cloud Run URL, the preview uses the
production API and database. Exact credentialed CORS may also reject the preview
origin.

Use local full-stack testing for behaviour that mutates data unless a dedicated
staging backend and database exist. Do not add broad wildcard credentialed CORS
to make previews work.

## Production build roots

| Service | Root | Build/start | Output |
| --- | --- | --- | --- |
| Cloudflare Pages | `apps/web` | `npm run build` | `out` |
| Cloud Run | `apps/api` | `Dockerfile` | container port `8080` |

Cloud Run injects `PORT`. Do not define it as an application environment
variable. The container runs `alembic upgrade head` and then Uvicorn as the
non-root `eidolon` user.

## Cloud Run configuration

Required production settings:

| Variable | Requirement |
| --- | --- |
| `APP_ENV` | `production` |
| `DATABASE_URL` | Supabase Session pooler URL using PostgreSQL/asyncpg and TLS |
| `GROQ_API_KEY` | Secret binding; backend only |
| `JWT_SECRET` | Secret binding; random 32-4096 UTF-8 bytes |
| `LLM_PROVIDER` | `groq` in the current production profile |
| `GROQ_MODEL` | An enabled configured production model |
| `COGNITION_MODE` | `selective` by default; `off` or `all` only intentionally |
| `COGNITION_MAX_OUTPUT_TOKENS` | Bounded structured-output allowance, `128..2000` |
| `WEB_ORIGIN` | Exact HTTPS Cloudflare production origin |
| `CORS_ORIGINS` | Additional exact HTTPS origins only when required |
| `REFRESH_COOKIE_SECURE` | `true` |
| `REFRESH_COOKIE_SAMESITE` | `none` for default cross-site hosts |
| `ENABLE_DEBUG_ROUTES` | `false` unless temporarily and intentionally enabled |

Conservative pool settings are documented in `.env.example`. The maximum
potential application connections are approximately:

```text
(DATABASE_POOL_SIZE + DATABASE_MAX_OVERFLOW) * Cloud Run maximum instances
```

Keep that below the available database connection allowance.

`selective` cognition makes one additional bounded Groq request only after an
eligible reply has safely persisted. Provider failure cannot fail that reply and
falls back to deterministic post-processing. `all` materially increases calls;
do not enable it without checking quota/cost behavior. `off` retains the
deterministic path.

Use Secret Manager/Cloud Run secret bindings for database, provider, and JWT
values. When deploying a new image, preserve the service account, secret
bindings, environment variables, timeout, concurrency, max instances, ingress,
and authentication settings. Some `gcloud --set-*` flags replace the complete
existing set; inspect the command before running it.

## Cloudflare configuration

| Setting | Value |
| --- | --- |
| Framework | Next.js static export |
| Root | `apps/web` |
| Build command | `npm run build` |
| Output | `out` |
| Node | 22 |
| Public build variable | `NEXT_PUBLIC_API_BASE_URL=<Cloud Run HTTPS URL>` |

`NEXT_PUBLIC_API_BASE_URL` is intentionally public. Never create
`NEXT_PUBLIC_*` variables containing a database URL, provider key, JWT secret,
or credential.

Static security headers live in `apps/web/public/_headers`.

## Migrations

Cloud Run applies every pending migration during revision startup under a shared
PostgreSQL advisory lock. A failed migration prevents the new API revision from
becoming healthy.

For each schema change:

1. update the SQLAlchemy model,
2. add a reviewed Alembic revision,
3. upgrade a local database from the prior head,
4. run migration and endpoint tests,
5. verify a current backup before destructive changes,
6. keep the migration compatible with a brief overlap of old and new API
   revisions.

Advisory locking prevents concurrent migration races; it does not make a
destructive schema change backward-compatible.

## Scheduler behaviour

Job state and locks are durable, but APScheduler runs inside an active API
instance. Request-based Cloud Run CPU and scale-to-zero can delay ticks. Jobs
catch up when an instance is active.

Proactive presence uses `proactive_candidates` as the evidence/lifecycle source
of truth and one deduplicated `proactive_delivery` job as its execution
envelope. A worker reclaims a `running` row whose lock has been abandoned for 15
minutes, increments its retry count, and reruns the candidate under a row lock.
Generation and message delivery remain transactional, so restart recovery
cannot intentionally create a second note. Capped retries use exponential
backoff; exhaustion leaves both a failed job and a `failed` candidate lifecycle
event with safe reason codes. Expired, cancelled, dismissed, replied, or already
delivered candidates are no-ops if an old envelope wakes later.

Eligible chat responses also request best-effort immediate processing through a
durable `chat_postprocess` row. If immediate work is interrupted, the normal
scheduler retries it; the chat receipt remains pending and then becomes ready or
degraded without affecting the persisted reply.

Eligible post-chat work also ensures one `memory_maintenance` row due roughly a
day later per companion. The pass is deterministic and local: it consolidates
exact claims, backfills entity links, and applies retention-aware decay. It adds
no provider call and stores only reviewed/consolidated/faded counts in the job
payload. Scale-to-zero may delay it safely; the next active instance catches up.

Do not enable minimum instances or always-allocated CPU merely to improve
scheduling without explicit approval, because that can change cost. Disable the
scheduler with `ENABLE_SCHEDULER=false` when proactive work is not desired.

## Health and release verification

After a backend deploy:

```bash
export API_URL=https://your-cloud-run-service-url
curl --fail "$API_URL/health"
curl --fail "$API_URL/ready"
```

Expected bounded responses:

```json
{"status":"ok","service":"eidolon-api"}
```

```json
{"status":"ready","database":"ok"}
```

Then verify from the production frontend:

- authentication and session refresh
- one streamed chat turn and persistence after reload
- its continuity receipt settling without exposing raw cognition/prompt content
- exact production CORS origin
- memory/relationship state for the test account
- no unexpected browser console/network failures
- latest Cloudflare and Cloud Run revisions correspond to the intended commit

## Backups and restore

Do not trust important production data without a tested backup and restore path.

- Keep database credentials and dumps out of Git.
- Use the provider's managed backup/export capability and/or an encrypted
  operator-controlled `pg_dump` process.
- Record the Alembic revision with each backup.
- Periodically restore into a disposable PostgreSQL instance and run
  `alembic current`, `/ready`, and representative ownership checks.
- Take a verified backup before destructive migrations or bulk data cleanup.
- Account JSON export is a user-data feature, not a complete database backup.

## Rollback

A Cloud Run traffic rollback can restore application code, but it does not undo
an already-applied database migration. Production schema changes must therefore
be backward-compatible or include a separately tested recovery plan.

For frontend regressions, use Cloudflare's prior deployment only after confirming
its embedded API base URL and API contract remain compatible.

## Resource and cost controls

The personal deployment targets configured free-tier limits, but external free
tiers and model availability can change.

- keep Cloud Run max instances and database pools bounded,
- keep prompts and output limits bounded,
- set cloud budget/quota notifications outside the repository,
- monitor provider/database quotas and current model availability,
- do not assume a preview, retry loop, scheduler change, or live test is free,
- keep provider/database abstractions and current backups usable for migration.

## Troubleshooting

- Production settings failure: compare Cloud Run variables and secret bindings
  with `.env.example`; never paste values into source.
- `/health` succeeds but `/ready` fails: the process is alive but PostgreSQL is
  unavailable; inspect bounded platform logs and Supabase/session-pooler state.
- Provider readiness fails: verify secret binding, configured model availability,
  quota, and timeout without exposing the key.
- Frontend build rejects API URL: set the public Cloudflare build variable and
  trigger a new build.
- Browser CORS failure: compare the browser `Origin` exactly with `WEB_ORIGIN`
  and `CORS_ORIGINS`; omit paths and trailing slashes.
- Login succeeds but reload signs out: verify `SameSite=None; Secure`,
  credentialed fetches, and third-party-cookie policy; prefer same-site custom
  subdomains for reliability.
- Stream ends early: verify Cloud Run request timeout exceeds provider timeout
  and no proxy buffers `text/event-stream`.
- New revision fails startup: inspect migration status first; do not bypass a
  failed migration by starting against an unknown schema.
