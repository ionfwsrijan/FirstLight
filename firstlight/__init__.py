"""FirstLight: the 6 AM on-call agent for the air a child breathes.

A deterministic, evidence-first engine decides whether a school morning is
SAFE / PROTECTED / CLOSED. CPSB-approved AQI bands and the GRAP action plan
are codified as open rule tables; an AI only narrates what the engine already
decided. No decision is ever produced by a model, a prompt, or a coin toss.

Layers:
  domain       pure data types, no IO
  engine       deterministic rules, geometry, interpolation, plume, trend
  dsl          declarative rule chain evaluated like a small language
  ledger       append-only, hash-chained event log (tamper-evident)
  auth         HMAC capability tokens + role matrix + Cedar policies
  agent        intent parsing, narration, consent gate, certificates
  notifier     dispatch channel abstraction (console / smtp / webhook)
  storage      sqlite persistence + repositories
  pipeline     the scheduled morning run (fetch -> decide -> notify)
  api          FastAPI runtime for Build It local mode
  cli          run / seed / gate entrypoints
"""

__version__ = "0.2.0"
RULESET_VERSION = "firstlight-rules-v2@2026-10"
