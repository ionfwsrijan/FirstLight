# FirstLight — Validity model: logic, not likelihood

FirstLight is a **rule-executor, not a predictor**. That distinction is the
whole validity story, and it is the honest answer to "where's your backtest?"

A *predictor* is trained on historical outcomes, generalizes, drifts, and
needs re-validation. FirstLight is none of those things: it executes the
**published** CPCB bands and CAQM GRAP stages against this morning's observed
air and fires, and emits a verdict with a trace and a signed receipt. It has
no training data, no parameters, no model weights, and — by design — nothing
to drift.

## What we assert, and how you can check it yourself

| Claim | Proof | Reproduce it |
|---|---|---|
| The full seeded morning produces exactly the verdicts derivable by hand from the published thresholds | **Golden-morning test** (`tests/test_golden_morning.py`) locks 2026-10-08 to 5 CLOSED / 2 PROTECTED, each verdict annotated with the station AQI → band → deciding rule | `py -m firstlight.cli gate` (run 2) then read the sheet at the top of `tests/test_golden_morning.py` next to the CPCB/GRAP tables in `firstlight/engine/policy.py` |
| The deciding rule for every school is identifiable and quotable | every `Decision` carries a full rule trace (`R-CLOSE-401`, `R-CLOSE-VP-PLUME`, `R-PROTECT-201`, …) and the ledger stores it | open any live receipt in the console — it names the rule and the AQI |
| The cloud output is byte-for-byte the local output | **Parity test** (`tests/test_sam_mirror.py`) flips `SOURCE_MODE` and asserts identical payloads — the same engine ships as a Lambda layer | `pytest tests/test_sam_mirror.py` |
| Verdicts are deterministic and tamper-evident | same input → same decision hash, every run, on any fresh database; the ledger is hash-chained and verified after every morning | `pytest tests/test_golden_morning.py tests/test_ledger.py` |
| The whole behavior is regression-locked | 163 tests across the DSL, interpolation, plume, trend, bands, auth (Cedar), consent, ledger, API, and the AWS mirror — run in CI on every push | `py -m firstlight.cli gate` |

## What we explicitly do NOT claim

- **No historical backtest.** We do not claim "the engine correctly called
  closures on date X." Falsely presenting a backtest here would cheat the
  audit chain that is the product. If you want to see the rules check against
  real history, supply the closure dates + station AQIs and the engine will
  replay them — deterministically, with the same receipts. The mechanism is
  open; the data is yours.
- **No predictive skill.** AQI thresholds are legal policy, not a forecast.
  When the rules change, you edit the DSL — you do not retrain anything.
- **No AI in the decision.** An LLM lives only in the narrating layer. Every
  verdict is produced by rules you can read in one file, and no prompt can
  overwrite it — the decision is consistent, traced, and audited, while
  authorized officials (principal, officer) remain accountable: nothing
  dispatches without their explicit confirmation, and the review path (re-run
  the morning, read the receipt) stays ordinary.

## Why that is stronger than a backtest

A model that "got it right 14 of 16 days" is *evidence about the model*.
FirstLight doesn't need evidence about itself at inference time: its contract
is **the same input implies the same verdict, forever, on laptop and on AWS,
with the public rules as the sole authority**. That is a guarantee, not a
statistic — and the judge can verify it live, today, without trusting us.