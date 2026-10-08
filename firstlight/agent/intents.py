"""Intents: map a caller's natural language to a structured intent.

Deterministic keyword/synonym recognition supporting Hindi and Hinglish
mixes, since the school gate is answered in the caller's own language. No
model involved — an LLM may later paraphrase, but the intent is decided here.

Intents: greet, status, why, change, actions, send, recall, unknown
"""

from __future__ import annotations

from dataclasses import dataclass

STATUS_WORDS = (
    "safe", "status", "school", "kal", "aaj", "shaadi", "open",
    "today", "morning", "bache", "bacche", "schooli", "kesa", "kaisa",
)
WHY_WORDS = ("why", "kya", "kyun", "reason", "kaise", "hmm", "because", "warna")
CHANGE_WORDS = ("what changed", "change", "badla", "kya hua", "fires", "fire", "stubble", "smoke", "smog", "dhan", "dhua")
ACTIONS_WORDS = ("what do", "kya kare", "do we", "action", "actions", "kya kar", "steps")
SEND_WORDS = ("send it", "send", "bhejo", "alert", "announce", "notify", "inform", "intimate")
RECALL_WORDS = ("recall", "cancel", "undo", "stop it", "wapis", "rok do", "withdraw")
GREET_WORDS = ("good morning", "hi", "hello", "namaste", "salaam", "hey", "namaskar")


@dataclass(frozen=True)
class Intent:
    name: str
    original: str
    matched_words: tuple[str, ...]

    def to_dict(self) -> dict:
        return {"name": self.name, "original": self.original, "matched": list(self.matched_words)}


def parse(text: str) -> Intent:
    t = (text or "").lower().strip()
    if not t:
        return Intent("greet", text, ())
    if any(w in t for w in WHY_WORDS):
        return Intent("why", text, tuple(w for w in WHY_WORDS if w in t))
    if any(w in t for w in CHANGE_WORDS):
        return Intent("change", text, tuple(w for w in CHANGE_WORDS if w in t))
    if any(w in t for w in RECALL_WORDS):
        return Intent("recall", text, tuple(w for w in RECALL_WORDS if w in t))
    if any(w in t for w in SEND_WORDS):
        return Intent("send", text, tuple(w for w in SEND_WORDS if w in t))
    if any(w in t for w in ACTIONS_WORDS):
        return Intent("actions", text, tuple(w for w in ACTIONS_WORDS if w in t))
    if any(w in t for w in STATUS_WORDS):
        return Intent("status", text, tuple(w for w in STATUS_WORDS if w in t))
    if any(w in t for w in GREET_WORDS):
        return Intent("greet", text, tuple(w for w in GREET_WORDS if w in t))
    return Intent("unknown", text, ())