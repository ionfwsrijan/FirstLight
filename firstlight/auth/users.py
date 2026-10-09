"""Seeded demo identities for Build It (password login, per-role caps).

Build It authenticates against locally seeded accounts: pbkdf2_hmac-sha256
with a deterministic per-user salt, constant-time comparison. Ship It reuses
the same console against Amazon Cognito (see sam/template.yaml) — only this
module's `authenticate` call differs.
"""

from __future__ import annotations

import hashlib
import hmac
import sqlite3

from ..storage import UsersRepo

# (username, password, role, display_name)
DEMO_USERS: tuple[tuple[str, str, str, str], ...] = (
    ("parent@firstlight.demo", "parent123", "parent", "Meera (parent)"),
    ("principal@firstlight.demo", "principal123", "principal", "Mr. Rao (principal)"),
    ("officer@firstlight.demo", "officer123", "officer", "Officer Kapoor"),
)

_ITERATIONS = 120_000


def _salt(username: str) -> str:
    return hashlib.sha256(f"firstlight-salt:{username}".encode()).hexdigest()[:16]


def _password_hash(password: str, salt: str) -> str:
    return hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), _ITERATIONS).hex()


def seed_users(conn: sqlite3.Connection) -> int:
    """Idempotent: inserts or refreshes the demo accounts. Returns count."""
    repo = UsersRepo(conn)
    for username, password, role, display_name in DEMO_USERS:
        salt = _salt(username)
        repo.upsert(username.lower(), display_name, role, salt, _password_hash(password, salt))
    return len(DEMO_USERS)


def authenticate(conn: sqlite3.Connection, username: str, password: str) -> dict | None:
    """Returns {'sub', 'role', 'displayName'} on success, None on bad credentials."""
    repo = UsersRepo(conn)
    row = repo.get(username.strip().lower())
    if row is None:
        # constant work on the miss path too, so timing does not leak existence
        _password_hash(password, _salt(username.strip().lower() or "unknown"))
        return None
    digest = _password_hash(password, row["salt"])
    if not hmac.compare_digest(digest, row["password_hash"]):
        return None
    return {"sub": row["username"], "role": row["role"], "displayName": row["display_name"]}
