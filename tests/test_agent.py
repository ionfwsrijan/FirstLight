import os
import sys
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from firstlight.agent import ConsentState, consent_turn, parse
from firstlight.agent.certificate import RULESET_VERSION, sign, verify
from firstlight.domain import Decision, Level, RuleHit


class TestIntents(unittest.TestCase):
    def test_status(self):
        self.assertEqual(parse("is today safe for school?").name, "status")

    def test_why(self):
        self.assertEqual(parse("why?").name, "why")
        self.assertEqual(parse("kyun itna bad?").name, "why")

    def test_change(self):
        self.assertEqual(parse("what changed overnight?").name, "change")
        self.assertEqual(parse("stubble fires?").name, "change")

    def test_actions(self):
        self.assertEqual(parse("what do we do?").name, "actions")

    def test_send(self):
        self.assertEqual(parse("send it to parents").name, "send")
        self.assertEqual(parse("bhejo").name, "send")

    def test_recall(self):
        self.assertEqual(parse("cancel the alert").name, "recall")
        self.assertEqual(parse("wapis le lo").name, "recall")

    def test_greet_empty(self):
        self.assertEqual(parse("").name, "greet")
        self.assertEqual(parse("hello").name, "greet")

    def test_unknown(self):
        self.assertEqual(parse("qwerty nonsense").name, "unknown")


class TestConsent(unittest.TestCase):
    def test_question_must_not_send(self):
        state = ConsentState()
        gate = consent_turn(state, "send", "would you send it if asked?")
        self.assertFalse(gate["maySend"])

    def test_explicit_confirm_sends(self):
        state = ConsentState()
        gate = consent_turn(state, "send", "yes, send it")
        self.assertTrue(gate["maySend"])

    def test_send_requires_own_turn(self):
        state = ConsentState()
        state.observe("send", "send it")  # earlier turn asked
        gate = consent_turn(state, "why", "ok go ahead")
        self.assertFalse(gate["maySend"])  # new turn is 'why', not a send

    def test_status_never_sends(self):
        state = ConsentState()
        gate = consent_turn(state, "status", "is it safe?")
        self.assertFalse(gate["maySend"])

    def test_recall_intent_does_not_send(self):
        state = ConsentState()
        gate = consent_turn(state, "recall", "cancel")
        self.assertFalse(gate["maySend"])


def _decision() -> Decision:
    school_id = "s-avini"
    return Decision(
        school_id=school_id,
        date="2026-10-08",
        level=Level.CLOSED,
        aqi_effective=442.0,
        band_label="Severe",
        band_hex="#8a1320",
        grap_stage=3,
        fires_upwind=6,
        plume_score=3.0,
        trend="rising",
        reasons=(RuleHit("R-CLOSE-401", "Severe", "AQI>=401 closes", True),),
        actions=("Declare online day",),
        evidence={"features": {"aqi_eff": 442.0}},
    )


class TestCertificate(unittest.TestCase):
    def test_sign_and_verify(self):
        cert = sign(_decision(), "secret")
        claims = verify(cert, "secret")
        self.assertIsNotNone(claims)
        self.assertEqual(claims["schoolId"], "s-avini")
        self.assertEqual(claims["level"], 2)
        self.assertEqual(claims["ruleset"], RULESET_VERSION)

    def test_wrong_secret_rejected(self):
        cert = sign(_decision(), "secret")
        self.assertIsNone(verify(cert, "wrong-secret"))

    def test_tampered_rejected(self):
        cert = sign(_decision(), "secret")
        sig, canonical = cert.split(":", 1)
        forged = sig + ":" + canonical.replace('"aqiEffective": 442.0', '"aqiEffective": 150.0')
        self.assertIsNone(verify(forged, "secret"))

    def test_malformed_rejected(self):
        self.assertIsNone(verify("garbage", "secret"))


if __name__ == "__main__":
    unittest.main()
