"""Console data endpoints that the local web/index.html shell expects.

The deployed console is the SAME page as the local build (web/index.html is
copied into the UiHandler bundle), so this handler exposes the exact route
contract the page fetches. The paths mirror the local `/api/*` surface exactly
(the same console calls the same URLs against both); a leading `/api` is
stripped here so the handler also answers bare `/health` etc. for manual calls:

  GET  /api/health            liveness + ruleset + per-field provenance (public)
  GET  /api/morning/inputs    morning inputs (live sources when refreshed) + provenance
  GET  /api/schools           all schools
  GET  /api/decisions/{id}    latest saved decisions for a school
  GET  /api/transcript        persisted agent conversation
  GET  /api/ledger            recent hash-chained ledger rows (officer)
  GET  /api/ledger/verify     recompute the hash chain (officer)
  GET  /api/outbox            delivered alerts, channel + receipt (principal/officer)

This handler is read-only: the officer-only POST /sources/refresh lives in its
own function (sources.py) so it can carry a scoped read/write policy while this
one keeps a read-only grant.
"""

from __future__ import annotations

import os

try:  # Lambda treats handlers/ as the code root (no package parent)
    from .shared import (
        cognito_role,
        decisions_for,
        effective_inputs_dyn,
        ledger_entries,
        ledger_verify,
        outbox_messages,
        principal_id,
        respond,
        source_status_dyn,
        transcript_turns,
    )
except ImportError:
    from shared import (
        cognito_role,
        decisions_for,
        effective_inputs_dyn,
        ledger_entries,
        ledger_verify,
        outbox_messages,
        principal_id,
        respond,
        source_status_dyn,
        transcript_turns,
    )

_VERSION = "0.2.0"


def _health() -> dict:
    return {
        "ok": True,
        "app": "FirstLight",
        "version": _VERSION,
        "ruleset": os.environ.get("RULESET_VERSION", ""),
        "source": _fires_view(),
        "sources": source_status_dyn(),
    }


def _fires_view() -> dict:
    fields = source_status_dyn()["fires"]
    return {
        "source": "frozen" if not fields["live"] else "live",
        "label": fields["provider"],
        "fetchedAt": fields["fetchedAt"],
        "count": fields["count"],
        "fallback": fields["fallback"],
        "error": fields["error"],
    }


def _require(event: dict, *roles: str):
    role = cognito_role(event)
    if role not in roles:
        return respond(403, {"detail": f"role {role} cannot use this endpoint"})
    return None


def handler(event: dict, _context) -> dict:
    method = event.get("httpMethod", "GET")
    path = (event.get("path") or "").rstrip("/") or "/"
    if path == "/api" or path.startswith("/api/"):
        path = path[4:] or "/"
    if path == "/morning/inputs":
        path = "/inputs"

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
    ]
    is_described = (method, path) in described or (
        method == "GET" and path.startswith("/decisions/")
    )
    if not is_described:
        return respond(404, {"error": f"no such endpoint {method} {path}"})

    inputs = effective_inputs_dyn()

    if method == "GET" and path == "/inputs":
        payload = inputs.to_dict()
        payload["source"] = _fires_view()
        payload["sources"] = source_status_dyn()
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

    return respond(404, {"error": f"no such endpoint {method} {path}"})
