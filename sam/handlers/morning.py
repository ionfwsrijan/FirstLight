"""Ship It mirror of FIRSTLIGHT pipeline/morning.py.

Uses the frozen scenario for date 2026-10-08 (same as the local build) so the
demo and the deployed twin show identical verdicts.
"""

from __future__ import annotations

from firstlight.agent import narrate, sign
from firstlight.engine import decide_all
from firstlight.pipeline.scenario import morning_inputs

from .shared import get_latest, parse_body, principal_id, put_alert, put_decision, respond, notify_webhook


def handler(event: dict, _context) -> dict:
    """POST /morning — decide every school, persist to DynamoDB, alert."""
    inputs = morning_inputs()

    summary = {"date": inputs.date, "decisions": [], "alerts": []}
    for decision in decide_all(inputs):
        summary["decisions"].append(decision.to_dict())
        put_decision(decision.school_id, decision.to_dict())

        if decision.level.name_short in ("PROTECTED", "CLOSED"):
            school = next(s for s in inputs.schools if s.id == decision.school_id)
            message = narrate(school, decision)
            cert = sign(decision, "shipit-demo-key")
            receipt = notify_webhook(decision.level.name_short, message)
            put_alert(decision.school_id, decision.date, decision.level.name_short, cert)
            summary["alerts"].append({"schoolId": decision.school_id, "level": decision.level.name_short, "receipt": receipt})

    return respond(200, {"ok": True, "by": principal_id(event), **summary})


def status_handler(event: dict, _context) -> dict:
    """GET /status?schoolId=... — latest decision for a school."""
    params = event.get("queryStringParameters") or {}
    school_id = params.get("schoolId", "")
    if not school_id:
        return respond(400, {"error": "schoolId is required"})
    decision = get_latest(school_id)
    if decision is None:
        return respond(404, {"error": f"no decision for {school_id}"})
    return respond(200, {"schoolId": school_id, "decision": decision})