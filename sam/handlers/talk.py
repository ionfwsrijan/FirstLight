"""Ship It mirror of the 6 AM agent talk endpoint (with the consent gate).

Consent is decided the same way as the local build: a send intent in the same
turn AND an explicit confirmation phrase — otherwise the agent never sends.
Role enforcement also mirrors the local console: only a principal or officer
may dispatch; a parent's confirmed send is denied by the role gate
("ROLE CANNOT SEND") and nothing is sent.
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
    send_denied_reply,
    short,
    sign,
    status_reply,
    why_reply,
)
from firstlight.engine import decide_school
from firstlight.pipeline.scenario import morning_inputs

try:
    from .shared import (
        append_turns,
        cognito_role,
        notify_webhook,
        now_utc,
        parse_body,
        principal_id,
        put_alert,
        respond,
    )
except ImportError:  # Lambda treats handlers/ as the code root (no package parent)
    from shared import (
        append_turns,
        cognito_role,
        notify_webhook,
        now_utc,
        parse_body,
        principal_id,
        put_alert,
        respond,
    )

_SEND_ROLES = ("principal", "officer")


def handler(event: dict, _context) -> dict:
    body = parse_body(event)
    text = body.get("text", "")
    school_id = body.get("school_id", "")

    inputs = morning_inputs()
    try:
        school = next(s for s in inputs.schools if s.id == school_id)
    except StopIteration:
        return respond(404, {"error": f"no school {school_id}"})

    who = principal_id(event)
    role = cognito_role(event)

    intent = parse(text)
    gate = consent_turn(ConsentState(), intent.name, text)
    gate["authorized"] = role in _SEND_ROLES
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
        if not gate["authorized"]:
            reply = send_denied_reply(school, role)
        else:
            message = f"{decision.level.name_short}: {short(school, decision)}"
            receipt = notify_webhook(decision.level.name_short, message)
            channel = "webhook" if receipt.startswith("hook") else "noop"
            alert_id = put_alert(
                school_id, decision.date, decision.level.name_short, cert,
                message, channel, receipt, who, now_utc(),
            )
            sent = {"status": "sent", "schoolId": school_id, "cert": cert,
                    "delivery": {"channel": channel, "receipt": receipt, "alertId": alert_id}}
            reply = send_confirmed_reply(school, decision, cert, channel, receipt)

    turn = append_turns(school_id, who, text, intent.name, reply, intent.name)

    return respond(
        200,
        {"by": who, "intent": intent.name, "reply": reply,
         "decision": decision.to_dict(), "consent": gate, "sent": sent,
         "recoverable": decision.level.name_short != "GREEN", "turn": turn},
    )
