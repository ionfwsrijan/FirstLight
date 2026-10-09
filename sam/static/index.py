"""Serves the FirstLight Ship It web console.

The console is the SAME page as the local build: web/index.html is copied into
this bundle (by sam/build-layer.ps1) so the deployed UI cannot drift from the
local one. The handler derives its own API base URL from the incoming request
and injects it — plus the Cognito demo credentials (the local short passwords
cannot meet the pool's minimum-length/uppercase policy) — into the page via the
`<!--__API_BASE__-->` marker.
"""

from __future__ import annotations

import json
import os

_MARKER = "<!--__API_BASE__-->"

_CREDS = {
    "parent": {"username": "parent@firstlight.demo", "password": "Parent12345"},
    "principal": {"username": "principal@firstlight.demo", "password": "Principal123"},
    "officer": {"username": "officer@firstlight.demo", "password": "Officer1234"},
    "__hint": (
        "<b>Demo accounts</b> (click a card to fill): "
        "<b>parent@firstlight.demo</b> / Parent12345 · "
        "<b>principal@firstlight.demo</b> / Principal123 · "
        "<b>officer@firstlight.demo</b> / Officer1234. "
        "Cognito users: meera / rao / kapoor."
    ),
}

_PATH = os.path.join(os.path.dirname(__file__), "index.html")


def _injection(api_base: str) -> str:
    return (
        "<script>"
        f"window.__API__={json.dumps(api_base)};"
        f"window.__CREDS__={json.dumps(_CREDS, ensure_ascii=False)};"
        "</script>"
    )


def handler(event: dict, _context) -> dict:
    headers = event.get("headers") or {}
    host = headers.get("Host") or headers.get("host") or "localhost"
    stage = (event.get("requestContext") or {}).get("stage", "dev")
    api_base = f"https://{host}/{stage}".rstrip("/")

    with open(_PATH, encoding="utf-8") as f:
        html = f.read()
    if _MARKER in html:
        html = html.replace(_MARKER, _injection(api_base))
    else:  # defensive: keep the console usable if the marker was stripped
        html = html.replace("</head>", _injection(api_base) + "</head>", 1)
    return {
        "statusCode": 200,
        "headers": {
            "Content-Type": "text/html; charset=utf-8",
            "Cache-Control": "no-store",
            "X-FirstLight-Ruleset": os.environ.get("RULESET_VERSION", ""),
        },
        "body": html,
    }