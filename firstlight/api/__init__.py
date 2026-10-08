"""FastAPI application for Build It local mode.

Endpoints:
  GET  /api/health            liveness + ruleset version
  GET  /api/morning/inputs    the frozen scenario (judge-facing)
  POST /api/morning/run       run the deterministic morning (officer)
  GET  /api/schools           all schools
  GET  /api/decisions/{school_id}   latest decisions for a school
  POST /api/agent/talk        one turn of the 6 AM agent (with consent)
  GET  /api/ledger            recent ledger rows
  GET  /api/ledger/verify     tamper check
  POST /api/auth/issue        issue a capability token (demo creds)
"""

from __future__ import annotations

import logging
import sqlite3
from contextlib import asynccontextmanager
from typing import Annotated

from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel

from .. import RULESET_VERSION
from ..agent import ConsentState, consent_turn, parse, short, sign
from ..auth import allowed, issue, verify
from ..config import settings
from ..engine import decide_school
from ..ledger import Ledger
from ..pipeline import run_morning
from ..pipeline.scenario import morning_inputs
from ..storage import DecisionsRepo, SchoolsRepo, connect

log = logging.getLogger("firstlight.api")


@asynccontextmanager
async def lifespan(_app: FastAPI):
    if settings.auto_seed and not settings.db_exists:
        from ..cli.seed import seed

        seed()
        log.info("auto-seeded %s", settings.db_path)
    yield


app = FastAPI(title=settings.app_name, version=settings.version, lifespan=lifespan)


class AuthPayload(BaseModel):
    sub: str
    role: str


class TalkPayload(BaseModel):
    text: str
    school_id: str
    caller: str = "parent"


def _db() -> sqlite3.Connection:
    return connect(settings.db_path)


def _auth(authorization: Annotated[str | None, Header()] = None) -> dict:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="missing bearer token")
    claims = verify(authorization.removeprefix("Bearer "), settings.secret)
    if claims is None:
        raise HTTPException(status_code=401, detail="invalid or expired token")
    return claims


def _require(claims: dict, *actions: str) -> dict:
    for a in actions:
        if allowed(claims["role"], a):
            return claims
    raise HTTPException(status_code=403, detail=f"role {claims['role']} cannot {actions}")


@app.get("/api/health")
def health() -> dict:
    return {"ok": True, "app": settings.app_name, "version": settings.version, "ruleset": RULESET_VERSION}


@app.get("/")
def console() -> FileResponse:
    index = settings.web_dir / "index.html"
    if not index.exists():
        raise HTTPException(status_code=404, detail="web console not built yet")
    return FileResponse(index)


@app.get("/api/morning/inputs")
def get_inputs() -> dict:
    return morning_inputs().to_dict()


@app.post("/api/morning/run")
def run(claims: Annotated[dict, Depends(_auth)]) -> dict:
    _require(claims, "run:morning")
    conn = connect(settings.db_path)
    result = run_morning(conn, settings, morning_inputs(), as_user=claims["sub"])
    conn.close()
    return result.to_dict()


@app.get("/api/schools")
def schools(claims: Annotated[dict, Depends(_auth)]) -> dict:
    _require(claims, "school:read")
    conn = _db()
    rows = SchoolsRepo(conn).all()
    conn.close()
    return {"schools": [s.to_dict() for s in rows]}


@app.get("/api/decisions/{school_id}")
def decisions_for_school(school_id: str, claims: Annotated[dict, Depends(_auth)]) -> dict:
    _require(claims, "school:read")
    conn = _db()
    rows = DecisionsRepo(conn).for_school(school_id)
    conn.close()
    return {"schoolId": school_id, "decisions": rows}


@app.post("/api/agent/talk")
def talk(payload: TalkPayload, claims: Annotated[dict, Depends(_auth)]) -> dict:
    _require(claims, "agent:talk")
    state = ConsentState()
    intent = parse(payload.text)
    gate = consent_turn(state, intent.name, payload.text)

    inputs = morning_inputs()
    school = next(s for s in inputs.schools if s.id == payload.school_id)
    decision = decide_school(inputs, school)

    if intent.name == "status":
        reply = short(school, decision)
    elif intent.name == "why":
        fired = [r for r in decision.reasons if r.applied]
        reply = " ".join(f"{r.rule_id}: {r.detail}" for r in fired) or "No specific rule fired."
    elif intent.name == "change":
        ev = decision.evidence
        plume = ev["plume"]
        reply = (
            f"Overnight changes: {plume['upwindFires']} stubble fires upwind, plume {plume['score']:.2f}; "
            f"AQI {ev['trend']['delta']:+.0f} vs the {ev['trend']['baseline']:.0f} baseline."
        )
    elif intent.name == "actions":
        reply = "; ".join(decision.actions) if decision.actions else "Open normally."
    elif intent.name == "greet":
        reply = (
            f"Good morning. I'm FirstLight for {school.name}. "
            f"Today's status: {decision.level.name_short}. Ask 'why?', or say 'send' to alert parents."
        )
    elif intent.name == "send":
        reply = "Confirmed. I'll only send after you explicitly say 'yes, send it' in this turn."
    elif intent.name == "recall":
        reply = "The alert can be retracted. Say 'withdraw the alert' to confirm the recall."
    else:
        reply = short(school, decision)

    sent: dict | None = None
    if gate["maySend"]:
        conn = _db()
        cert = sign(decision, settings.secret)
        Ledger(conn).append("alert", school.id, {"level": decision.level.name_short, "cert": cert})
        conn.commit()
        conn.close()
        sent = {"cert": cert, "status": "sent", "schoolId": school.id}

    return {
        "intent": intent.name,
        "reply": reply,
        "decision": decision.to_dict(),
        "consent": gate,
        "sent": sent,
        "recoverable": decision.level.name_short != "GREEN",
    }


@app.get("/api/ledger")
def ledger_rows(claims: Annotated[dict, Depends(_auth)]) -> dict:
    _require(claims, "ledger:read")
    conn = _db()
    rows = _ledger(conn).entries(limit=25)
    conn.close()
    return {"entries": rows}


@app.get("/api/ledger/verify")
def ledger_verify(claims: Annotated[dict, Depends(_auth)]) -> dict:
    _require(claims, "ledger:read")
    conn = _db()
    result = _ledger(conn).verify()
    conn.close()
    return result


def _ledger(conn: sqlite3.Connection) -> Ledger:
    return Ledger(conn)


@app.post("/api/auth/issue")
def issue_token(payload: AuthPayload) -> JSONResponse:
    # Demo-only credential issue. Ship It uses Cognito; see sam/template.yaml.
    if payload.role not in ("parent", "principal", "officer"):
        raise HTTPException(status_code=400, detail="unknown role")
    token = issue(payload.sub, payload.role, settings.secret, settings.token_ttl_seconds)
    return JSONResponse({"token": token, "role": payload.role, "sub": payload.sub})


@app.get("/api/me")
def me(claims: Annotated[dict, Depends(_auth)]) -> dict:
    return {"sub": claims["sub"], "role": claims["role"]}