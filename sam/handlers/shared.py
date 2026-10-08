"""Shared helpers for the Ship It Lambda handlers.

These mirror the local repositories with DynamoDB as the store. The decision
engine itself (`firstlight.engine`, `firstlight.dsl`) is pure Python and ships
in the FirstLightCoreLayer, so the cloud verdict is byte-for-byte the same as
the local FastAPI verdict.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request

import boto3

TABLE = os.environ["TABLE_NAME"]


def _table():
    return boto3.resource("dynamodb").Table(TABLE)


def put_decision(school_id: str, decision: dict) -> None:
    row = {
        "pk": f"SCHOOL#{school_id}",
        "sk": f"DECISION#{decision['date']}",
        "level": decision["level"],
        "bandLabel": decision["bandLabel"],
        "grapStage": decision["grapStage"],
        "plumeScore": decision["plumeScore"],
        "trend": decision["trend"],
        "payload": json.dumps(decision, ensure_ascii=False, sort_keys=True),
    }
    _table().put_item(Item=row)


def put_alert(school_id: str, date: str, level: str, cert: str) -> None:
    _table().put_item(Item={"pk": f"SCHOOL#{school_id}", "sk": f"ALERT#{date}", "level": level, "cert": cert})


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
    return claims.get("claims", {}).get("sub", "unknown")