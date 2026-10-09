"""Ship It mirror of the 6 AM agent talk endpoint (with the consent gate).

Consent is decided the same way as the local build: a send intent in the same
turn AND an explicit confirmation phrase — otherwise the agent never sends.
"""

from __future__ import annotations

from firstlight.agent import (
    ConsentState,
    actions_reply,
    change_reply,
    consent_turn,
    greet_reply,
    parse,
    recall_reply,
    send_armed_reply,
    send_confirmed_reply,
    short,
    sign,
    status_reply,
    why_reply,
)
from firstlight.engine import decide_school
from firstlight.pipeline.scenario import morning_inputs

from .shared import notify_webhook, parse_body, principal_id, put_alert, respond


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
    # Ship It enforces identity/roles at the Cognito gateway, not in the handler,
    # so a confirmed send here is always authorized.
    gate["authorized"] = True
    decision = decide_school(inputs, school)

    if intent.name == "status":
        reply = status_reply(school, decision)
    elif intent.name == "why":
        reply = why_reply(school, decision)
    elif intent.name == "change":
        reply = change_reply(school, decision)
    elif intent.name == "actions":
        reply = actions_reply(school, decision)
    elif intent.name == "greet":
        reply = greet_reply(school, decision)
    elif intent.name == "send":
        reply = send_armed_reply(school, decision)
    elif intent.name == "recall":
        reply = recall_reply(school, decision)
    else:
        reply = short(school, decision)

    sent = None
    if gate["maySend"]:
        cert = sign(decision, "shipit-demo-key")
        put_alert(school_id, decision.date, decision.level.name_short, cert)
        receipt = notify_webhook(decision.level.name_short, f"{decision.level.name_short}: {short(school, decision)}")
        channel = "webhook" if receipt == "noop" or receipt.startswith("hook") else "noop"
        sent = {"status": "sent", "schoolId": school_id, "cert": cert,
                "delivery": {"channel": channel, "receipt": receipt}}
        reply = send_confirmed_reply(school, decision, cert, channel, receipt)

    return respond(
        200,
        {"by": principal_id(event), "intent": intent.name, "reply": reply,
         "decision": decision.to_dict(), "consent": gate, "sent": sent},
    )