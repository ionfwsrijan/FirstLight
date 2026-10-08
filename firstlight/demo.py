"""The scripted morning: the judge-facing film runs this and it cannot fail.

Deterministic dialogue through the same code path a human would use. No live
APIs, no tokens, no account. The verdict is whatever the engine already said.
"""

from __future__ import annotations

from . import agent
from .data import SCHOOLS, school_by_id


def run(school_id: str = SCHOOLS[0].id) -> dict:
    agent.reset_session()
    school = school_by_id(school_id)

    script = [
        ("parent", "good morning — is today safe for school?"),
        ("parent", "why?"),
        ("parent", "what do we do"),
        ("parent", "send it"),
        ("official", "cancel the alert"),
        ("official", "send the alert"),
    ]

    turns = []
    for caller, text in script:
        turn = agent.answer(caller, school_id, text)
        turns.append(
            {
                "caller": caller,
                "text": text,
                "intent": turn.intent,
                "reply": turn.reply,
                "decision": turn.decision,
                "sent": turn.sent,
                "notified": turn.notified,
            }
        )
    return {
        "schoolName": school.name,
        "schoolId": school_id,
        "date": "2026-10-08",
        "town": "NCR",
        "turns": turns,
    }


def main() -> None:
    result = run()
    print(f"\nFIRSTLIGHT — {result['schoolName']} · {result['date']}\n")
    for t in result["turns"]:
        who = "you" if t["caller"] == "parent" else "official"
        print(f'  [{t["intent"]:>8}] {who:<8} "{t["text"]}"')
        print(f"  {t['reply'][:220]}\n")


if __name__ == "__main__":
    main()