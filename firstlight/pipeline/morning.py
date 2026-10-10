"""The scheduled morning: ingest snapshot, decide every school, persist,
alert, and append to the tamper-evident ledger.

`pipeline(app)` is the Build It entry. `pipeline_lambda(...)` mirrors it for
the Ship It SAM template (see sam/handlers/morning.py). Both share the same
core orchestration so the local and cloud behaviors cannot drift.
"""

from __future__ import annotations

import logging
import sqlite3
from dataclasses import dataclass

from .. import RULESET_VERSION
from ..agent import narrate, sign
from ..config import Settings
from ..domain import MorningInputs
from ..engine import decide_all
from ..ledger import Ledger
from ..notifier import build
from ..storage import AlertsRepo, DecisionsRepo, HistoryRepo

log = logging.getLogger("firstlight.pipeline")


@dataclass
class MorningResult:
    date: str
    decisions: list[dict]
    alerts: list[dict]
    ledger_ok: bool
    ruleset: str

    def to_dict(self) -> dict:
        return {
            "date": self.date,
            "decisions": self.decisions,
            "alerts": self.alerts,
            "ledgerOk": self.ledger_ok,
            "ruleset": self.ruleset,
        }


def run_morning(conn: sqlite3.Connection, cfg: Settings, inputs: MorningInputs, as_user: str = "pipeline") -> MorningResult:
    """Run the full morning: decide, persist, alert, and record to the ledger."""
    ledger = Ledger(conn)
    decisions_repo = DecisionsRepo(conn)
    alerts_repo = AlertsRepo(conn)
    history_repo = HistoryRepo(conn)
    notifier = build(cfg.notify_channel, cfg)

    decisions = decide_all(inputs)
    persisted: list[dict] = []
    alerts: list[dict] = []

    for d in decisions:
        decisions_repo.save(d)
        history_repo.set_morning(d.school_id, inputs.date, d.aqi_effective)
        persisted.append(d.to_dict())
        cert = sign(d, cfg.secret)
        ledger.append(
            "decision",
            d.school_id,
            {
                "date": d.date,
                "level": d.level.name_short,
                "aqiEffective": round(d.aqi_effective, 1),
                "grapStage": d.grap_stage,
                "cert": cert,
            },
        )

        should_alert = d.level.name_short in ("PROTECTED", "CLOSED")
        if should_alert:
            message = narrate(next(s for s in inputs.schools if s.id == d.school_id), d)
            receipt = notifier.notify(school_id=d.school_id, level=d.level.name_short, message=message)
            channel = cfg.notify_channel
            alert_id = alerts_repo.save_alert(
                d.school_id, d.date, int(d.level), d.level.name_short, message, as_user, cert,
                channel=channel, receipt=receipt,
            )
            ledger.append(
                "alert",
                d.school_id,
                {"alertId": alert_id, "receipt": receipt, "cert": cert, "channel": channel},
            )
            alerts.append(
                {
                    "alertId": alert_id,
                    "schoolId": d.school_id,
                    "level": d.level.name_short,
                    "receipt": receipt,
                    "channel": channel,
                }
            )

    ledger.append("morning_run", inputs.date, {"asUser": as_user, "ruleset": RULESET_VERSION})
    conn.commit()
    return MorningResult(inputs.date, persisted, alerts, ledger.verify()["ok"], RULESET_VERSION)
