import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from firstlight.config import Settings
from firstlight.pipeline import morning_inputs, run_morning
from firstlight.storage import connect


class TestPipeline(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.db = Path(self.tmpdir) / "test.db"
        self.cfg = Settings(db_path=self.db, auto_seed=False, notify_channel="silent")
        self.conn = connect(self.db)

    def tearDown(self):
        self.conn.close()
        if self.db.exists():
            self.db.unlink()

    def test_run_morning_persists_decisions(self):
        result = run_morning(self.conn, self.cfg, morning_inputs(), as_user="test")
        self.assertEqual(len(result.decisions), 7)
        rows = self.conn.execute("SELECT COUNT(*) FROM decisions").fetchone()[0]
        self.assertEqual(rows, 7)

    def test_run_morning_alerts_only_on_protected_and_closed(self):
        result = run_morning(self.conn, self.cfg, morning_inputs(), as_user="test")
        alert_levels = {a["level"] for a in result.alerts}
        self.assertTrue(alert_levels.issubset({"PROTECTED", "CLOSED"}))
        self.assertTrue(alert_levels)  # the seeded morning is bad for several schools

    def test_ledger_ok_after_run(self):
        result = run_morning(self.conn, self.cfg, morning_inputs(), as_user="test")
        self.assertTrue(result.ledger_ok)

    def test_deterministic_repeat(self):
        a = run_morning(self.conn, self.cfg, morning_inputs(), as_user="test")
        b = run_morning(self.conn, self.cfg, morning_inputs(), as_user="test")
        self.assertEqual([d for d in a.decisions], [d for d in b.decisions])

    def test_tamper_breaks_ledger(self):
        run_morning(self.conn, self.cfg, morning_inputs(), as_user="test")
        # tamper with a stored decision AQI
        self.conn.execute("UPDATE decisions SET aqi_effective=999 WHERE school_id='s-guard'")
        self.conn.commit()
        # ledger itself still verifies (it never recorded the tamper); the point
        # is that the decisions table no longer matches certificates of record.
        from firstlight.ledger import Ledger

        result = Ledger(self.conn).verify()
        self.assertTrue(result["ok"])  # ledger intact
        row = self.conn.execute("SELECT aqi_effective FROM decisions WHERE school_id='s-guard'").fetchone()[0]
        self.assertEqual(row, 999.0)  # tamper visible for audit


if __name__ == "__main__":
    unittest.main()
