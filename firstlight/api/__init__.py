"""FastAPI application for Build It local mode.

Endpoints:
  GET  /api/health            liveness + ruleset version + data provenance
  GET  /api/morning/inputs    scenario inputs (frozen + provenance label)
  POST /api/morning/run       run the morning on current inputs (officer)
  POST /api/sources/refresh   explicit NASA FIRMS refresh (officer)
  GET  /api/schools           all schools
  GET  /api/decisions/{school_id}   latest decisions for a school
  POST /api/agent/talk        one turn of the 6 AM agent (consent + transcript)
  GET  /api/transcript        persisted agent conversation (agent:talk)
  GET  /api/outbox            delivered alerts, channel + receipt (alert:send)
  GET  /api/ledger            recent ledger rows
  GET  /api/ledger/verify     tamper check
  POST /api/auth/login        seeded password login (Build It; Ship It uses Cognito)
  POST /api/auth/issue        disabled: open role minting is closed (403)
  GET  /api/me                current identity
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
from ..agent import (
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
from ..auth import allowed, authenticate, issue, seed_users, verify
from ..config import settings
from ..engine import decide_school
from ..ledger import Ledger
from ..notifier import build as build_notifier
from ..pipeline import effective_inputs_live, run_morning, source_status
from ..pipeline.air import refresh_air
from ..pipeline.sources import read_status
from ..pipeline.sources import refresh as refresh_fire_source
from ..storage import AlertsRepo, DecisionsRepo, SchoolsRepo, TranscriptRepo, UsersRepo, connect

log = logging.getLogger("firstlight.api")


@asynccontextmanager
async def lifespan(_app: FastAPI):
    if settings.auto_seed and not settings.db_exists:
        from ..cli.seed import seed

        seed()
        log.info("auto-seeded %s", settings.db_path)
    # demo accounts: idempotent upsert, so every boot restores the published creds
    conn = connect(settings.db_path)
    seed_users(conn)
    conn.commit()
    conn.close()
    yield


app = FastAPI(title=settings.app_name, version=settings.version, lifespan=lifespan)


class LoginPayload(BaseModel):
    username: str
    password: str


class TalkPayload(BaseModel):
    text: str
    school_id: str


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
    conn = _db()
    try:
        source = read_status(conn)
        sources = source_status(conn)
    finally:
        conn.close()
    return {
        "ok": True,
        "app": settings.app_name,
        "version": settings.version,
        "ruleset": RULESET_VERSION,
        "source": source,
        "sources": sources,
    }


@app.get("/")
def console() -> FileResponse:
    index = settings.web_dir / "index.html"
    if not index.exists():
        raise HTTPException(status_code=404, detail="web console not built yet")
    return FileResponse(index)


@app.get("/api/morning/inputs")
def get_inputs() -> dict:
    conn = _db()
    try:
        inputs, provenance = effective_inputs_live(conn)
        sources = source_status(conn)
    finally:
        conn.close()
    payload = inputs.to_dict()
    payload["source"] = provenance["fires"]
    payload["sources"] = sources
    return payload


@app.post("/api/morning/run")
def run(claims: Annotated[dict, Depends(_auth)]) -> dict:
    _require(claims, "run:morning")
    conn = _db()
    inputs, provenance = effective_inputs_live(conn)
    result = run_morning(conn, settings, inputs, as_user=claims["sub"])
    conn.close()
    out = result.to_dict()
    out["source"] = provenance["fires"]
    return out


@app.post("/api/sources/refresh")
def sources_refresh(claims: Annotated[dict, Depends(_auth)]) -> dict:
    _require(claims, "run:morning")  # officer only
    conn = _db()
    try:
        fires = refresh_fire_source(conn)
        air = refresh_air(conn)
        sources = source_status(conn)
    finally:
        conn.close()
    log.info("source refresh -> fires=%s(%s) air=%s(%s)", fires["source"], fires["count"], air["source"], air["count"])
    return {**fires, "air": air, "sources": sources}


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
    conn = _db()
    try:
        caller = claims["sub"]
        intent = parse(payload.text)

        inputs, provenance = effective_inputs_live(conn)
        school = next((s for s in inputs.schools if s.id == payload.school_id), None)
        if school is None:
            raise HTTPException(status_code=404, detail=f"no school {payload.school_id}")
        decision = decide_school(inputs, school)

        # server-side transcript replays prior *user* turns into the consent gate,
        # so "yes, send it" still needs the send-intent in the same turn (see
        # consent.SEND_REQUIRES_OWN_TURN) while pendingSend survives a reload.
        transcripts = TranscriptRepo(conn)
        state = ConsentState()
        for row in transcripts.user_turns(caller, payload.school_id):
            state.observe(row["intent"], row["text"])
        gate = consent_turn(state, intent.name, payload.text)
        gate["authorized"] = allowed(claims["role"], "alert:send")

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

        sent: dict | None = None
        if gate["maySend"]:
            if not gate["authorized"]:
                reply = send_denied_reply(school, claims["role"])
            else:
                cert = sign(decision, settings.secret)
                message = f"{decision.level.name_short}: {short(school, decision)}"
                channel = settings.notify_channel
                receipt = build_notifier(channel, settings).notify(
                    school_id=school.id, level=decision.level.name_short, message=message
                )
                alert_id = AlertsRepo(conn).save_alert(
                    school.id,
                    decision.date,
                    int(decision.level),
                    decision.level.name_short,
                    message,
                    caller,
                    cert,
                    channel=channel,
                    receipt=receipt,
                )
                Ledger(conn).append(
                    "alert",
                    school.id,
                    {"alertId": alert_id, "level": decision.level.name_short, "cert": cert, "channel": channel, "receipt": receipt},
                )
                sent = {
                    "cert": cert,
                    "status": "sent",
                    "schoolId": school.id,
                    "delivery": {"channel": channel, "receipt": receipt, "alertId": alert_id},
                }
                reply = send_confirmed_reply(school, decision, cert, channel, receipt)

        turn = transcripts.next_turn(caller, payload.school_id)
        transcripts.append(caller, payload.school_id, turn, "user", payload.text, intent.name)
        transcripts.append(caller, payload.school_id, turn, "agent", reply, intent.name)
        conn.commit()

        return {
            "intent": intent.name,
            "reply": reply,
            "decision": decision.to_dict(),
            "consent": gate,
            "sent": sent,
            "recoverable": decision.level.name_short != "GREEN",
            "source": provenance,
            "turn": turn,
        }
    finally:
        conn.close()


@app.get("/api/transcript")
def transcript(
    claims: Annotated[dict, Depends(_auth)],
    school_id: str = "",
) -> dict:
    _require(claims, "agent:talk")
    conn = _db()
    rows = TranscriptRepo(conn).recent(claims["sub"], school_id)
    conn.close()
    return {
        "turns": [
            {
                "id": r["id"],
                "turn": r["turn"],
                "speaker": r["speaker"],
                "intent": r["intent"],
                "text": r["text"],
                "createdUtc": r["created_utc"],
            }
            for r in rows
        ]
    }


@app.get("/api/outbox")
def outbox(claims: Annotated[dict, Depends(_auth)]) -> dict:
    _require(claims, "alert:send")  # principal + officer
    conn = _db()
    rows = AlertsRepo(conn).recent(25)
    conn.close()
    return {
        "messages": [
            {
                "alertId": r["id"],
                "schoolId": r["school_id"],
                "level": r["level_name"],
                "message": r["message"],
                "issuedBy": r["issued_by"],
                "issuedUtc": r["issued_utc"],
                "channel": r["channel"],
                "receipt": r["receipt"],
                "cert": r["cert"],
            }
            for r in rows
        ]
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


@app.post("/api/auth/login")
def login(payload: LoginPayload) -> JSONResponse:
    conn = _db()
    try:
        user = authenticate(conn, payload.username, payload.password)
    finally:
        conn.close()
    if user is None:
        raise HTTPException(status_code=401, detail="invalid credentials")
    token = issue(user["sub"], user["role"], settings.secret, settings.token_ttl_seconds)
    return JSONResponse({"token": token, "role": user["role"], "sub": user["sub"], "displayName": user["displayName"]})


@app.post("/api/auth/issue")
def issue_token() -> JSONResponse:
    # Open role minting is closed: possession of a URL is not identity.
    # Build It authenticates via /api/auth/login; Ship It uses Cognito (sam/template.yaml).
    raise HTTPException(
        status_code=403,
        detail="open role minting is disabled; sign in with a seeded account via POST /api/auth/login",
    )


@app.get("/api/me")
def me(claims: Annotated[dict, Depends(_auth)]) -> dict:
    conn = _db()
    try:
        row = UsersRepo(conn).get(claims["sub"])
    finally:
        conn.close()
    return {"sub": claims["sub"], "role": claims["role"], "name": row["display_name"] if row else ""}
