"""Server entrypoint: `python -m firstlight.api.server` or via cli.

Wraps the FastAPI app in uvicorn. This is the Build It way to run — no AWS
account, no card, no bill — exactly as required for the Build It track.
"""

from __future__ import annotations

import uvicorn

from ..config import settings


def main() -> None:
    print(f"FirstLight → http://{settings.host}:{settings.port}")
    print("  health:   GET /api/health")
    print("  morning:  GET /api/morning/inputs")
    print("  talk:     POST /api/agent/talk  (consent-gated send)")
    print("  run:      POST /api/morning/run (officer role)")
    uvicorn.run("firstlight.api:app", host=settings.host, port=settings.port, log_level=settings.log_level.lower())


if __name__ == "__main__":
    main()
