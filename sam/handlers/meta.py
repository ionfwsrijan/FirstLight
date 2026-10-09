"""Console data endpoints that the local web/index.html shell expects.

The deployed console is the SAME page as the local build (web/index.html is
copied into the UiHandler bundle), so this handler exposes the exact route
contract the page fetches, minus the leading /api:

  GET  /health            liveness + ruleset + source provenance (public)
  GET  /inputs            morning inputs as frozen scenario + provenance
  GET  /schools           all schools
  GET  /decisions/{id}    latest saved decisions for a school
  GET  /transcript        persisted agent conversation
  GET  /ledger            recent hash-chained ledger rows (officer)
  GET  /ledger/verify     recompute the hash chain (officer)
  GET  /outbox            delivered alerts, channel + receipt (principal/officer)
  POST /sources/refresh   explicit FIRMS refresh (officer) — honest frozen stub
"""

from __future__ import annotations

import os

from firstlight.pipeline.scenario import morning_inputs

try:
    from .shared import (
        _FALLBACK_STATUS,
        cognito_role,
        decisions_for,
        ledger_entries,
        ledger_verify,
        outbox_messages,
        principal_id,
        respond,
        transcript_turns,
    )
except ImportError:  # Lambda treats handlers/ as the code root (no package parent)
    from shared import (
        _FALLBACK_STATUS,
        cognito_role,
        decisions_for,
        ledger_entries,
        ledger_verify,
        outbox_messages,
        principal_id,
        respond,
        transcript_turns,
    )

_VERSION = "0.2.0"


def _health() -> dict:
    return {
        "ok": True,
        "app": "FirstLight",
        "version": _VERSION,
        "ruleset": os.environ.get("RULESET_VERSION", ""),
        "source": dict(_FALLBACK_STATUS),
    }


def _refresh_stub() -> dict:
    status = dict(_FALLBACK_STATUS)
    status["fallback"] = True
    status["error"] = (
        "live NASA FIRMS refresh is a Build It local feature; "
        "the mirror serves the deterministic frozen scenario"
    )
    return status


def _require(event: dict, *roles: str):
    role = cognito_role(event)
    if role not in roles:
        return respond(403, {"detail": f"role {role} cannot use this endpoint"})
    return None


def handler(event: dict, _context) -> dict:
    method = event.get("httpMethod", "GET")
    path = (event.get("path") or "").rstrip("/") or "/"

    # Public: used by the login overlay before any token exists.
    if method == "GET" and path == "/health":
        return respond(200, _health())

    described = [
        ("GET", "/inputs"),
        ("GET", "/schools"),
        ("GET", "/transcript"),
        ("GET", "/ledger"),
        ("GET", "/ledger/verify"),
        ("GET", "/outbox"),
        ("POST", "/sources/refresh"),
    ]
    is_described = (method, path) in described or (
        method == "GET" and path.startswith("/decisions/")
    )
    if not is_described:
        return respond(404, {"error": f"no such endpoint /login{path}"})

    inputs = morning_inputs()

    if method == "GET" and path == "/inputs":
        payload = inputs.to_dict()
        payload["source"] = dict(_FALLBACK_STATUS)
        return respond(200, payload)

    if method == "GET" and path == "/schools":
        return respond(200, {"schools": [s.to_dict() for s in inputs.schools]})

    if method == "GET" and path.startswith("/decisions/"):
        school_id = (event.get("pathParameters") or {}).get("schoolId", "")
        if not school_id:
            return respond(400, {"error": "schoolId is required"})
        return respond(200, {"schoolId": school_id, "decisions": decisions_for(school_id)})

    if method == "GET" and path == "/transcript":
        params = event.get("queryStringParameters") or {}
        school_id = params.get("school_id", "")
        if not school_id:
            return respond(400, {"error": "school_id is required"})
        return respond(200, {"turns": transcript_turns(school_id, principal_id(event))})

    if method == "GET" and path == "/outbox":
        blocked = _require(event, "principal", "officer")
        if blocked:
            return blocked
        return respond(200, {"messages": outbox_messages(25)})

    if method == "GET" and path in ("/ledger", "/ledger/verify"):
        blocked = _require(event, "officer")
        if blocked:
            return blocked
        if path == "/ledger/verify":
            return respond(200, ledger_verify())
        return respond(200, {"entries": ledger_entries(25)})

    if method == "POST" and path == "/sources/refresh":
        blocked = _require(event, "officer")
        if blocked:
            return blocked
        return respond(200, _refresh_stub())

    return respond(404, {"error": f"no such endpoint {method} {path}"})