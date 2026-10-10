# FirstLight — demo script (pre-recorded, ~3 minutes)

Everything below is the real running app against `pipeline/scenario.py`'s
frozen morning of **2026-10-08**. Because the scenario is frozen, the film can
be re-recorded any number of times and the verdicts never change.

## Shot 1 — the console boots (0:00–0:20)

- `py -m firstlight.cli seed` then `py -m firstlight.cli serve`.
- Browser opens `http://127.0.0.1:8000` — sign in as **officer**
  (`officer@firstlight.demo` / `officer123`). Point at **/api/health**: `ok`,
  `version 0.2.0`, `ruleset firstlight-rules-v2@2026-10`, `source frozen`.
- Say it out loud: *"No AWS account, no card, no bill — the demo makes zero
  network calls by default. The one live feed (NASA FIRMS fires) is an
  explicit officer action with a visible fallback."*

## Shot 2 — the frozen inputs (0:20–0:40)

- Console → **frozen morning inputs**: `2026-10-08`, 7 stations, 7 stubble
  fires, wind from 310° at 16 km/h. The topbar chip reads **FROZEN** and the
  Scenario card labels where every input came from and when it was observed.
- Open `pipeline/scenario.py` in the editor: 7 real-placed NCR schools,
  Punjab/Haryana fires, 7 prior mornings of history. "Ships frozen so every
  run is reproducible."

## Shot 3 — the 6 AM question (0:40–1:10)

- Pick **s-avini**, ask (as officer, or parent): *"is today safe for school?"*
- Reply pins the evidence: **AQI 442 (Severe), GRAP Stage 3, 6 upwind
  stubble fires, rising**.
- Click **run morning** (officer) → 7 schools: 5 CLOSED, 2 PROTECTED.
- "The AI narrated this — the engine decided it. There is no code path where
  the model chooses a verdict."

## Shot 4 — consent, the safety proof (1:10–1:50)

- As **principal** (`principal@firstlight.demo` / `principal123`), ask:
  *"would you send it if the air got worse?"* → status line says
  **no-send**. Freeze on this frame.
- Then: *"yes, send it"* → status flips to **CERTIFIED SEND ✓**, and the
  reply shows the receipt + delivery (`via console → receipt console-s-avini`).
- "Sending required the send intent AND an explicit confirmation in the same
  turn. A question never sends. This is unit-tested."
- (Optional beat — the role gate:) sign in as **parent**, say *"yes, send
  it"* → the agent answers "the 'parent' role cannot dispatch alerts". Roles
  are enforced end to end, not just at the API boundary.

## Shot 5 — trust, the receipts (1:50–2:10)

- **verify ledger** → `all rows hash-chained, tamper check ✓`.
- Show `tests/test_ledger.py::test_tamper_detected` editing a row → verify
  flips to false. "Any offline edit breaks the chain."
- Show the certificate object in `agent/certificate.py`: HMAC-signed, so a
  judge can verify a decision later with one command.

## Shot 6 — same engine, cloud-shaped (2:10–2:40)

- Open `firstlight/auth/cedar/policies.cedar`: "AWS **Cedar** is the
  authorization engine here — genuine AWS open source, Build It Approved."
- Open `sam/template.yaml`: Cognito ↔ parent/principal/officer, Lambda +
  DynamoDB mirror, core layer.
- `sam build-layer.ps1` + `sam validate -t sam\template.yaml` → template is
  valid today. "Ship It runs the same engine the moment the account clears;
  until then, this repo is the product."

## Shot 7 — the gate (2:40–3:00)

- `py -m firstlight.cli gate` → **151 tests, OK**.
- Close on the tagline: *"FirstLight — the 6 AM on-call agent for the air a
  child breathes."*

## The 60-second fallback (if the film must be shorter)

Shot 3 → Shot 4 (consent) → Shot 6 (Cedar/SAM) → Shot 7 (gate, 151 tests).
