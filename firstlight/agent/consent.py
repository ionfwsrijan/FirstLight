"""Consent gate: sending never happens unless the caller says the words.

Safety model from the transcript — not from a model's opinion of what the
user "meant". The gate is: the send intent must be in the current turn, and
the caller must also have an explicit confirmation phrase ("yes send",
"confirm", "bhejo"). This prevents an over-eager agent from acting on an
"are you going to send it?" question.

State is per-session; the caller is whoever owns the current API token.
"""

from __future__ import annotations

from dataclasses import dataclass, field

CONFIRM_WORDS = ("yes", "confirm", "ok", "haan", "bhejo", "send it")
QUESTION_MARKERS = ("?", "would you", "can you", "are you", "should i", "should we", "if i", "would we", "could you")
SEND_REQUIRES_OWN_TURN = True  # belief of consent cannot be inherited from earlier turns


@dataclass
class ConsentState:
    last_intent: str = ""
    pending_send: bool = False
    greeting_seen: bool = False
    sent_events: list[str] = field(default_factory=list)

    def observe(self, intent: str, raw: str) -> dict:
        """Update state from a turn; returns {maySend, asked, confirmed}."""
        t = (raw or "").lower()
        is_question = any(m in t for m in QUESTION_MARKERS)
        asked = "send" in intent and any(w in t for w in ("send", "bhejo"))
        confirmed = any(w in t for w in CONFIRM_WORDS) and not is_question
        may_send = asked and confirmed and SEND_REQUIRES_OWN_TURN
        self.last_intent = intent
        if asked:
            self.pending_send = True
        if may_send:
            self.pending_send = False
        return {"maySend": may_send, "asked": asked, "confirmed": confirmed, "pendingSend": self.pending_send}


def consent_turn(state: ConsentState, intent: str, raw: str) -> dict:
    return state.observe(intent, raw)