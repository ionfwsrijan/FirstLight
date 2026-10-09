"""Shared helpers for the Ship It Lambda handlers.

These mirror the local repositories with DynamoDB as the store. The decision
engine itself (`firstlight.engine`, `firstlight.dsl`) is pure Python and ships
in the FirstLightCoreLayer, so the cloud verdict is byte-for-byte the same as
the local FastAPI verdict.

In addition to the decision/alert rows written by morning.py and talk.py, the
LEDGER item collection is a real append-only SHA-256 hash chain (seq ->
prevHash -> hash) so `ledger_verify()` means the same thing it does locally.
"""

from __future__ import annotations

import hashlib
import json
import os
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from decimal import Decimal

import boto3

TABLE = os.environ["TABLE_NAME"]

_FALLBACK_STATUS = {
    "source": "frozen",
    "label": "Frozen scenario snapshot",
    "fetchedAt": None,
    "count": 7,  # the seeded stubble fires; see pipeline/scenario.py
    "fallback": False,
    "error": None,
}

ROLE_BY_EMAIL_LOCALPART = {
    "parent": "parent",
    "principal": "principal",
    "officer": "officer",
}
ROLE_BY_USERNAME = {"meera": "parent", "rao": "principal", "kapoor": "officer"}


def _table():
    return boto3.resource("dynamodb").Table(TABLE)


