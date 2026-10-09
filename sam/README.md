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

- `template.yaml` — API + 6 Lambdas + Cognito + DynamoDB + Core layer.
- `handlers/morning.py` — decide all schools / status for one school.
- `handlers/talk.py` — consent-gated 6 AM agent (same consent rules as local).
- `handlers/login.py` — public Cognito login for the console (id token → role).
- `handlers/meta.py` — the console's read surface: `/health`, `/inputs`,
  `/schools`, `/decisions/{schoolId}`, `/transcript`, `/ledger`,
  `/ledger/verify`, `/outbox`, and `POST /sources/refresh`.
- `handlers/shared.py` — DynamoDB mirror of the SQLite repositories, including a
  real SHA-256 hash-chain ledger (`/ledger/verify` recomputes the chain) and the
  persisted agent transcript.
- `static/index.py` + `static/index.html` — the browser console served by the
  API at `GET /`. **`web/index.html` is the single source of truth**: the page is
  byte-identical to the local build and only the API base URL and the demo
  credentials are injected at serve time. `build-layer.ps1` refreshes
  `static/index.html` from `web/index.html`, so the two can never drift.
- `build-layer.ps1` — packages the `firstlight` Python package into a Lambda
  layer so the cloud verdict is byte-identical to the local verdict.

## Deploy (from source, verified working)

```powershell
.\sam\build-layer.ps1                    # build layer content
sam validate -t sam/template.yaml        # template is valid even pre-account
sam build --template sam/template.yaml
sam deploy --guided --capabilities CAPABILITY_IAM
```

Then run the same demo flow (or just open the console URL in a browser):
`GET /` serves the console; `POST /login` with a demo account returns the token
the page uses from then on.

```text
GET  <ApiUrl>/                       -> the browser console (login form)
POST <ApiUrl>/login  {username,password}
POST <ApiUrl>/morning                -> 7 schools decided, identical verdicts to local
GET  <ApiUrl>/status?schoolId=s-avini
POST <ApiUrl>/talk  {"text":"yes, send it","school_id":"s-avini"}
```

## Deployed (live) instance

Deployed and verified end to end in the Srijan AWS account, region `ap-south-2`:

- **Stack**: `firstlight-shipit` — API Gateway + 5 Lambdas (arm64, python3.12) +
  Cognito user pool + DynamoDB `firstlight-shipit-DecisionsTable-*`.
- **ApiUrl**: `https://2mzwa6sjug.execute-api.ap-south-2.amazonaws.com/dev/`
  (Cognito authorizer on every API route — no token ⇒ 401; the console and
  login are public by design).
- **Console URL**: `https://2mzwa6sjug.execute-api.ap-south-2.amazonaws.com/dev/`
  — an EnviroPulse-styled browser console served by the API (`GET /`), with an
  inline Cognito-backed login (`POST /login`, same username/password UX as the
  local console). Demo accounts: `parent@firstlight.demo` / `Parent12345`
  (Meera — can ask, cannot send), `principal@firstlight.demo` / `Principal123`
  (Mr. Rao — can send), `officer@firstlight.demo` / `Officer1234` (Kapoor —
  can send + run the morning).
- **UserPoolId**: `ap-south-2_P3svZgHis` · **UserPoolClientId**:
  `1kvqda903s34vjavra0d71gnvo`.
- Verified live: `GET /` → the full local console (identical markup to
  `web/index.html`) with the API base and the Cognito demo credentials injected
  from the request, and a successful same-origin `/health` call from the
  browser; `POST /login` → cognito IdToken + role for all three demo
  accounts (wrong password → 401); `/morning` → 7 decisions + 7 alerts
  (5 CLOSED / 2 PROTECTED, byte-identical to the local build), officer-only
  (parent → 403); `/status` and `/decisions/{id}` → latest decision; `/talk`
  consent flow (a question never sends; explicit "yes, send it" sends with a
  delivery receipt; a parent confirming send is refused with `sent:null`,
  `consent.authorized:false`); `/ledger` → 16 hash-chained rows (decision /
  alert / morning_run) and `/ledger/verify` → `ok:true` over those rows;
  `/outbox` → 8 alerts for the principal and officer (parent → 403);
  `/transcript` → the persisted 2-turn agent conversation; `/sources/refresh` →
  honest `frozen` fallback; unknown school → 404, no token → 401.

> The one AWS surface we avoided: Cognito's *Managed Login v1* hosted-UI page
> (a brand-new pool + domain serves a generic "An error was encountered with the
> requested page" and there is no fix short of recreating the pool). The console
> therefore logs in against `POST /login` → `AdminInitiateAuth` under
> `ALLOW_ADMIN_USER_PASSWORD_AUTH` — the same token the gateway authorizer
> already trusts — and users, passwords, and roles stay in Cognito.

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