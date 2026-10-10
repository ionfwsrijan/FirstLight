"""Append-only, hash-chained event ledger.

Every state-affecting fact (reading ingested, fire detected, decision emitted,
alert sent/recalled, admin run) is appended with a SHA-256 chain: row N's hash
includes row N-1's hash, so any edit breaks the chain. This is the tamper-proof
backing for firstlight's signature claims: `verify()` must pass for the day's
decisions to be displayed as authentic.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime

LEDGER_TABLE = """
CREATE TABLE IF NOT EXISTS ledger (
    seq INTEGER PRIMARY KEY AUTOINCREMENT,
    ts TEXT NOT NULL,
    kind TEXT NOT NULL,
    ref TEXT NOT NULL,
    payload TEXT NOT NULL,
    prev_hash TEXT NOT NULL,
    hash TEXT NOT NULL
);
"""


def _now_utc() -> str:
    return datetime.now(UTC).isoformat()


def _hash(seq: int, ts: str, kind: str, ref: str, payload: str, prev_hash: str) -> str:
    h = hashlib.sha256()
    h.update(f"{seq}|{ts}|{kind}|{ref}|{json.dumps(payload, sort_keys=True)}|{prev_hash}".encode())
    return h.hexdigest()


@dataclass
class Ledger:
    conn: sqlite3.Connection

    def append(self, kind: str, ref: str, payload: dict) -> str:
        cur = self.conn.execute("SELECT seq, hash FROM ledger ORDER BY seq DESC LIMIT 1")
        row = cur.fetchone()
        prev_hash = row[1] if row else ""
        seq = (row[0] + 1) if row else 1
        ts = _now_utc()
        dumped = json.dumps(payload, ensure_ascii=False, sort_keys=True)
        digest = _hash(seq, ts, kind, ref, dumped, prev_hash)
        self.conn.execute(
            "INSERT INTO ledger (seq, ts, kind, ref, payload, prev_hash, hash) VALUES (?,?,?,?,?,?,?)",
            (seq, ts, kind, ref, dumped, prev_hash, digest),
        )
        return digest

    def entries(self, limit: int = 100) -> list[dict]:
        cur = self.conn.execute(
            "SELECT seq, ts, kind, ref, payload FROM ledger ORDER BY seq DESC LIMIT ?", (limit,)
        )
        return [{"seq": r[0], "ts": r[1], "kind": r[2], "ref": r[3], "payload": json.loads(r[4])} for r in cur.fetchall()]

    def verify(self) -> dict:
        """Recompute the whole chain; return ok + where it broke, if anywhere."""
        cur = self.conn.execute("SELECT seq, ts, kind, ref, payload, prev_hash, hash FROM ledger ORDER BY seq")
        prev_hash = ""
        ok = True
        broke_at: int | None = None
        for row in cur.fetchall():
            seq, ts, kind, ref, payload, prev_hash_stored, stored = row
            expected = _hash(seq, ts, kind, ref, payload, prev_hash)
            if stored != expected or prev_hash_stored != prev_hash:
                ok = False
                broke_at = seq
                break
            prev_hash = stored
        count = self.conn.execute("SELECT COUNT(*) FROM ledger").fetchone()[0]
        return {"ok": ok, "rows": count, "brokeAt": broke_at}
