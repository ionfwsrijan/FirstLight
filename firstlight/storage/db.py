"""SQLite persistence. WAL for concurrent reads; everything is a repository.

Schema is kept in this module as SQL text, DDL is idempotent. Responsibly
plain (stdlib sqlite3) so Build It needs zero extra installs beyond FastAPI.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from ..ledger.store import LEDGER_TABLE

SCHEMA = """
CREATE TABLE IF NOT EXISTS stations (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    lat REAL NOT NULL,
    lon REAL NOT NULL,
    aqi INTEGER NOT NULL,
    main_pollutant TEXT NOT NULL,
    last_updated_utc TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS schools (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    ward TEXT NOT NULL,
    lat REAL NOT NULL,
    lon REAL NOT NULL,
    strength INTEGER NOT NULL,
    has_sensitive_group INTEGER NOT NULL DEFAULT 0,
    opens_at TEXT NOT NULL DEFAULT '08:30'
);

CREATE TABLE IF NOT EXISTS fires (
    id TEXT PRIMARY KEY,
    lat REAL NOT NULL,
    lon REAL NOT NULL,
    district TEXT NOT NULL,
    state TEXT NOT NULL,
    frp REAL NOT NULL,
    detected_utc TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'active'
);

CREATE TABLE IF NOT EXISTS wind (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    direction_deg REAL NOT NULL,
    speed_kmh REAL NOT NULL,
    observed_utc TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS history_aqi (
    school_id TEXT NOT NULL,
    morning_date TEXT NOT NULL,
    aqi REAL NOT NULL,
    PRIMARY KEY (school_id, morning_date)
);

CREATE TABLE IF NOT EXISTS decisions (
    school_id TEXT NOT NULL,
    date TEXT NOT NULL,
    level INTEGER NOT NULL,
    aqi_effective REAL NOT NULL,
    band_label TEXT NOT NULL,
    band_hex TEXT NOT NULL,
    grap_stage INTEGER NOT NULL,
    fires_upwind INTEGER NOT NULL,
    plume_score REAL NOT NULL,
    trend TEXT NOT NULL,
    reasons_json TEXT NOT NULL,
    actions_json TEXT NOT NULL,
    evidence_json TEXT NOT NULL,
    created_utc TEXT NOT NULL,
    PRIMARY KEY (school_id, date)
);

CREATE TABLE IF NOT EXISTS alerts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    school_id TEXT NOT NULL,
    date TEXT NOT NULL,
    level INTEGER NOT NULL,
    level_name TEXT NOT NULL,
    message TEXT NOT NULL,
    issued_by TEXT NOT NULL,
    issued_utc TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'sent',
    cert TEXT NOT NULL,
    channel TEXT NOT NULL DEFAULT '',
    receipt TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS users (
    username TEXT PRIMARY KEY,
    display_name TEXT NOT NULL,
    role TEXT NOT NULL,
    salt TEXT NOT NULL,
    password_hash TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS transcript (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    caller TEXT NOT NULL,
    school_id TEXT NOT NULL,
    turn INTEGER NOT NULL,
    speaker TEXT NOT NULL,
    intent TEXT NOT NULL DEFAULT '',
    text TEXT NOT NULL,
    created_utc TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_transcript_conv ON transcript(caller, school_id, id);

CREATE TABLE IF NOT EXISTS meta (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
"""


def _migrate(conn: sqlite3.Connection) -> None:
    """Additive migrations for databases created before a column existed."""
    alert_cols = {row[1] for row in conn.execute("PRAGMA table_info(alerts)")}
    if "channel" not in alert_cols:
        conn.execute("ALTER TABLE alerts ADD COLUMN channel TEXT NOT NULL DEFAULT ''")
    if "receipt" not in alert_cols:
        conn.execute("ALTER TABLE alerts ADD COLUMN receipt TEXT NOT NULL DEFAULT ''")


def connect(db_path: Path) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.executescript(SCHEMA)
    conn.executescript(LEDGER_TABLE)
    _migrate(conn)
    conn.commit()
    return conn


def json_of(value) -> str:
    return json.dumps(value, ensure_ascii=False)


def loads(raw: str) -> object:
    return json.loads(raw) if raw else None