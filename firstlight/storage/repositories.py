"""Repositories: typed access over the sqlite connection.

Thin, explicit, and driveable — the same interface the Ship It SAM template
reimplements against DynamoDB, so swapping persistence does not change the
engine, the pipeline, or the API logic.
"""

from __future__ import annotations

import sqlite3
from datetime import datetime, timezone

from ..domain import Decision, School, Station, StubbleFire
from .db import json_of, loads


class StationsRepo:
    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn

    def upsert(self, station: Station) -> None:
        self.conn.execute(
            "INSERT INTO stations (id, name, lat, lon, aqi, main_pollutant, last_updated_utc) "
            "VALUES (?,?,?,?,?,?,?) "
            "ON CONFLICT(id) DO UPDATE SET aqi=excluded.aqi, main_pollutant=excluded.main_pollutant, "
            "last_updated_utc=excluded.last_updated_utc",
            (station.id, station.name, station.lat, station.lon, station.aqi, station.main_pollutant, station.last_updated_utc),
        )

    def all(self) -> list[Station]:
        rows = self.conn.execute("SELECT * FROM stations").fetchall()
        return [Station(r["id"], r["name"], r["lat"], r["lon"], r["aqi"], r["main_pollutant"], r["last_updated_utc"]) for r in rows]


class SchoolsRepo:
    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn

    def upsert(self, school: School) -> None:
        self.conn.execute(
            "INSERT INTO schools (id, name, ward, lat, lon, strength, has_sensitive_group, opens_at) "
            "VALUES (?,?,?,?,?,?,?,?) "
            "ON CONFLICT(id) DO UPDATE SET name=excluded.name, strength=excluded.strength",
            (school.id, school.name, school.ward, school.lat, school.lon, school.strength, 1 if school.has_sensitive_group else 0, school.opens_at),
        )

    def all(self) -> list[School]:
        rows = self.conn.execute("SELECT * FROM schools").fetchall()
        return [
            School(r["id"], r["name"], r["ward"], r["lat"], r["lon"], r["strength"], bool(r["has_sensitive_group"]), r["opens_at"])
            for r in rows
        ]


class FiresRepo:
    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn

    def upsert(self, fire: StubbleFire) -> None:
        self.conn.execute(
            "INSERT INTO fires (id, lat, lon, district, state, frp, detected_utc, status) "
            "VALUES (?,?,?,?,?,?,?,?) "
            "ON CONFLICT(id) DO UPDATE SET status=excluded.status, frp=excluded.frp",
            (fire.id, fire.lat, fire.lon, fire.district, fire.state, fire.frp, fire.detected_utc, fire.status),
        )

    def all_active(self) -> list[StubbleFire]:
        rows = self.conn.execute("SELECT * FROM fires WHERE status='active'").fetchall()
        return [StubbleFire(r["id"], r["lat"], r["lon"], r["district"], r["state"], r["frp"], r["detected_utc"], r["status"]) for r in rows]


class HistoryRepo:
    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn

    def set_morning(self, school_id: str, morning_date: str, aqi: float) -> None:
        self.conn.execute(
            "INSERT INTO history_aqi (school_id, morning_date, aqi) VALUES (?,?,?) "
            "ON CONFLICT(school_id, morning_date) DO UPDATE SET aqi=excluded.aqi",
            (school_id, morning_date, aqi),
        )

    def prior(self, school_id: str, up_to_date: str) -> list[float]:
        rows = self.conn.execute(
            "SELECT aqi FROM history_aqi WHERE school_id=? AND morning_date < ? ORDER BY morning_date DESC LIMIT 7",
            (school_id, up_to_date),
        ).fetchall()
        return [r["aqi"] for r in rows]


class DecisionsRepo:
    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn

    def save(self, decision: Decision) -> None:
        self.conn.execute(
            "INSERT INTO decisions (school_id, date, level, aqi_effective, band_label, band_hex, grap_stage, "
            "fires_upwind, plume_score, trend, reasons_json, actions_json, evidence_json, created_utc) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?) "
            "ON CONFLICT(school_id, date) DO UPDATE SET level=excluded.level, aqi_effective=excluded.aqi_effective, "
            "band_label=excluded.band_label, grap_stage=excluded.grap_stage, reasons_json=excluded.reasons_json, "
            "actions_json=excluded.actions_json, evidence_json=excluded.evidence_json",
            (
                decision.school_id,
                decision.date,
                int(decision.level),
                decision.aqi_effective,
                decision.band_label,
                decision.band_hex,
                decision.grap_stage,
                decision.fires_upwind,
                decision.plume_score,
                decision.trend,
                json_of([r.to_dict() for r in decision.reasons]),
                json_of(list(decision.actions)),
                json_of(decision.evidence),
                datetime.now(timezone.utc).isoformat(),
            ),
        )

    def for_school(self, school_id: str) -> list[dict]:
        rows = self.conn.execute(
            "SELECT school_id, date, level, aqi_effective, band_label, grap_stage, plume_score, trend "
            "FROM decisions WHERE school_id=? ORDER BY date DESC LIMIT 30",
            (school_id,),
        ).fetchall()
        return [dict(r) for r in rows]

    def today(self, school_id: str, date: str) -> dict | None:
        row = self.conn.execute(
            "SELECT * FROM decisions WHERE school_id=? AND date=?", (school_id, date)
        ).fetchone()
        return dict(row) if row else None


