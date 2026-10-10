# FirstLight — What's real, what's simulated, and where the numbers come from

Judges should never have to guess which parts of a demo are live. This file is
the honest ledger of that: every input, every constant, and its source.

## Inputs

| Input | In the demo | Live? | Source / note |
|---|---|---|---|
| Stubble fires | 7 fires, Punjab/Haryana, 07–08 Oct 2026 | **Live capable** | NASA FIRMS 24h `VIIRS_SNPP`/`MODIS` CSV — [`firstlight/pipeline/sources.py`](../firstlight/pipeline/sources.py). Deployed with `SOURCE_MODE=live`, the 6 AM schedule (and an officer's *Refresh*) fetches the live feed and records provenance (source, timestamp, count, fallback); on any failure it falls back to the frozen snapshot visibly. |
| CPCB station AQI | 7 NCR stations | **Live capable** | [`firstlight/pipeline/air.py`](../firstlight/pipeline/air.py) fetches live PM2.5/PM10 from the key-free Open-Meteo air-quality API and converts to a **CPCB statutory AQI** via the CPCB PM2.5/PM10 sub-index breakpoints (Central Pollution Control Board, *National Air Quality Index*, 2014; AQI = max sub-index). Same fallback + provenance contract as fires; cached with a 60 s backpressure floor. |
| Wind | 310°, 16 km/h | **Frozen** | Scenario constant (a real IMD observation would slot into the same spot). |
| Prior mornings | 7 daily AQIs per school | **Frozen** | Used only as the trend baseline. |
| Schools | 7 NCR schools | **Frozen** | Illustrative; not a real school directory. |

Wind, prior mornings and the school directory stay frozen so a demo is reproducible; `SOURCE_MODE=live` (the deployed default) fetches the two inputs that genuinely change — station air and stubble fires — with a visible, recorded fallback to the frozen snapshot on any failure. `/health` and the console banner label every field live-vs-frozen, so nothing is overclaimed.

## Constants and where they come from

| Constant | Value | Source |
|---|---|---|
| CPCB AQI bands | Good 0–50, Satisfactory 51–100, Moderate 101–200, Poor 201–300, Very Poor 301–400, Severe 401–500 | Central Pollution Control Board, *National Air Quality Index* (Oct 2014). See [`firstlight/engine/bands.py`](../firstlight/engine/bands.py). |
| GRAP stage triggers | I ≥ 201, II ≥ 301, III ≥ 401, IV ≥ 450 | Commission for Air Quality Management (CAQM), *Graded Response Action Plan* for Delhi-NCR. Same file. |
| Level mapping | Severe → CLOSED; Very Poor (± plume) → CLOSED/PROTECTED; Poor → PROTECTED | [`firstlight/engine/policy.py`](../firstlight/engine/policy.py), rules `R-CLOSE-*`, `R-PROTECT-*`. |
| Sensitive-school bonus | +15 effective AQI | Local policy choice (a sensitive cohort lowers the real-world trigger). Documented, not a standard. |
| Trend window / thresholds | 7 mornings; ±15 % = rising/improving | `firstlight/engine/trend.py`. Local heuristic. |
| Haversine / bearing | standard great-circle formulas | `firstlight/engine/geometry.py`. |
| IDW station interpolation | inverse-distance weighting (Shepard) over a 50 km floor | `firstlight/engine/interpolation.py`. Standard method. |
| Plume score / upwind reach | wind-vector + reach heuristic (0–3 scale) | `firstlight/engine/plume.py`. **A documented approximation**, not a dispersion model (no HYSPLIT/AERMOD). Cited in code; treat as an indicator, not a physical simulation. |

## Deliberately out of scope (and said so)

- **No foundation model decides anything.** The "agent" is deterministic
  (`firstlight/agent/`): keyword/synonym intent parsing (English + Hindi/Hinglish)
  and templated narration built from the `Decision` object. There is no
  Bedrock/Nova/LLM call in the decision or reply path. This is a feature: the
  verdict is auditable, not sampled.
- **No real SMS/voice delivery.** The notifier returns a channel receipt
  (`console-`, `webhook-`, `smtp-`); the twin wires the webhook channel via
  `ALERT_HOOK_URL`. `docs/README` claims are limited to what is provisioned.
- **No secret manager in the twin's local mode.** `FIRSTLIGHT_SECRET` has a dev
  default; production must inject it.

## Why the ledger matters here

Every decision, alert, and morning run is appended to a SHA-256 hash chain
(`firstlight/ledger/store.py`, mirrored in `sam/handlers/shared.py`). `verify()`
recomputes the chain and reports the first broken row. This is what lets the
project say "it ships the receipts" without asking you to trust it.
