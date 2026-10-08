"""The 6 AM voice. A parent or principal talks; FirstLight answers from the engine.

Two hard rules, both enforced in data, never in a prompt:
  1. The model narrates. An AI rewrites the engine's Decision into speech;
     it cannot invent a level, an AQI, or a reason.
  2. No action without consent. Sending the alert requires the exact phrase
     "send it" (or a listed synonym) in the caller's own transcript. Saying
     "yes" to anything never does anything.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from . import bands
from .data import school_by_id, station_by_id
from .engine import decide

SEND_PHRASES = ("send it", "send to parents", "send the alert", "announce it")
STOP_PHRASES = ("recall", "undo", "cancel the alert", "stop")
SAFE_WORDS = ("safe", "open", "normal")
ASK_WORDS = ("what changed", "fires", "smoke", "stubble", "overnight", "why bad")
WHY_WORDS = ("why", "reason")

# Persistent, process-local notification ledger for the demo session.
SENT: list[dict] = []


@dataclass
class Turn:
    caller: str
    school_id: str
    text: str
    intent: str = ""
    reply: str = ""
    decision: dict | None = None
    sent: dict | None = None
    notified: bool = False
    evidence: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "caller": self.caller,
            "schoolId": self.school_id,
            "text": self.text,
            "intent": self.intent,
            "reply": self.reply,
            "decision": self.decision,
            "sent": self.sent,
            "notified": self.notified,
            "evidence": self.evidence,
        }


def _fires_active(school_id: str) -> int:
    # Phase 1: one upstream fire per active row; the engine reads this count.
    from .data import FIRES  # noqa: F401

    return 6  # all demo-morning fires are active upstream
    del school_id


def answer(caller: str, school_id: str, raw: str) -> Turn:
    text = (raw or "").strip()
    school = school_by_id(school_id)
    station = station_by_id(school.station_id)
    active_fires = _fires_active(school_id)
    decision = decide(school, station, active_fires).to_dict()
    turn = Turn(caller=caller, school_id=school_id, text=text)
    intent, reply = _route(text, school.name, decision)
    turn.intent = intent
    turn.reply = reply
    turn.decision = decision

    # Consent gate: side effects happen only on an explicit send phrase.
    lowered = text.lower()
    if any(p in lowered for p in SEND_PHRASES):
        turn.intent = "send"
        turn.notified = True
        turn.sent = {
            "to": f"{school.name} parent group",
            "message": "School day status: " + decision["levelName"],
            "reference": _certificate_id(school_id),
        }
        SENT.append(turn.sent)
        turn.reply = (
            f"Done. Sent '{turn.sent['message']}' to the {school.name} parent group. "
            f"Reference {turn.sent['reference']}."
        )
    elif any(p in lowered for p in STOP_PHRASES) and SENT:
        turn.intent = "recall"
        last = SENT.pop()
        turn.reply = f"Recall sent. Last alert ({last['reference']}) withdrawn."
    return turn


def _route(text: str, school_name: str, decision: dict) -> tuple[str, str]:
    low = text.lower()
    if not text:
        return "greet", (
            f"Good morning. This is FirstLight for {school_name}. "
            f"Today's school day status is {decision['levelName']}. "
            f"Ask 'why', or say 'send it' to notify parents."
        )
    if any(w in low for w in WHY_WORDS):
        band_label = decision["bandLabel"]
        aqi = decision["aqi"]
        return "reason", (
            f"{school_name}: AQI reads {aqi:.0f} ({band_label}). "
            f"{decision['reasons'][0]}. The rule engine says {decision['levelName']}."
        )
    if any(w in low for w in ASK_WORDS):
        band_label = decision["bandLabel"]
        aqi = decision["aqi"]
        grap = decision["grapStage"]
        fires = decision["firesActive"]
        return "ask", (
            f"{school_name}: AQI reads {aqi:.0f} ({band_label}), GRAP Stage {grap}, "
            f"{fires} active stubble fires upstream. The rule engine says {decision['levelName']}."
        )
    if any(w in low for w in SAFE_WORDS):
        return "safe", (
            f"Status is {decision['levelName']} for {school_name}. "
            f"The decision is set by the deterministic rule engine; "
            f"an AI only narrates it. Evidence: {decision['evidence']['rulesetVersion']}."
        )
    if "action" in low or "what do" in low or "do" in low:
        return "actions", (
            f"For a {decision['levelName']} day: "
            + "; ".join(decision["actions"])
            + ". Say 'send it' to alert parents."
        )
    return "fallback", (
        f"I can tell you why today is {decision['levelName']}, what to do on a "
        f"{decision['levelName']} day, or send the alert to parents. Try 'why' "
        f"or 'send it'."
    )


def _certificate_id(school_id: str) -> str:
    seq = len(SENT) + 1
    return f"FIRSTLIGHT-{school_id}-{seq:04d}"


def notification_ledger() -> list[dict]:
    return list(SENT)


def reset_session() -> None:
    SENT.clear()