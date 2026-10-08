"""Ship It mirror of the 6 AM agent talk endpoint (with the consent gate).

Consent is decided the same way as the local build: a send intent in the same
turn AND an explicit confirmation phrase — otherwise the agent never sends.
"""

from __future__ import annotations

from firstlight.agent import ConsentState, consent_turn, parse, sign, short
from firstlight.engine import decide_school
from firstlight.pipeline.scenario import morning_inputs

from .shared import parse_body, principal_id, put_alert, respond


def handler(event: dict, _context) -> dict:
    body = parse_body(event)
    text = body.get("text", "")
    school_id = body.get("school_id", "")

    inputs = morning_inputs()
    try:
        school = next(s for s in inputs.schools if s.id == school_id)
    except StopIteration:
        return respond(404, {"error": f"no school {school_id}"})

    intent = parse(text)
    gate = consent_turn(ConsentState(), intent.name, text)
    decision = decide_school(inputs, school)

    sent = None
    if gate["maySend"]:
        cert = sign(decision, "shipit-demo-key")
        put_alert(school_id, decision.date, decision.level.name_short, cert)
        sent = {"status": "sent", "schoolId": school_id, "cert": cert}

    reply = short(school, decision) if intent.name in ("status", "unknown") else f"intent={intent.name}"

    return respond(
        200,
        {"by": principal_id(event), "intent": intent.name, "reply": reply,
         "decision": decision.to_dict(), "consent": gate, "sent": sent},
    )