"""Seed the local database with the deterministic scenario (if absent)."""

from __future__ import annotations

import sys
from pathlib import Path

from ..auth import seed_users
from ..config import settings
from ..pipeline.scenario import morning_inputs
from ..storage import FiresRepo, HistoryRepo, SchoolsRepo, StationsRepo, connect


def seed() -> dict:
    db = connect(settings.db_path)
    inputs = morning_inputs()
    stations, schools_repo, fires_repo, history_repo = (
        StationsRepo(db),
        SchoolsRepo(db),
        FiresRepo(db),
        HistoryRepo(db),
    )
    for st in inputs.stations:
        stations.upsert(st)
    for sch in inputs.schools:
        schools_repo.upsert(sch)
    for fire in inputs.fires:
        fires_repo.upsert(fire)
    for sid, aqis in inputs.history_aqi.items():
        # prior mornings are the trend baseline; today's is set by run_morning
        for idx, aqi in enumerate(aqis, start=1):
            history_repo.set_morning(sid, f"2026-10-{idx:02d}", aqi)
    seed_users(db)  # demo identities for /api/auth/login
    db.commit()
    counts = {
        "stations": db.execute("SELECT COUNT(*) FROM stations").fetchone()[0],
        "schools": db.execute("SELECT COUNT(*) FROM schools").fetchone()[0],
        "fires": db.execute("SELECT COUNT(*) FROM fires").fetchone()[0],
        "history_rows": db.execute("SELECT COUNT(*) FROM history_aqi").fetchone()[0],
        "users": db.execute("SELECT COUNT(*) FROM users").fetchone()[0],
    }
    db.close()
    return counts


def main(argv: list[str] | None = None) -> None:
    argv = sys.argv[1:] if argv is None else argv
    force = "--force" in argv
    if settings.db_exists and not force:
        print(f"database already present: {settings.db_path}")
        print("run with --force to reseed")
        return
    if force and settings.db_exists:
        settings.db_path.unlink()
        for sidecar in (".wal", "-wal", ".shm", "-shm"):
            p = Path(str(settings.db_path) + sidecar)
            if p.exists():
                p.unlink()
    counts = seed()
    print(f"seeded {settings.db_path}")
    for k, v in counts.items():
        print(f"  {k}: {v}")


if __name__ == "__main__":
    main()
