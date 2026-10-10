# FirstLight: the 6 AM agent that decides seven schools' mornings — and ships the receipts

It is 6 AM in Delhi in early November. The air at Anand Vihar reads **427** on the CPCB scale and there are six stubble fires upwind in Punjab. No human has looked at any of it yet. FirstLight has already interpolated every school's air from the nearest monitoring stations, scored the smoke plume against the wind, read the seven-day trend, and run it all through the published rules — **CPCB bands and the CAQM GRAP stages** — for all seven schools at once. One school comes out **CLOSED**. Another, calmer, comes out **PROTECTED**. Each verdict arrives with its evidence and the exact list of actions the rules allow.

That's the product. The interesting engineering question is the one every team deploying an "AI agent" eventually has to answer: **when the decision affects a child's school day, who is actually making the call — and can you prove it?**

This post is how I built FirstLight on AWS so the answer is *ordinary deterministic code*, and every decision ships with a receipt.

> **Live console:** https://8s2dtqrqzi.execute-api.ap-south-2.amazonaws.com/dev/
> **Source:** https://github.com/ionfwsrijan/FirstLight

---

## The design bet: no foundation model in the decision path

The default move for an "agent" in 2026 is to put a model in the middle. I deliberately didn't. There is **no LLM anywhere in the decision or reply path**. The verdict is produced by a pure-Python rule engine, and the "agent" that talks to users is a deterministic intent classifier plus a narrator that reads the decision back.

The reason is simple: the class of 2026 does not get its school day decided by a temperature setting. A model can *paraphrase* the decision (it does), but it can never *make* it. That single constraint is what makes every other property in this project — determinism, testability, auditability — possible.

```
06:00 ──► morning_inputs()          # snapshot: 7 stations · 7 schools · 7 fires
      ──► interpolate(stations)     # IDW over the 4 nearest stations
      ──► plume(fires, wind)        # upwind reach (500 km) + fire radiative power
      ──► trend(history)            # 7-day median baseline
      ──► evaluate(rules)           # 7-rule DSL → CPCB band · GRAP stage · verdict
      ──► persist + ledger.append() # append-only SHA-256 hash chain
```

## Where AWS fits

FirstLight ships on two paths. **Build It** is a zero-dependency local replay (FastAPI + SQLite, no account, no network). **Ship It** is the real thing, deployed in `ap-south-2`. The trick is that both run **the exact same core** — it's packaged as a Lambda layer, and a test asserts the cloud answer is byte-for-byte identical to the local one.

| AWS service / open source | What it does here |
|---|---|
| **AWS Lambda** (arm64, python3.12) + **API Gateway** (REST + Cognito authorizer) | serves the same console and the `morning / talk / meta` APIs |
| **Lambda layer** | the pure-Python engine, rule DSL, ledger and agent — shared with the local build |
| **Amazon DynamoDB** (single table, on-demand, PITR + SSE) | decisions, alerts, the hash-chained ledger, agent transcript, outbox |
| **Amazon Cognito** | parent / principal / officer roles and the ID tokens the gateway trusts |
| **Amazon EventBridge** | the autonomous `cron(30 0 * * ? *)` run at 06:00 IST — no human, no login |
| **Amazon CloudWatch + SNS + SQS** | error alarms to a topic; a dead-letter queue on the scheduled async path |
| **AWS IAM** (scoped inline policies) | least privilege per function — Dynamo read vs read/write, Cognito auth only |
| **AWS Cedar** (open source) | the allow/forbid role matrix, shipped in the local build too |
| **AWS SAM CLI** (open source) | build + deploy; `cfn-lint` and `sam validate` run in CI |

Under the hood: `aws-cdk`-free, hand-written SAM, X-Ray active tracing on functions and stage, and a single DynamoDB table with `PAY_PER_REQUEST`.

## Four things I'd want a reviewer to attack

### 1. The consent gate is deliberate, not decorative

Dispatch requires the *send intent* **and** an explicit confirmation in the **same turn**. `is my school closed?` never sends. `maybe send later` never sends. And a **parent** who does confirm is refused — and the refusal is recorded.

```python
# firstlight/agent/consent.py (shape, abridged)
if not (intent.send and turn.confirmed):
    return Reply(status, reason="question, not an instruction", sent=None)
if role not in ("principal", "officer"):
    return Refusal(recorded=True)   # parent confirmed → refused, and logged
dispatch_once(decision)             # exactly once
```

Every consent and intent variant has its own test. There are **163 tests** and **87% coverage**, and the safety model is asserted directly rather than described.

## It executes once — then proves it

The alert is delivered a single time, its HMAC certificate verifies offline, and the decision, the alert and the agent's turns are appended to a **SHA-256 hash chain**. `verify()` recomputes the chain and reports the *first* broken row. Tamper with any row and the trail fails loudly.

