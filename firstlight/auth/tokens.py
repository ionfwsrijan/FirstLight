"""HMAC-signed capability tokens.

Signed, tamper-evident, no external deps. A token is {sub, role, iat, exp}
HMAC-SHA256'd with the server secret. Verification recomputes the MAC and
checks expiry. For the Build It path this is a dependency-free stand-in for
AWS SigV4 / Cognito; the Ship It SAM template wires the same roles to Cognito.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time


def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def _unb64(data: str) -> bytes:
    pad = "=" * (-len(data) % 4)
    return base64.urlsafe_b64decode(data + pad)


def _sign(payload: str, secret: str) -> str:
    return hmac.new(secret.encode(), payload.encode(), hashlib.sha256).hexdigest()


def issue(sub: str, role: str, secret: str, ttl_seconds: int, now: float | None = None) -> str:
    now = now or time.time()
    body = {"sub": sub, "role": role, "iat": int(now), "exp": int(now) + ttl_seconds}
    payload = _b64(json.dumps(body, sort_keys=True).encode())
    return f"{payload}.{_sign(payload, secret)}"


def verify(token: str, secret: str, now: float | None = None) -> dict | None:
    """Return the decoded claims, or None if tampered/expired/malformed."""
    try:
        payload_b64, sig = token.split(".", 1)
    except (ValueError, AttributeError):
        return None
    if not hmac.compare_digest(sig, _sign(payload_b64, secret)):
        return None
    try:
        claims = json.loads(_unb64(payload_b64).decode())
    except (json.JSONDecodeError, Exception):
        return None
    now = now or time.time()
    if claims.get("exp", 0) < now:
        return None
    return claims