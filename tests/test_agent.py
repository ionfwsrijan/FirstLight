import os
import sys
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from firstlight import agent


class TestAgentIntent(unittest.TestCase):
    def test_greet(self):
        t = agent.answer("parent", "s-avini", "")
        self.assertEqual(t.intent, "greet")

    def test_reason_intent(self):
        t = agent.answer("parent", "s-avini", "why?")
        self.assertEqual(t.intent, "reason")

    def test_reason_contains_engine_text(self):
        t = agent.answer("parent", "s-avini", "why is it bad")
        self.assertEqual(t.intent, "reason")
        self.assertIn("AQI", t.reply)

    def test_safe_word_returns_status(self):
        t = agent.answer("parent", "s-avini", "is today safe for school?")
        self.assertEqual(t.intent, "safe")
        self.assertIn("RED", t.reply)

    def test_ask_fires(self):
        t = agent.answer("parent", "s-avini", "what changed overnight? any fires?")
        self.assertEqual(t.intent, "ask")
        assert "fire" in t.reply.lower() or "stubble" in t.reply.lower()

    def test_actions(self):
        t = agent.answer("parent", "s-avini", "what do we do")
        self.assertEqual(t.intent, "actions")

    def test_fallback(self):
        t = agent.answer("parent", "s-avini", "hello there")
        self.assertEqual(t.intent, "fallback")


class TestConsentGate(unittest.TestCase):
    def test_yes_never_sends(self):
        agent.reset_session()
        t = agent.answer("parent", "s-avini", "yes sure")
        self.assertFalse(t.notified)
        self.assertIsNone(t.sent)

    def test_no_send_without_phrase(self):
        agent.reset_session()
        t = agent.answer("parent", "s-avini", "please let parents know")
        self.assertFalse(t.notified)

    def test_send_requires_exact_phrase(self):
        agent.reset_session()
        t = agent.answer("parent", "s-avini", "send it")
        self.assertTrue(t.notified)
        self.assertIsNotNone(t.sent)
        self.assertIn("FIRSTLIGHT-", t.sent["reference"])

    def test_synonym_send(self):
        agent.reset_session()
        t = agent.answer("parent", "s-avini", "send the alert now")
        self.assertTrue(t.notified)

    def test_recall_requires_history(self):
        agent.reset_session()
        t = agent.answer("parent", "s-avini", "cancel the alert")
        self.assertNotIn("withdrawn", t.reply)

    def test_send_then_recall_pop(self):
        agent.reset_session()
        agent.answer("parent", "s-avini", "send it")
        t = agent.answer("parent", "s-avini", "cancel the alert")
        self.assertIn("withdrawn", t.reply)
        self.assertEqual(len(agent.notification_ledger()), 0)

    def test_send_ledger_growth(self):
        agent.reset_session()
        agent.answer("parent", "s-avini", "send it")
        agent.answer("parent", "s-avini", "send to parents")
        self.assertEqual(len(agent.notification_ledger()), 2)


class TestDecisionMirroring(unittest.TestCase):
    def test_decision_present_and_static(self):
        agent.reset_session()
        t = agent.answer("parent", "s-avini", "send it")
        self.assertEqual(t.decision["levelName"], "RED")
        self.assertEqual(t.sent["message"], "School day status: RED")

    def test_different_schools_differ(self):
        a = agent.answer("parent", "s-avini", "").decision["aqi"]
        b = agent.answer("parent", "s-granite", "").decision["aqi"]
        self.assertGreater(a, b)


if __name__ == "__main__":
    unittest.main()