```python
# firstlight/ledger/store.py (shape)
def verify(self) -> VerifyResult:
    prev = GENESIS
    for i, row in enumerate(self.rows()):
        if row.prev_hash != prev or digest(row) != row.hash:
            return VerifyResult(ok=False, first_bad=i)
        prev = row.hash
    return VerifyResult(ok=True)
```

This is what lets me write "it ships the receipts" without asking anyone to trust me. The ledger is a first-class feature, not a log line.

## Roles fail closed

Every protected route checks the Cognito token **and** the Cedar matrix. `401`, `403` and `404` each have tests. The public surface is deliberately tiny: `/api/health`, `/api/auth/login`, and `/`. IAM is composed per function from narrow statements — a Dynamo read policy for the read-only console handler, read/write only where the officer's refresh runs, and Cognito `AdminInitiateAuth` only in the login function. No broad managed policies; `cfn-lint` is clean in CI.

## Honesty as a feature: live vs frozen, stated per field

A demo that quietly mixes real and fake data is worse than one that admits both. The deployed twin runs `SOURCE_MODE=live`: the 6 AM EventBridge schedule (and an officer's *Refresh*) fetches **live station air** from the key-free Open-Meteo air-quality API, converted to a **CPCB statutory AQI** via the official PM2.5/PM10 sub-index breakpoints, and **live stubble fires** from NASA FIRMS. Wind and prior mornings stay frozen for a reproducible demo.

Crucially, every field carries provenance. `GET /api/health` reports, per field, whether it is live or frozen and whether a live fetch fell back:

```json
{
  "source": { "source": "live", "fetchedAt": "2026-10-10T03:30:12Z" },
  "sources": {
    "stations": { "mode": "live",   "count": 7,  "fallback": false },
    "fires":    { "mode": "live",   "count": 80, "fallback": false },
    "wind":     { "mode": "frozen" },
    "history":  { "mode": "frozen" }
  }
}
```

On any upstream failure the value falls back to the frozen snapshot — visibly, and recorded. The console shows a `LIVE DATA` / `DEMO · FROZEN SNAPSHOT` banner so a judge never has to guess.

## The autonomous 6 AM run

The thing that makes it real is that it doesn't need anyone to press a button. An EventBridge rule fires at `06:00 IST`, invokes the scheduled handler, which refreshes the live sources and then decides all seven schools — entirely independent of logins. The async path has an SQS dead-letter queue and CloudWatch error alarms wired to an SNS topic. I verified the rule fires end-to-end by temporarily setting it to `rate(2 minutes)` and watching `AWS/Events Invocations` and a fresh Lambda `REPORT` line, then restoring the cron.

---

## Try it in two minutes (no AWS account)

```bash
make setup            # venv + package + dev deps
make serve            # console + FastAPI at http://127.0.0.1:8000
```

Sign in as any persona, read the morning, then ask the agent. Say `yes, send it` as a **parent** and it's refused (recorded). Say it as the **principal** and the alert fires once, with a signed certificate and a new ledger row.

On AWS:

```bash
python sam/build_layer.py
sam build --template sam/template.yaml
sam deploy --stack-name firstlight-shipit --region ap-south-2 \
  --capabilities CAPABILITY_IAM --no-confirm-changeset --resolve-s3 \
  --parameter-overrides Env=dev SourceMode=live
```

## What I'd do differently / what's honest

- **Two inputs live, two frozen — on purpose.** Reproducibility beats realism for a demo; the provenance endpoint removes the guesswork.
- **A dev default secret, not a secret manager.** Inject `FIRSTLIGHT_SECRET` in production.
- **Reserved concurrency is off** on a brand-new account (the quota is too low to reserve safely), but scoped IAM, PITR + SSE, active tracing, alarms and the DLQ are all on.
- **The notifier returns a receipt**, not a real telephony call tree — the whole dispatch path is real, the last mile is a stand-in.

All of the above, with CPCB and CAQM citations, lives in `docs/LEARNINGS.md`.

## Takeaway

The hardest part of an agent that touches the real world isn't the model — it's the **contract around it**. Deterministic policy makes the decision testable; a hash chain makes it provable; per-field provenance makes it honest; and a shared Lambda layer makes the cloud and your laptop agree byte-for-byte. Put a model in front to translate, by all means — but keep it out of the room where the call gets made.

**Live console:** https://8s2dtqrqzi.execute-api.ap-south-2.amazonaws.com/dev/ · **Code:** https://github.com/ionfwsrijan/FirstLight (MIT)

---

*Suggested tags:* `aws` · `serverless` · `aws-lambda` · `serverlessλ` · `python` · `airquality` · `architecture`