class AlertsRepo:
    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn

    def save_alert(
        self,
        school_id: str,
        date: str,
        level: int,
        level_name: str,
        message: str,
        issued_by: str,
        cert: str,
        channel: str = "",
        receipt: str = "",
    ) -> int:
        cur = self.conn.execute(
            "INSERT INTO alerts (school_id, date, level, level_name, message, issued_by, issued_utc, status, cert, channel, receipt) "
            "VALUES (?,?,?,?,?,?,?, 'sent', ?,?,?)",
            (
                school_id,
                date,
                level,
                level_name,
                message,
                issued_by,
                datetime.now(timezone.utc).isoformat(),
                cert,
                channel,
                receipt,
            ),
        )
        return cur.lastrowid

    def recent(self, limit: int = 25) -> list[dict]:
        rows = self.conn.execute("SELECT * FROM alerts ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
        return [dict(r) for r in rows]


class UsersRepo:
    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn

    def upsert(self, username: str, display_name: str, role: str, salt: str, password_hash: str) -> None:
        self.conn.execute(
            "INSERT INTO users (username, display_name, role, salt, password_hash) VALUES (?,?,?,?,?) "
            "ON CONFLICT(username) DO UPDATE SET display_name=excluded.display_name, role=excluded.role, "
            "salt=excluded.salt, password_hash=excluded.password_hash",
            (username, display_name, role, salt, password_hash),
        )

    def get(self, username: str) -> dict | None:
        row = self.conn.execute("SELECT * FROM users WHERE username=?", (username,)).fetchone()
        return dict(row) if row else None


class TranscriptRepo:
    """Server-side conversation record: the consent gate replays these turns."""

    MAX_TURNS = 100

    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn

    def user_turns(self, caller: str, school_id: str) -> list[dict]:
        """Prior *user* turns only (assistant replies are never consent input)."""
        rows = self.conn.execute(
            "SELECT intent, text FROM transcript WHERE caller=? AND school_id=? AND speaker='user' ORDER BY id ASC",
            (caller, school_id),
        ).fetchall()
        return [dict(r) for r in rows]

    def next_turn(self, caller: str, school_id: str) -> int:
        row = self.conn.execute(
            "SELECT COALESCE(MAX(turn), 0) + 1 AS n FROM transcript WHERE caller=? AND school_id=?",
            (caller, school_id),
        ).fetchone()
        return int(row["n"])

    def append(self, caller: str, school_id: str, turn: int, speaker: str, text: str, intent: str) -> int:
        cur = self.conn.execute(
            "INSERT INTO transcript (caller, school_id, turn, speaker, intent, text, created_utc) VALUES (?,?,?,?,?,?,?)",
            (caller, school_id, turn, speaker, intent, text, datetime.now(timezone.utc).isoformat()),
        )
        self.conn.execute(
            "DELETE FROM transcript WHERE caller=? AND school_id=? AND id NOT IN "
            "(SELECT id FROM transcript WHERE caller=? AND school_id=? ORDER BY id DESC LIMIT ?)",
            (caller, school_id, caller, school_id, self.MAX_TURNS),
        )
        return int(cur.lastrowid)

    def recent(self, caller: str, school_id: str = "", limit: int = 60) -> list[dict]:
        if school_id:
            rows = self.conn.execute(
                "SELECT * FROM transcript WHERE caller=? AND school_id=? ORDER BY id DESC LIMIT ?",
                (caller, school_id, limit),
            ).fetchall()
        else:
            rows = self.conn.execute(
                "SELECT * FROM transcript WHERE caller=? ORDER BY id DESC LIMIT ?",
                (caller, limit),
            ).fetchall()
        return [dict(r) for r in reversed(rows)]


class MetaRepo:
    """Small key/value JSON store (data provenance lives here)."""

    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn

    def get(self, key: str) -> object | None:
        row = self.conn.execute("SELECT value FROM meta WHERE key=?", (key,)).fetchone()
        return loads(row["value"]) if row else None

    def set(self, key: str, value: object) -> None:
        self.conn.execute(
            "INSERT INTO meta (key, value) VALUES (?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
            (key, json_of(value)),
        )

    def delete(self, key: str) -> None:
        self.conn.execute("DELETE FROM meta WHERE key=?", (key,))