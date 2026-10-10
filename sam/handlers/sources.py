"""Officer-only live source refresh, split from the read-only meta handler.

Kept in its own Lambda so it can carry a scoped DynamoDB read/write grant (it
persists provenance) while meta.py keeps a read-only grant -- least privilege,
one direction per function.

When SOURCE_MODE=frozen (local/CI) this is an honest stub: it says it would go
live, records nothing, and never touches the network. When SOURCE_MODE=live
(deployed) it fetches live station air (Open-Meteo -> CPCB AQI) and live stubble
fires (NASA FIRMS), falling back to the frozen snapshot visibly on any failure.
"""

from __future__ import annotations

import os

try:  # Lambda treats handlers/ as the code root (no package parent)
    from .shared import (
        cognito_role,
        refresh_air_dyn,
        refresh_fires_dyn,
        respond,
        source_status_dyn,
    )
except ImportError:
    from shared import (
        cognito_role,
        refresh_air_dyn,
        refresh_fires_dyn,
        respond,
        source_status_dyn,
    )


def _stub() -> dict:
    fires = source_status_dyn()["fires"]
    return {
        "source": "frozen",
        "label": fires["provider"],
        "fetchedAt": None,
        "count": fires["count"],
        "fallback": True,
        "error": (
            "live refresh runs only when SOURCE_MODE=live; this stack is the "
            "deterministic frozen mirror"
        ),
    }


def handler(event: dict, _context) -> dict:
    role = cognito_role(event)
    if role != "officer":
        return respond(403, {"detail": f"role {role} cannot run:morning"})

    if os.environ.get("SOURCE_MODE", "frozen") != "live":
        return respond(200, _stub())

    fires = refresh_fires_dyn()
    air = refresh_air_dyn()
    return respond(200, {**fires, "air": air, "sources": source_status_dyn()})
