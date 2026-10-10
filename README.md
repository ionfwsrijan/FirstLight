# FirstLight

**The 6 AM on-call agent for the air a child breathes — it answers before a single bell rings, and it ships the receipts.**

> **Track:** Air · **Path:** Build It + Ship It (both live).
> **Ship It is deployed:** the console runs on AWS Lambda + API Gateway +
> DynamoDB + Cognito — **[open the live console](https://8s2dtqrqzi.execute-api.ap-south-2.amazonaws.com/dev/)**. Every verdict you see is the
> same deterministic engine as the local build, packaged into the Lambda layer
> by [`sam/build_layer.py`](sam/build_layer.py) (and asserted identical by
> [`tests/test_sam_mirror.py`](tests/test_sam_mirror.py)). The **Build It** path
> (FastAPI + SQLite) is the zero-dependency replay for reviewers: no account, no
> network, runnable in two minutes. AWS **Cedar** open-source policies encode the
> role matrix in both.

[![CI](https://github.com/ionfwsrijan/FirstLight/actions/workflows/ci.yml/badge.svg)](https://github.com/ionfwsrijan/FirstLight/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/license-MIT-2eb872)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.11%20%7C%203.12%20%7C%203.13-3776ab)](pyproject.toml)
[![Built on AWS](https://img.shields.io/badge/built%20on-AWS-ff9900)](docs/architecture.md)

**Live console:** <https://8s2dtqrqzi.execute-api.ap-south-2.amazonaws.com/dev/> · **Local replay:** `py -m firstlight.cli seed && py -m firstlight.cli serve` → <http://127.0.0.1:8000>

**Docs:** [Architecture (Mermaid)](docs/architecture.md) · [Demo film](docs/demo-script.md) · [What's real vs simulated](docs/LEARNINGS.md) · [Submission map](docs/submission.md) · [Cedar policies](firstlight/auth/cedar/policies.cedar) · [Ship It runbook](sam/README.md)

Every winter, NCR children lose school days to closures nobody decided — a
cloud of stubble smoke arrives overnight, a principal wakes up confused, and
the class call is made in a panic, one school at a time, hours too late.
FirstLight is the call made *by the rules* at 6 AM: it reads 7 CPCB stations,
the stubble fires upwind of the NCR (the frozen scenario's 7, or a **live NASA
FIRMS 24h feed** — the one input that genuinely changes day to day) and 7 prior
mornings on **2026-10-08**, and a deterministic engine answers for each school —
**GREEN, PROTECTED or CLOSED** — from the AQI bands and GRAP stages the
authorities already published. An agent narrates that verdict in plain words
(or Hinglish), explains *why* with the exact rule that fired, and only sends
the parent alert after **you confirm in your own transcript**. Every decision
lands in a tamper-evident ledger, and every alert is dispatched with a channel
receipt you can track in the **outbox**, carrying an HMAC certificate you can
verify later, offline.

Built solo for the AWS *First Commit* hackathon. Everything below is live code
with tests, not a slide.

## Try it in two minutes, no AWS account

```powershell
py -m firstlight.cli seed    # build the local sqlite from the frozen 2026-10-08 morning
py -m firstlight.cli serve   # FastAPI on http://127.0.0.1:8000 (auto-seeds if empty)
```

Open <http://127.0.0.1:8000>, **sign in** with a seeded account (`officer@
firstlight.demo` / `officer123` — or click a card to fill it), **list schools**,
**run the morning**, then talk to the agent: *is today safe for school?* → *why?*
→ *would you send it if the air got worse?* (nothing is sent — that was a
question) → *yes, send it* (signed certificate + **delivery receipt in the
outbox**) → **verify ledger**. Every verdict, consent decision and tamper check
you see is the production code path against a real SQLite file. Sign in as
**principal** to actually dispatch (a parent's "yes, send it" is politely
denied by the role gate), and as **officer** to swap the frozen fires for the
**live NASA FIRMS feed** (`Refresh fire data`) — the source chip goes
`LIVE · FIRMS`, and every input's provenance is labeled on the dashboard.

---

## What it does, in one morning

```
06:00 · FastAPI POST /api/morning/run (officer role)   ingest the frozen snapshot
        │  + interpolate AQI        IDW from the 4 nearest stations (≤ 40 km)
        │  + stubble plume          wind 310°/16 kmh · alignment + reach
        │  + 7-day trend            median baseline · Δ and Δfrac, then rising/stable/improving
        ▼
        rule engine · data-driven DSL (7 rules, CPCB bands, GRAP stages,
        plume, sensitivity bonus) · per school: GREEN / PROTECTED / CLOSED
        ▼
        SQLite (WAL)  → decisions · history_aqi · alerts  (idempotent per school per date)
        ▼
        hash-chained ledger  → decision/alert/cert rows; verify() must pass to be shown
        ▼
   you, in the console ◀──── FastAPI POST /api/agent/talk   (consent gate + role gate)
        "is today safe for school?"  → status, band, GRAP, upwind fires, trend
        "why?"                       → the exact rules that fired, verbatim
        "yes, send it"               → HMAC-signed certificate + notifier dispatch
        ▼
        notifier (console / silent / SMTP / webhook) → parent + principal + ward office
        ▼
        outbox (GET /api/outbox)     → every send visible: channel + receipt + cert
```

The same morning, one hour later, is decisionally identical: the engine is
deterministic, and `run_morning` is idempotent. The AI narrates the engine; it
never manufactures a number.

## Where AWS fits

| Service / AWS open source | Role | Where |
|---|---|---|
| **AWS Cedar** (AWS OSS) | the authorization engine: allow/forbid matrix for parent/principal/officer | [`auth/cedar/policies.cedar`](firstlight/auth/cedar/policies.cedar), mirrored by `auth/roles.py` |
| **Powertools for AWS Lambda** (AWS OSS) | optional tracing/routing on the Ship It functions | `pyproject.toml` `[aws]` extra, `sam/handlers/` |
| **Amazon Cognito** | the roles as real identity (parent/principal/officer) in the twin | `sam/template.yaml` |
| **Amazon API Gateway** | the twin's authorized API | `sam/template.yaml` |
| **Amazon DynamoDB** | decisions + alerts store in the twin (mirror of SQLite tables) | `sam/handlers/shared.py` |
| **AWS Lambda** | morning / status / talk functions in the twin | `sam/handlers/` |
| **AWS Serverless Application Model** | the whole Ship It definition | [`sam/template.yaml`](sam/template.yaml) |
| **FastAPI + SQLite (Build It)** | the demoable local product, zero cloud | `firstlight/api/`, `firstlight/storage/` |
| **SMTP / webhook / console** | alert delivery channels (the twin wires the webhook via `ALERT_HOOK_URL`) | `firstlight/notifier/`, `sam/handlers/shared.py` |

## Safety model (the part that matters)

Auto-decided school closures are only worth shipping if they cannot do the
wrong thing. FirstLight's controls are in code and tests, not in a prompt:

1. **The engine decides.** `decide_school` returns a level from the AQI/band/
   GRAP/plume tables. There is **no code path** where a model, prompt or coin
   toss produces a verdict; the agent only converts `Decision` to speech.
2. **Consent is checked against your transcript, never the model's claim.**
   Every talk turn is persisted (`/api/transcript`) and replayed into the
   consent gate, so the gate remembers your conversation even across a reload.
   `consent_turn` still requires the send intent **and** an explicit
   confirmation phrase (`yes, send it`, `bhejo`) in *the same turn*. A
   question — *"would you send it?"* — never sends.
3. **Roles are one-directional, end to end.** A parent can read status and ask
   questions; only a principal can `alert:send`; only an officer can
   `run:morning`, refresh live data or read the ledger. Forbidden by default;
   tested per endpoint — and the *agent itself* refuses to dispatch for a role
   without `alert:send`, even after explicit confirmation.
4. **Live data is labeled, and falls back.** The engine never touches the
   network. An officer's `Refresh fire data` fetches NASA FIRMS and records
   provenance (source, timestamp, count, fallback flag) in the DB; the console
   labels every input with where it came from and when it was observed.
   If FIRMS is unreachable the morning stays on the frozen scenario, visibly.
5. **Every fact is chained.** The ledger is append-only and hash-chained
   (SHA-256). An offline edit breaks `verify()` and the day stops being shown
   as authentic — edits are *detectable*, not silent.
6. **Every alert is signed and its delivery proven.** Alerts carry an
   HMAC-signed certificate over the canonical decision JSON and are dispatched
   through a real notifier; the returned receipt (e.g. `console-s-avini`,
   `smtp-…`) is recorded alongside in the outbox.
7. **Deterministic and idempotent.** The same inputs give the same verdict a
   hundred times; replaying the morning does not duplicate decisions.
8. **Fail-closed by default.** Published endpoints 401 without a token,
   **403 on open role minting** (`/api/auth/issue` is closed — login only),
   403 on the wrong role, 404 for unknown schools; unknown agent turns return
   the status narration, never an invented answer.
9. **Tests assert the safety model.** `tests/test_agent.py` proves the consent
   gate, `tests/test_ledger.py` proves tamper detection, `tests/test_api.py`
   proves login, closed minting, role enforcement and the delivery outbox on
   live endpoints, `tests/test_sources.py` proves FIRMS parsing and the
   fallback/provenance path.

Details: [`tests/`](tests/) and [`docs/architecture.md`](docs/architecture.md).

## Run it

### Locally, no AWS account (the *Build It* path)

```powershell
git clone https://github.com/ionfwsrijan/FirstLight && cd firstlight
py -m pip install -e ".[test]"     # fastapi, uvicorn, pydantic, httpx
py -m firstlight.cli gate          # 121 tests
py -m firstlight.cli seed          # build the local sqlite (or let the server auto-seed)
py -m firstlight.cli serve         # http://127.0.0.1:8000
```

Sign in with a demo account (seeded idempotently on every boot):
`parent@firstlight.demo` / `parent123` · `principal@firstlight.demo` /
`principal123` · `officer@firstlight.demo` / `officer123`.

Needs Python 3.11+. No Docker, no AWS credentials, no npm. `scripts/run.ps1`
and `scripts/gate.ps1` wrap the two common commands.

### On AWS (the *Ship It* path — deployed)

```bash
python sam/build_layer.py                  # package the pure-Python core into a Lambda layer (cross-platform)
sam validate -t sam/template.yaml --lint
sam build --template sam/template.yaml
sam deploy --stack-name firstlight-shipit --capabilities CAPABILITY_IAM \
  --no-confirm-changeset --resolve-s3 --parameter-overrides Env=dev --region ap-south-2
```

Then the same flow against the deployed URL:

```text
GET  <ApiUrl>/                   → the live console
POST <ApiUrl>/login  {username,password}
POST <ApiUrl>/morning            → 7 schools, byte-identical verdicts to local
GET  <ApiUrl>/decisions/s-avini
POST <ApiUrl>/talk  {"text":"yes, send it","school_id":"s-avini"}
```

The live deployment is on the AWS free tier shape (Lambda + DynamoDB on-demand
+ Cognito). Full runbook, least-privilege IAM notes and the hosted-UI caveat:
[`sam/README.md`](sam/README.md).

## Repository map

```
firstlight/
  config.py            env-overridable settings (secret, db path, web dir, notify…)
  domain/              Level/Trend, Station, School, StubbleFire, Wind, inputs, RuleHit, Decision
  engine/              CPCB bands + GRAP stages, haversine/bearing, IDW interpolation,
                       stubble-plume model, 7-day trend, decision orchestration
  dsl/                 data-driven rule chain evaluated like a tiny language (7 rules)
  ledger/store.py      append-only hash-chained event ledger + verify()
  auth/                HMAC capability tokens, seeded password login (pbkdf2-sha256), role matrix, Cedar policies
  agent/               intents (en + Hindi/Hinglish), narrator, consent gate, certificate signing
  notifier/            console / silent / SMTP / webhook dispatch abstraction (returns a receipt)
  storage/             SQLite schema (WAL) + repositories: stations, schools, fires, history, decisions,
                       alerts (channel+receipt), users, server-side agent transcript, meta (provenance)
  pipeline/            frozen 2026-10-08 scenario + live NASA FIRMS source (parse/fetch/refresh/fallback)
                       + run_morning orchestration
  api/                 FastAPI: /api/health, /api/auth/login (issue is 403), /api/morning/*, /api/sources/refresh,
                       /api/agent/talk, /api/transcript, /api/outbox, /api/ledger*, /
  cli/                 serve · seed · gate
web/index.html         the console (login, source chip, provenance labels, outbox, transcript — no build step)
sam/                   Ship It twin: template.yaml, Lambda handlers, DynamoDB mirror, core layer
tests/                 121 tests: bands, geometry, interpolation, plume, trend, DSL, ledger tamper,
                       auth + Cedar + login, intents + consent, certificates, pipeline, API roles,
                       FIRMS parsing + fallback, outbox + transcript, SAM mirror
scripts/               run.ps1 · gate.ps1
docs/                  architecture.md (Mermaid) · demo-script.md (the film, shot by shot)
```

## Development

```powershell
py -m firstlight.cli gate    # the whole suite; exit code gates the commit
py -m firstlight.cli seed    # rebuild the local database from the frozen morning
py -m firstlight.cli serve   # the API + console
```

Tests are the spec. The safety model is asserted from the same code that runs
(`tests/test_agent.py`, `tests/test_ledger.py`), the roles from live endpoints
(`tests/test_api.py`), and the Ship It twin from the same files the layers
ship (`tests/test_sam_mirror.py` — cloud verdicts must equal local verdicts).

## Production notes

What "production shape" means here, and where each claim is enforced:

| Concern | Where |
|---|---|
| Secrets are injectable, never hard-required: `FIRSTLIGHT_SECRET` (dev default only), DB path, notify channel, SMTP creds, webhook URL | `firstlight/config.py` |
| SQLite runs in WAL mode, foreign keys on, schema idempotent; the ledger table is created with the schema, so a fresh boot is always verify-true | `storage/db.py` |
| Token expiry and role are verified on every call; `_require` enforces the action matrix, tests cover 401/403/404 | `auth/tokens.py`, `api/__init__.py`, `tests/test_api.py` |
| Notifier failures are logged and never take the morning down (SMTP/webhook return a receipt or a `-failed` string) | `notifier/__init__.py` |
| The morning is idempotent per school+date (upsert), and the whole thing is committed atomically after the ledger append | `pipeline/morning.py`, `storage/repositories.py` |
| Determinism is a test: repeated runs produce byte-identical decision payloads | `tests/test_engine.py`, `tests/test_pipeline.py` |
| The demo console serves from the same FastAPI process, no separate build | `api/__init__.py` `/`, `web/index.html` |
| Live fire refresh is officer-only; provenance (source, timestamp, count, fallback) is persisted and labeled; FIRMS failures fall back to the frozen scenario | `pipeline/sources.py`, `storage/repositories.py`, `api/__init__.py` |
| Every send is auditable end to end: alert row carries channel + receipt + cert, the outbox exposes it, talk turns persist server-side | `storage/repositories.py`, `api/__init__.py` |

Known gaps, on purpose for a hackathon: a dev-only default secret instead of a
real secret manager (inject it in prod), and the demo's stations/wind/history
stay frozen (only the fires are live, via NASA FIRMS with a visible fallback —
the ingest interface is the same dict shape, so a full feed is a swap of one
fetcher). The full "real vs simulated" table, with CPCB/CAQM citations, is in
[`docs/LEARNINGS.md`](docs/LEARNINGS.md). The Ship It twin **is deployed**
(live console above) and is `sam validate`-clean.

## Quality gates

```bash
ruff check .                         # lint
mypy firstlight                      # types (clean)
pytest --cov=firstlight              # tests + coverage floor
python sam/build_layer.py --check    # console single-source (no drift)
cfn-lint sam/template.yaml && sam validate --template sam/template.yaml --lint
```

All of these run in [`.github/workflows/ci.yml`](.github/workflows/ci.yml) on
every push and pull request.

## Charts

- **Architecture** (Mermaid): [`docs/architecture.md`](docs/architecture.md)
- **Demo film script** (shot by shot): [`docs/demo-script.md`](docs/demo-script.md)