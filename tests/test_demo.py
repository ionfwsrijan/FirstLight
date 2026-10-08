import os
import sys
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from firstlight import demo


class TestDemo(unittest.TestCase):
    def test_script_length(self):
        r = demo.run("s-avini")
        self.assertEqual(len(r["turns"]), 6)

    def test_script_school_header(self):
        r = demo.run("s-avini")
        self.assertEqual(r["schoolId"], "s-avini")
        self.assertEqual(r["date"], "2026-10-08")

    def test_script_deterministic(self):
        a = demo.run("s-avini")
        b = demo.run("s-avini")
        self.assertEqual(a, b)

    def test_send_happens_and_is_then_recalled(self):
        r = demo.run("s-avini")
        notified = [t for t in r["turns"] if t["notified"]]
        self.assertEqual(len(notified), 2)  # "send it" then re-announce
        self.assertTrue(r["turns"][3]["sent"])
        self.assertTrue(r["turns"][5]["sent"])

    def test_reply_text_nonempty(self):
        for turn in demo.run("s-avini")["turns"]:
            self.assertTrue(turn["reply"].strip())


if __name__ == "__main__":
    unittest.main()