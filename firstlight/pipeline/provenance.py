"""Per-field data provenance: exactly which morning inputs are live vs frozen.

The console and `/health` should never have to guess. Each field carries its
own honesty record so a judge can see, field by field, that stations and fires
can be live (with a visible fallback) while wind and history are frozen
snapshots seeded for a reproducible demo.
"""

from __future__ import annotations

from .air import read_air_status
from .scenario import HISTORY, WIND
from .sources import read_status as read_fire_status

_FIELDS = ("stations", "fires", "wind", "history")


def _field(
    live: bool,
    provider: str,
    *,
    fetched_at: str | None = None,
    count: int = 0,
    fallback: bool = False,
    error: str | None = None,
) -> dict:
    return {
        "live": live,
        "provider": provider,
        "fetchedAt": fetched_at,
        "count": count,
        "fallback": fallback,
        "error": error,
    }


def source_status(conn) -> dict:
    """One dict per input field, each stating plainly whether it is live."""
    air = read_air_status(conn)
    fires = read_fire_status(conn)
    days = len(next(iter(HISTORY.values()))) if HISTORY else 0
    return {
        "stations": _field(
            air["source"] != "frozen",
            air["label"],
            fetched_at=air["fetchedAt"],
            count=air["count"],
            fallback=air["fallback"],
            error=air["error"],
        ),
        "fires": _field(
            fires["source"] != "frozen",
            fires["label"],
            fetched_at=fires["fetchedAt"],
            count=fires["count"],
            fallback=fires["fallback"],
            error=fires["error"],
        ),
        "wind": _field(
            False,
            "IMD observation · frozen scenario",
            fetched_at=WIND.observed_utc,
            count=1,
        ),
        "history": _field(
            False,
            f"Seeded prior mornings · {days} days",
            count=days,
        ),
    }


def live_fields(status: dict) -> list[str]:
    return [name for name in _FIELDS if status.get(name, {}).get("live")]


__all__ = ["source_status", "live_fields"]
