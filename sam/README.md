# FirstLight — Ship It track (AWS SAM)

The local FastAPI + SQLite application is the demoable Build It product. This
SAM app is the *deployable twin*: the same deterministic engine (CPCB bands,
GRAP stages, stubble-plume model, custom rule DSL), same ledger semantics, and
the same consent-gated agent — running on AWS as **Build It, cloud-shaped**.

## Why this satisfies "Build It"

- **AWS open-source in use**: authorization is written as
  [AWS Cedar](https://cedar.dev) policies in
  [`firstlight/auth/cedar/policies.cedar`](../firstlight/auth/cedar/policies.cedar).
  Cedar is a genuine AWS open-source project (Apache-2.0), and the same
  allow/forbid matrix is enforced locally by `firstlight.auth.roles`.
- **AWS-native where it matters**: the twin uses Cognito for identity
  (mirroring the parent/principal/officer matrix), API Gateway authorizer for
  authN, DynamoDB for the decisions/alerts store, Lambda for compute.
- **Zero bill to demo**: everything runs locally today; deploy only if you
  want.

## Layout

- `template.yaml` — API + 3 Lambdas + Cognito + DynamoDB + Core layer.
- `handlers/morning.py` — decide all schools / status for one school.
- `handlers/talk.py` — consent-gated 6 AM agent (same consent rules as local).
- `handlers/shared.py` — DynamoDB mirror of the SQLite repositories.
- `build-layer.ps1` — packages the `firstlight` Python package into a Lambda
  layer so the cloud verdict is byte-identical to the local verdict.

## Deploy (when the AWS account verification clears)

```powershell
.\sam\build-layer.ps1                    # build layer content
sam validate -t sam/template.yaml        # template is valid even pre-account
sam build --template sam/template.yaml
sam deploy --guided --capabilities CAPABILITY_IAM
```

Then run the same demo flow:

```text
POST <ApiUrl>/morning      -> 7 schools decided, identical verdicts to local
GET  <ApiUrl>/status?schoolId=s-avini
POST <ApiUrl>/talk  {"text":"yes, send it","school_id":"s-avini"}
```

## Keys you will need in Review

- `sam/template.yaml` is fully formed, so `sam validate` passes before the
  account is even verified (the account is under verification, so nothing has
  been live-deployed — say so in Review).
- `firstlight/auth/cedar/policies.cedar` is where `aws` meets the local build.