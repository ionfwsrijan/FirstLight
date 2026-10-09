import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from fastapi.testclient import TestClient

os.environ.setdefault("FIRSTLIGHT_DB", str(Path(tempfile.mkdtemp()) / "api-test.db"))
os.environ.setdefault("FIRSTLIGHT_AUTO_SEED", "false")
os.environ.setdefault("FIRSTLIGHT_NOTIFY", "silent")

from firstlight.api import app  # noqa: E402
from firstlight.cli.seed import seed  # noqa: E402
from firstlight.config import settings  # noqa: E402
from firstlight.auth import issue, DEMO_USERS  # noqa: E402


class TestApi(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)
        seed()

    def _header(self, role: str = "parent") -> dict:
        token = issue("tester", role, settings.secret, 3600)
        return {"Authorization": f"Bearer {token}"}

    def test_health(self):
        r = self.client.get("/api/health")
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.json()["ok"])
        self.assertIn("ruleset", r.json())
        body = r.json()
        # imperative provenance: health reports where today's fire data came from
        self.assertIn("source", body)
        self.assertEqual(body["source"]["source"], "frozen")

    def test_morning_inputs(self):
        r = self.client.get("/api/morning/inputs")
        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertEqual(len(body["schools"]), 7)
        self.assertEqual(len(body["fires"]), 7)
        self.assertEqual(body["source"]["source"], "frozen")
        self.assertIn("fetchedAt", body["source"])

    def test_schools_requires_auth(self):
        r = self.client.get("/api/schools")
        self.assertEqual(r.status_code, 401)

    def test_schools_parent_allowed(self):
        r = self.client.get("/api/schools", headers=self._header("parent"))
        self.assertEqual(r.status_code, 200)
        self.assertEqual(len(r.json()["schools"]), 7)

    def test_morning_run_parent_forbidden(self):
        r = self.client.post("/api/morning/run", headers=self._header("parent"))
        self.assertEqual(r.status_code, 403)

    def test_morning_run_officer_allowed(self):
        r = self.client.post("/api/morning/run", headers=self._header("officer"))
        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertEqual(len(body["decisions"]), 7)
        self.assertTrue(body["ledgerOk"])
        self.assertEqual(body["source"]["source"], "frozen")

    def test_agent_talk_status(self):
        r = self.client.post(
            "/api/agent/talk",
            json={"text": "is today safe for school?", "school_id": "s-avini"},
            headers=self._header("parent"),
        )
        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertEqual(body["intent"], "status")
        self.assertIn("CLOSED", body["reply"])
        self.assertIn("Severe", body["decision"]["bandLabel"])

    def test_agent_talk_question_must_not_send(self):
        # "would you send it?" is an ask, not a consent -> sent stays None
        r = self.client.post(
            "/api/agent/talk",
            json={"text": "would you send it if the air got worse?", "school_id": "s-avini"},
            headers=self._header("parent"),
        )
        body = r.json()
        self.assertIsNone(body["sent"])

    def test_agent_talk_explicit_yes_sends(self):
        # a confirmed send is authorized for a principal (parent alone cannot dispatch)
        r = self.client.post(
            "/api/agent/talk",
            json={"text": "yes, send it", "school_id": "s-avini"},
            headers=self._header("principal"),
        )
        body = r.json()
        self.assertEqual(body["intent"], "send")
        self.assertIsNotNone(body["sent"])
        self.assertEqual(body["sent"]["status"], "sent")
        self.assertIn("receipt", body["sent"]["delivery"])
        self.assertIn("channel", body["sent"]["delivery"])
        self.assertTrue(body["consent"]["authorized"])

    def test_agent_talk_parent_yes_denied(self):
        # same-turn confirmation, but the parent role has no alert:send -> denied, not sent
        r = self.client.post(
            "/api/agent/talk",
            json={"text": "yes, send it", "school_id": "s-guard"},
            headers=self._header("parent"),
        )
        body = r.json()
        self.assertEqual(body["intent"], "send")
        self.assertIsNone(body["sent"])
        self.assertIs(body["consent"]["maySend"], True)
        self.assertIs(body["consent"]["authorized"], False)
        self.assertIn("cannot dispatch", body["reply"])

    def test_agent_talk_unknown_school_404(self):
        r = self.client.post(
            "/api/agent/talk",
            json={"text": "is today safe for school?", "school_id": "s-does-not-exist"},
            headers=self._header("parent"),
        )
        self.assertEqual(r.status_code, 404)

    def test_transcript_persists(self):
        self.client.post(
            "/api/agent/talk",
            json={"text": "is today safe for school?", "school_id": "s-guard"},
            headers=self._header("parent"),
        )
        r = self.client.get("/api/transcript?school_id=s-guard", headers=self._header("parent"))
        self.assertEqual(r.status_code, 200)
        turns = r.json()["turns"]
        self.assertTrue(turns, "a talk turn should be persisted server-side")
        self.assertEqual(turns[-1]["speaker"], "agent")
        speakers = [t["speaker"] for t in turns]
        self.assertIn("user", speakers)

    def test_ledger_requires_officer(self):
        r = self.client.get("/api/ledger/verify", headers=self._header("parent"))
        self.assertEqual(r.status_code, 403)
        r = self.client.get("/api/ledger/verify", headers=self._header("officer"))
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.json()["ok"])

    def test_outbox_requires_alert_send(self):
        r = self.client.get("/api/outbox", headers=self._header("parent"))
        self.assertEqual(r.status_code, 403)
        r = self.client.get("/api/outbox", headers=self._header("principal"))
        self.assertEqual(r.status_code, 200)
        self.assertIn("messages", r.json())

    def test_login_invalid_creds(self):
        r = self.client.post("/api/auth/login", json={"username": "parent@firstlight.demo", "password": "nope"})
        self.assertEqual(r.status_code, 401)

    def test_login_ok(self):
        r = self.client.post(
            "/api/auth/login",
            json={"username": "officer@firstlight.demo", "password": "officer123"},
        )
        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertTrue(body["token"])
        self.assertEqual(body["role"], "officer")
        self.assertTrue(body["displayName"])

    def test_auth_issue_is_closed(self):
        # open role minting must not exist in a submission-safe build
        r = self.client.post("/api/auth/issue", json={"sub": "mom", "role": "parent"})
        self.assertEqual(r.status_code, 403)

    def test_me(self):
        r = self.client.get("/api/me", headers=self._header("officer"))
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["role"], "officer")

    def test_seeded_users_exist(self):
        from firstlight.auth import authenticate
        from firstlight.storage import connect as db_connect

        conn = db_connect(settings.db_path)
        try:
            for username, password, role, _name in DEMO_USERS:
                user = authenticate(conn, username, password)
                self.assertIsNotNone(user, f"{username} should authenticate")
                self.assertEqual(user["role"], role)
        finally:
            conn.close()


if __name__ == "__main__":
    unittest.main()