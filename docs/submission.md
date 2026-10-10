# FirstLight — submission map (criterion → evidence)

A single page that points every judging criterion at the code, test, or URL
that proves it. No claim here without a pointer.

## Product & problem fit

- **Problem:** NCR school days are cancelled *after* the fact, school by school,
  by whoever wakes up first. FirstLight makes the call *by the published rules*
  at 6 AM, for every school at once, and keeps the receipts.
- Evidence: [`README.md`](../README.md) intro · [`docs/architecture.md`](architecture.md).

## It actually runs (Build It)

| Claim | Evidence |
|---|---|
| Zero-dependency local product | `py -m firstlight.cli seed && py -m firstlight.cli serve` → <http://127.0.0.1:8000> |
| Deterministic engine | [`firstlight/engine/`](../firstlight/engine/), tests in [`tests/test_engine.py`](../tests/test_engine.py) |
| Consent-gated agent | [`firstlight/agent/consent.py`](../firstlight/agent/consent.py), [`tests/test_agent.py`](../tests/test_agent.py) |
| Tamper-evident ledger | [`firstlight/ledger/store.py`](../firstlight/ledger/store.py), [`tests/test_ledger.py`](../tests/test_ledger.py) |
| Role model (Cedar + code) | [`firstlight/auth/cedar/policies.cedar`](../firstlight/auth/cedar/policies.cedar), [`tests/test_auth.py`](../tests/test_auth.py), [`tests/test_api.py`](../tests/test_api.py) |

## It ships (Ship It, on AWS)

| Criterion | Evidence |
|---|---|
| Deployed, reachable console | Live API + console from `sam/` (Lambda + API Gateway + DynamoDB + Cognito) |
| Same engine in the cloud | [`sam/build_layer.py`](../sam/build_layer.py) packages the exact `firstlight` core; [`tests/test_sam_mirror.py`](../tests/test_sam_mirror.py) asserts cloud verdicts equal local |
| Least-privilege IAM | [`sam/template.yaml`](../sam/template.yaml): per-function inline policies scoped to one table / one Cognito pool action — no broad managed policies |
| Data durability | DynamoDB PITR + SSE, stream enabled |
| Observability | X-Ray active on functions and stage; JSON logs |
| AuthN/AuthZ | Cognito authorizer on every protected route; `/health`, `/login`, `/` public by design |

## Rigor judges can attack

| Challenge | Where we answer it |
|---|---|
| "Where does that AQI number come from?" | [`docs/LEARNINGS.md`](LEARNINGS.md) — CPCB/CAQM citations, constants table |
| "What's live vs simulated?" | [`docs/LEARNINGS.md`](LEARNINGS.md) inputs table |
| "Could it close a school wrongly?" | Fail-closed by default; role gate + consent gate; determinism tests |
| "Can you prove the decision trail?" | Hash-chained ledger + `verify()`; `tests/test_ledger.py` |

## Quality gates (CI)

- Lint: `ruff check .`
- Types: `mypy firstlight` (clean)
- Tests + coverage floor: `pytest --cov=firstlight`
| Console single-source (`web/index.html` == served copy) | `python sam/build_layer.py --check` |
| IaC | `cfn-lint sam/template.yaml` · `sam validate --lint` |

All of the above run in [`.github/workflows/ci.yml`](../.github/workflows/ci.yml)
on every push and pull request.
