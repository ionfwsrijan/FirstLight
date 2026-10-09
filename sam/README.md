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

## Deploy (from source, verified working)

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

## Deployed (live) instance

Deployed and verified end to end in the Srijan AWS account, region `ap-south-2`:

- **Stack**: `firstlight-shipit` — API Gateway + 3 Lambdas (arm64, python3.12) +
  Cognito user pool + DynamoDB `firstlight-shipit-DecisionsTable-*`.
- **ApiUrl**: `https://2mzwa6sjug.execute-api.ap-south-2.amazonaws.com/dev/`
  (Cognito authorizer on every route — no token ⇒ 401).
- **UserPoolId**: `ap-south-2_P3svZgHis` · **UserPoolClientId**:
  `1kvqda903s34vjavra0d71gnvo`.
- Verified live: `/morning` → 7 decisions (5 CLOSED / 2 PROTECTED, byte-identical
  to the local build), `/status` → latest decision, `/talk` consent flow (a
  question never sends; explicit "yes, send it" sends with a delivery receipt),
  unknown school → 404, no token → 401.

To recreate it from scratch (Windows):

```powershell
py -m pip install aws-sam-cli cfn-lint externaltooling  # sam.exe lands in ...\Python313\Scripts
powershell -File sam/build-layer.ps1                     # must print "files ... 80" (not a 0-file copy)
sam build --template sam/template.yaml  # needs a python3.12 interpreter on PATH (py -3.12)
sam deploy --stack-name firstlight-shipit --capabilities CAPABILITY_IAM --no-confirm-changeset --resolve-s3 --region ap-south-2 --parameter-overrides Env=dev
```

Add a demo user and enable the admin password flow (one-time, per pool):

```powershell
aws cognito-idp update-user-pool-client --user-pool-id <pool> --client-id <client> --explicit-auth-flows ALLOW_USER_SRP_AUTH ALLOW_REFRESH_TOKEN_AUTH ALLOW_ADMIN_USER_PASSWORD_AUTH
aws cognito-idp admin-create-user --user-pool-id <pool> --username meera --user-attributes Name=email,Value=parent@firstlight.demo Name=email_verified,Value=true
aws cognito-idp admin-set-user-password --user-pool-id <pool> --username meera --password 'Parent12345' --permanent
aws cognito-idp admin-initiate-auth --user-pool-id <pool> --client-id <client> --auth-flow ADMIN_USER_PASSWORD_AUTH --auth-parameters USERNAME=meera,PASSWORD=Parent12345
```

## Keys you will need in Review

- `sam/template.yaml` is fully formed, so `sam validate` passes; the twin is
  now **live-deployed and verified**, not just template-valid.
- `firstlight/auth/cedar/policies.cedar` is where `aws` meets the local build.