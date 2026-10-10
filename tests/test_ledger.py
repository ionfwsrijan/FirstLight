import os
import sqlite3
import sys
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import tempfile

from firstlight.ledger import LEDGER_TABLE, Ledger


class TestLedger(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".db")
        self.tmp.close()
        self.conn = sqlite3.connect(self.tmp.name)
        self.conn.executescript(LEDGER_TABLE)
        self.ledger = Ledger(self.conn)

    def tearDown(self):
        self.conn.close()
        os.unlink(self.tmp.name)

    def test_append_and_verify(self):
        self.ledger.append("decision", "s1", {"level": "CLOSED"})
        self.ledger.append("alert", "s1", {"cert": "abc"})
        result = self.ledger.verify()
        self.assertTrue(result["ok"])
        self.assertEqual(result["rows"], 2)

    def test_tamper_detected(self):
        self.ledger.append("decision", "s1", {"level": "CLOSED"})
        self.ledger.append("alert", "s1", {"cert": "abc"})
        # Retroactively edit a past payload -> chain breaks.
        self.conn.execute("UPDATE ledger SET payload=? WHERE seq=1", ('{"level":"GREEN"}',))
        self.conn.commit()
        result = self.ledger.verify()
        self.assertFalse(result["ok"])

    def test_entries_ordered_desc(self):
        self.ledger.append("a", "x", {})
        self.ledger.append("b", "x", {})
        entries = self.ledger.entries(limit=10)
        self.assertEqual(entries[0]["kind"], "b")
        self.assertEqual(entries[1]["kind"], "a")

    def test_empty_ledger_ok(self):
        result = self.ledger.verify()
        self.assertTrue(result["ok"])
        self.assertEqual(result["rows"], 0)


if __name__ == "__main__":
    unittest.main()
