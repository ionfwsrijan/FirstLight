# FirstLight — the 6 AM on-call agent for the air a child breathes

**Track:** Air · **Path:** Build It + Ship It mirror · **Stack:** Python + FastAPI + SQLite (Build It), AWS SAM + Lambda + DynamoDB + Cognito (Ship It) · **AuthZ engine:** AWS Cedar OSS

At 6 AM, before a single bell rings, a parent or a principal needs one answer:
**is today safe for school?** FirstLight is the call that answers from the
**CPCB AQI band table, the GRAP action plan, and the overnight stubble-fire
record** — decided by a deterministic rule engine, narrated (never invented)
by a conversational agent, sent only after explicit consent, and backed by a
tamper-evident ledger and signed certificates.

> The 3 AM problem is easy: Delhi schools already call off class reactively,
> in the middle of the day, one school at a time. The problem is the **6 AM
> decision** — before the first symptom. FirstLight makes it *before anyone has
> to*, with receipts.

---

## What runs

```
firstlight/
  pyproject.toml               runtime deps (fastapi, uvicorn, pydantic)
  firstlight/
    config.py                  env-overridable settings (secret, db, web, notify…)
    domain/                    Level/Trend/Station/School/StubbleFire/Wind/Decision
    engine/
      bands.py                 CPCB AQI bands + GRAP stages          [deterministic]
      bands + policy catalog   the 7 rule decision hierarchy
      geometry.py              haversine, bearing, wind alignment
      interpolation.py         IDW AQI from the 4 nearest stations (≤40 km)
      plume.py                 stubble-fire plume model (reach, alignment)
      trend.py                 7-day rising/falling baseline
      policy.py + dsl/          data-driven custom rule DSL + catalog
    ledgers→ledger/store.py      hash-chained append-only event ledger + verify()
    auth/                      role matrix (parent/principal/officer), HMAC tokens
      auth/cedar/policies.cedar  AWS Cedar policies (the "Built on AWS" beat)
    agent/                     intents (en + Hindi/Hinglish), narrator,
      consent.py               consent gate ("yes, send it" in the same turn),
      certificate.py           HMAC-signed, verifiable decision certificates
    storage/                   SQLite schema + repositories (WAL)
    pipeline/                  frozen 2026-10-08 scenario + run_morning
    notifier/                  console / silent / SMTP / webhook
    api/                       FastAPI: /api/health, /morning/*, /agent/talk,
                               /ledger*, /auth/issue, / (web console)
    cli/                       serve · seed · gate
  web/index.html               the console (no build step, no npm)
  sam/                         Ship It twin: template.yaml, handlers, Cedar notes
  tests/                       102 tests, green, zero network calls
  scripts/                     run.ps1 (serve) · gate.ps1 (suite)
```

## Why it wins on the judging sheet

| Criterion | How FirstLight answers |
|---|---|
| **Idea & Impact** | Every NCR child loses school days each winter to reactive, uncoordinated closures. FirstLight turns a chaotic 6 AM scramble into one rule-decided answer with receipts. |
| **Built on AWS** | **Build It** — the product is a real, runnable, fully-tested local stack using AWS **Cedar** (a genuine AWS OSS project) for authorization, with a complete **Ship It SAM twin** (Lambda + DynamoDB + Cognito + API Gateway) that runs the *same* engine. Nothing needs a live account to demo; deployment is one command away. |
| **Design & usability** | A three-word flow — **status, why, send it** — a real parent can use in Hinglish. The web console mirrors the phone call exactly. |
| **Execution** | One deterministic feature runs and is tested: the decision engine, its persistence, its ledger, its auth, and its **consent-gated send** — 102 tests when you gate. |
| **Cost & realism** | Uses free, verifiable gov data shapes (CPCB AQI, GRAP, NASA FIRMS stubble fires); zero cloud bills in demo; signed receipts give the demo a paper trail judges can hold. |

## The two hard rules of the AI

1. **The engine decides.** `decide_school()` returns a level from the
   AQI/band/GRAP/plume tables. The agent converts it to speech. **There is no
   code path where the model chooses a verdict.**
2. **No action without consent.** Sending alerts requires the send intent
   **and an explicit confirmation phrase in the same turn** (`sent it`, `yes`).
   A question — *"would you send it?"* — never sends. Both rules are unit-tested.

```
> good morning — is today safe for school?
  Ramjas P. Block, Ashok Vihar: AQI 442 (Severe), GRAP Stage 3, 6 upwind
  stubble fires, rising. CLOSED — classes move online.
> why?
  AQI >= 401 (Severe band) → CLOSED; AQI >= 301 with an active stubble plume → CLOSED.
> what do we do
  Declare online day · cancel outdoor PE · notify parents by 7:00 · re-evaluate at 12:00
> would you send it if the air got worse?
  (the agent does NOT send — that was a question)
> yes, send it
  Done. Alert raised for s-avini, certificate FIRSTLIGHT-s-avini-0001, chained to the ledger.
```

## Run it (Build It — no AWS account, no card)

```powershell
py -m firstlight.cli gate            # 102 tests
py -m firstlight.cli seed            # build the local sqlite from the frozen morning
py -m firstlight.cli serve           # FastAPI on http://127.0.0.1:8000 (auto-seeds if empty)
# open http://127.0.0.1:8000  →  the FirstLight console
```

Console flow: **issue a token** (pick `officer`) → **list schools** → **run
morning** → ask the agent anything → try *"would you send it…?"* (no send)
then *"yes, send it"* (signed + sent) → **verify ledger**.

## Ship It twin (`sam/`)

`sam/template.yaml` builds: Cognito user pool (parent/principal/officer) ·
5-minute-api authorizer · DynamoDB decisions/alerts · 3 Lambdas · a `firstlight`
core **layer** so the cloud verdict is byte-identical to the local verdict.
`sam/build-layer.ps1` packages the core; `sam/README.md` has the deploy
commands. Authorization mirrors `firstlight/auth/cedar/policies.cedar`.

```powershell
.\sam\build-layer.ps1
sam validate -t sam\template.yaml     # valid today, before the account even clears
```

## Data honesty

`pipeline/scenario.py` ships a frozen representative morning
(7 NCR stations, 7 real-placed Delhi schools, 7 Punjab/Haryana stubble fires,
7 prior mornings of history) so every run is reproducible and every test is a
fact-check, not a fish. The real CPCB AQI feed and NASA FIRMS fire feed are
the documented next ingest; the repositories already consume the same dict
shapes.

## Tests

102 tests across: bands/GRAP thresholds, geometry, IDW interpolation, plume
model, trend, the rule DSL, ledger tamper-detection, HMAC tokens + role
matrix, Cedar policy presence, intents + consent gate, certificates, the full
morning pipeline, every API endpoint with role enforcement, and a Ship It
mirror test stubbing boto3.