def _to_dynamo(value):
    """DynamoDB supports Decimal, not Python float, for numeric values."""
    if isinstance(value, float):
        return Decimal(str(value))
    if isinstance(value, dict):
        return {k: _to_dynamo(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_to_dynamo(v) for v in value]
    return value


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def cognito_role(event: dict) -> str:
    """Parent / principal / officer, derived from the Cognito identity claims.

    The authorizer passes the id-token claims through; the demo emails are
    parent/principal/officer@firstlight.demo, so the email localpart is the
    role. Usernames (meera/rao/kapoor) are a fallback for local tests.
    """
    claims = (event.get("requestContext") or {}).get("authorizer") or {}
    claims = (claims.get("claims") or {}) if isinstance(claims, dict) else {}
    email = str(claims.get("email", "") or "")
    role = ROLE_BY_EMAIL_LOCALPART.get(email.split("@")[0].strip().lower())
    if role:
        return role
    sub = str(claims.get("sub", "") or "").lower()
    for username, user_role in ROLE_BY_USERNAME.items():
        if username in sub:
            return user_role
    return "viewer"


def put_decision(school_id: str, decision: dict) -> None:
    row = _to_dynamo({
        "pk": f"SCHOOL#{school_id}",
        "sk": f"DECISION#{decision['date']}",
        "level": decision["level"],
        "bandLabel": decision["bandLabel"],
        "grapStage": decision["grapStage"],
        "plumeScore": decision["plumeScore"],
        "trend": decision["trend"],
        "payload": json.dumps(decision, ensure_ascii=False, sort_keys=True),
    })
    _table().put_item(Item=row)


def put_alert(
    school_id: str,
    date: str,
    level: str,
    cert: str,
    message: str,
    channel: str,
    receipt: str,
    issued_by: str,
    issued_utc: str,
) -> str:
    """Record one delivered alert (outbox row) plus its ledger entry."""
    ms = int(time.time() * 1000)
    alert_id = f"{date}#{ms}"
    _table().put_item(Item=_to_dynamo({
        "pk": f"SCHOOL#{school_id}",
        "sk": f"ALERT#{alert_id}",
        "level": level,
        "cert": cert,
        "message": message,
        "channel": channel,
        "receipt": receipt,
        "issuedBy": issued_by,
        "issuedUtc": issued_utc,
    }))
    append_ledger("alert", school_id, {
        "alertId": alert_id, "receipt": receipt, "cert": cert, "channel": channel,
    })
    return alert_id


def outbox_messages(limit: int = 25) -> list[dict]:
    items = _table().scan(
        FilterExpression="begins_with(sk, :p)",
        ExpressionAttributeValues={":p": "ALERT#"},
    )["Items"]
    items = [i for i in items if i.get("message")]
    items.sort(key=lambda i: i["sk"], reverse=True)
    return [
        {
            "alertId": i["sk"].split("#", 2)[-1],
            "schoolId": i["pk"].split("#", 1)[-1],
            "level": i["level"],
            "message": i["message"],
            "issuedBy": i["issuedBy"],
            "issuedUtc": i["issuedUtc"],
            "channel": i["channel"],
            "receipt": i["receipt"],
            "cert": i["cert"],
        }
        for i in items[:limit]
    ]


def get_latest(school_id: str) -> dict | None:
    items = _table().query(
        KeyConditionExpression="pk = :pk AND begins_with(sk, :p)",
        ExpressionAttributeValues={":pk": f"SCHOOL#{school_id}", ":p": "DECISION#"},
        ScanIndexForward=False,
        Limit=1,
    )["Items"]
    if not items:
        return None
    return json.loads(items[0]["payload"])


def decisions_for(school_id: str, limit: int = 20) -> list[dict]:
    items = _table().query(
        KeyConditionExpression="pk = :pk AND begins_with(sk, :p)",
        ExpressionAttributeValues={":pk": f"SCHOOL#{school_id}", ":p": "DECISION#"},
        ScanIndexForward=False,
        Limit=limit,
    )["Items"]
    return [json.loads(i["payload"]) for i in items]


# ---------- append-only hash-chained ledger (mirrors firstlight/ledger) ----------

def _ledger_hash(seq: int, ts: str, kind: str, ref: str, payload: str, prev_hash: str) -> str:
    h = hashlib.sha256()
    h.update(f"{seq}|{ts}|{kind}|{ref}|{payload}|{prev_hash}".encode())
    return h.hexdigest()


def _next_ledger_seq() -> int:
    resp = _table().update_item(
        Key={"pk": "SYS#SEQ", "sk": "#counter"},
        UpdateExpression="ADD c :one",
        ExpressionAttributeValues={":one": 1},
        ReturnValues="UPDATED_NEW",
    )
    return int(resp["Attributes"]["c"])


def append_ledger(kind: str, ref: str, payload: dict) -> str:
    table = _table()
    previous = table.query(
        KeyConditionExpression="pk = :pk",
        ExpressionAttributeValues={":pk": "LEDGER"},
        ScanIndexForward=False,
        Limit=1,
    )["Items"]
    prev_hash = (previous[0].get("hash") or "") if previous else ""
    seq = _next_ledger_seq()
    ts = now_utc()
    dumped = json.dumps(payload, ensure_ascii=False, sort_keys=True)
    digest = _ledger_hash(seq, ts, kind, ref, dumped, prev_hash)
    table.put_item(Item={
        "pk": "LEDGER",
        "sk": f"#{seq:012d}",
        "ts": ts,
        "kind": kind,
        "ref": ref,
        "payload": dumped,
        "prevHash": prev_hash,
        "hash": digest,
    })
    return digest


def ledger_entries(limit: int = 25) -> list[dict]:
    items = _table().query(
        KeyConditionExpression="pk = :pk",
        ExpressionAttributeValues={":pk": "LEDGER"},
        ScanIndexForward=False,
        Limit=limit,
    )["Items"]
    return [
        {
            "seq": int(i["sk"].lstrip("#")),
            "ts": i["ts"],
            "kind": i["kind"],
            "ref": i["ref"],
            "payload": json.loads(i["payload"]),
        }
        for i in items
    ]


def ledger_verify() -> dict:
    items = _table().query(
        KeyConditionExpression="pk = :pk",
        ExpressionAttributeValues={":pk": "LEDGER"},
        ScanIndexForward=True,
    )["Items"]
    prev_hash = ""
    broke_at = None
    for i in items:
        seq = int(i["sk"].lstrip("#"))
        expected = _ledger_hash(seq, i["ts"], i["kind"], i["ref"], i["payload"], prev_hash)
        if expected != i.get("hash") or i.get("prevHash", "") != prev_hash:
            broke_at = seq
            break
        prev_hash = i.get("hash", "")
    return {"ok": broke_at is None, "rows": len(items), "brokeAt": broke_at}


# ---------- agent transcript (mirrors firstlight/storage TranscriptRepo) ----------

def append_turns(
    school_id: str,
    caller: str,
    user_text: str,
    user_intent: str,
    agent_text: str,
    agent_intent: str,
) -> int:
    pk = f"TRANSCRIPT#{school_id}#{caller}"
    previous = _table().query(
        KeyConditionExpression="pk = :pk",
        ExpressionAttributeValues={":pk": pk},
        ScanIndexForward=False,
        Limit=1,
    )["Items"]
    last_seq = int(previous[0]["sk"].lstrip("#")) if previous else 0
    user_seq = last_seq + 1
    turn = (user_seq + 1) // 2  # each message = one user turn + one agent turn
    ts = now_utc()
    _table().put_item(Item={
        "pk": pk, "sk": f"#{user_seq:012d}", "speaker": "user",
        "text": user_text, "intent": user_intent, "turn": turn, "ts": ts,
    })
    _table().put_item(Item={
        "pk": pk, "sk": f"#{user_seq + 1:012d}", "speaker": "agent",
        "text": agent_text, "intent": agent_intent, "turn": turn, "ts": ts,
    })
    return turn


def transcript_turns(school_id: str, caller: str) -> list[dict]:
    items = _table().query(
        KeyConditionExpression="pk = :pk",
        ExpressionAttributeValues={":pk": f"TRANSCRIPT#{school_id}#{caller}"},
        ScanIndexForward=True,
        Limit=400,
    )["Items"]
    return [
        {
            "id": i["sk"],
            "turn": int(i["turn"]),
            "speaker": i["speaker"],
            "intent": i.get("intent", ""),
            "text": i["text"],
            "createdUtc": i["ts"],
        }
        for i in items
    ]


def respond(status: int, body: dict) -> dict:
    return {
        "statusCode": status,
        "headers": {
            "Content-Type": "application/json",
            "X-FirstLight-Ruleset": os.environ.get("RULESET_VERSION", ""),
        },
        "body": json.dumps(body, ensure_ascii=False),
    }


def parse_body(event: dict) -> dict:
    return json.loads(event.get("body") or "{}")


def notify_webhook(level: str, message: str) -> str:
    hook = os.environ.get("ALERT_HOOK_URL", "")
    if not hook:
        return "noop"
    try:
        req = urllib.request.Request(
            hook, data=json.dumps({"level": level, "text": message}).encode(),
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=3) as r:
            return f"hook:{r.status}"
    except (urllib.error.URLError, TimeoutError, OSError):
        return "hook:failed"


def principal_id(event: dict) -> str:
    claims = (event.get("requestContext") or {}).get("authorizer") or {}
    claims = (claims.get("claims") or {}) if isinstance(claims, dict) else {}
    return claims.get("sub", "unknown")