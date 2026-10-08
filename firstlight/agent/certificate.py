"""Decision certificates: HMAC-signed, verifiable statements of record.

A certificate binds the school, date, level, AQI, band, GRAP stage, plume
score, and ruleset version to a signature. Anyone holding the public ruleset
(or the server secret in private operation) can verify that the certificate
was issued by this engine and has not been altered.

This is what FirstLight means by "recovered means proven": a recalled or
disputed alert has a certificate to audit.
"""

from __future__ import annotations

import hashlib
import hmac
import json

from .. import RULESET_VERSION
from ..domain import Decision

SALT = "firstlight-cert-v1"


def _canonical(decision: Decision) -> str:
    payload = {
        "schoolId": decision.school_id,
        "date": decision.date,
        "level": int(decision.level),
        "aqiEffective": round(decision.aqi_effective, 1),
        "band": decision.band_label,
        "grapStage": decision.grap_stage,
        "plumeScore": round(decision.plume_score, 3),
        "pirativeFiresUpwind": decision.fires_upwind,
        "ruleset": RULESET_VERSION,
    }
    return json.dumps(payload, sort_keys=True)


def sign(decision: Decision, secret: str) -> str:
    canonical = _canonical(decision)
    sig = hmac.new((secret + SALT).encode(), canonical.encode(), hashlib.sha256).hexdigest()
    return f"{sig}:{canonical}"


def verify(cert: str, secret: str) -> dict | None:
    """Return the certified claims if the certificate is authentic."""
    try:
        sig, canonical = cert.split(":", 1)
    except (ValueError, AttributeError):
        return None
    expected = hmac.new((secret + SALT).encode(), canonical.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(sig, expected):
        return None
    return json.loads(canonical)