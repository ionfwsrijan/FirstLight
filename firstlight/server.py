"""Build It: the whole product as one stdlib HTTP server on localhost.

No AWS account, no card, no bill. The student-verification problem that
haunted the previous project cannot exist here because we never call AWS.
"""

from __future__ import annotations

import json
import os
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse, parse_qs

from . import agent, bands, data, demo, ledger

ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / "web"
PORT = int(os.environ.get("FIRSTLIGHT_PORT", "8000"))

CORS = {"Access-Control-Allow-Origin": "*", "Access-Control-Allow-Methods": "GET,POST,OPTIONS"}


class Handler(BaseHTTPRequestHandler):
    def _json(self, payload: object, status: int = 200) -> None:
        raw = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(raw)))
        for k, v in CORS.items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(raw)

    def _static(self, path: str) -> None:
        rel = path.lstrip("/") or "index.html"
        candidate = (WEB / rel).resolve()
        if not candidate.is_file() or WEB not in candidate.parents:
            candidate = WEB / "index.html"
        data_raw = candidate.read_bytes()
        ctype = {
            ".html": "text/html; charset=utf-8",
            ".js": "text/javascript",
            ".css": "text/css",
            ".svg": "image/svg+xml",
        }.get(candidate.suffix.lower(), "application/octet-stream")
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data_raw)))
        self.end_headers()
        self.wfile.write(data_raw)

    def do_OPTIONS(self) -> None:
        self.send_response(204)
        for k, v in CORS.items():
            self.send_header(k, v)
        self.end_headers()

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        route = parsed.path
        if route == "/api/health":
            self._json({"ok": True, "version": "0.1.0", "engine": "rules-v1@2026-10"})
        elif route == "/api/snapshot":
            self._json(data.snapshot())
        elif route == "/api/ledger":
            self._json(ledger.summarize())
        elif route == "/api/bands":
            self._json({"bands": [b.__dict__ for b in bands.BANDS]})
        elif route == "/api/demo":
            query = parse_qs(parsed.query)
            sid = (query.get("school") or ["s-avini"])[0]
            self._json(demo.run(sid))
        elif route == "/api/notifications":
            self._json({"sent": agent.notification_ledger()})
        else:
            self._static(route)

    def do_POST(self) -> None:
        length = int(self.headers.get("Content-Length") or 0)
        body = self.rfile.read(length).decode("utf-8") if length else "{}"
        try:
            payload = json.loads(body or "{}")
        except json.JSONDecodeError:
            self._json({"ok": False, "error": "bad json"}, 400)
            return
        route = urlparse(self.path).path
        if route == "/api/turn":
            turn = agent.answer(
                payload.get("caller", "parent"),
                payload.get("schoolId", "s-avini"),
                payload.get("text", ""),
            )
            self._json({"ok": True, "turn": turn.to_dict()})
        else:
            self._json({"ok": False, "error": "not found"}, 404)

    def log_message(self, *args):
        pass


def main(argv: list[str] | None = None) -> None:
    argv = sys.argv[1:] if argv is None else argv
    port = int(argv[0]) if argv and argv[0].isdigit() else PORT
    server = ThreadingHTTPServer(("0.0.0.0", port), Handler)
    print(f"FirstLight -> http://localhost:{port}")
    print(f"Run the morning:  http://localhost:{port}/api/demo")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()