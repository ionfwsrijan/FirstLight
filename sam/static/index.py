"""Serves the FirstLight Ship It web console.

The console derives its own API base URL from the incoming request so it works
behind any stage without a template dependency; login happens against the
Cognito-backed /login endpoint from the page itself.
"""

from __future__ import annotations

import os

_PATH = os.path.join(os.path.dirname(__file__), "index.html")


def handler(event: dict, _context) -> dict:
    headers = event.get("headers") or {}
    host = headers.get("Host") or headers.get("host") or "localhost"
    stage = (event.get("requestContext") or {}).get("stage", "dev")
    api_base = f"https://{host}/{stage}"

    with open(_PATH, encoding="utf-8") as f:
        html = f.read()
    html = html.replace("__API_BASE__", api_base.rstrip("/"))
    return {
        "statusCode": 200,
        "headers": {
            "Content-Type": "text/html; charset=utf-8",
            "Cache-Control": "no-store",
            "X-FirstLight-Ruleset": os.environ.get("RULESET_VERSION", ""),
        },
        "body": html,
    }