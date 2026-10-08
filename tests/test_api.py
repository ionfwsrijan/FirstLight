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
from firstlight.auth import issue  # noqa: E402


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

    def test_morning_inputs(self):
        r = self.client.get("/api/morning/inputs")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(len(r.json()["schools"]), 7)
        self.assertEqual(len(r.json()["fires"]), 7)

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

    def test_agent_talk_status(self):
        r = self.client.post(
            "/api/agent/talk",
            json={"text": "is today safe for school?", "school_id": "s-avini", "caller": "parent"},
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
        r = self.client.post(
            "/api/agent/talk",
            json={"text": "yes, send it", "school_id": "s-avini"},
            headers=self._header("parent"),
        )
        body = r.json()
        self.assertIn(body["intent"], ("send",))
        self.assertIsNotNone(body["sent"])
        self.assertEqual(body["sent"]["status"], "sent")

    def test_ledger_requires_officer(self):
        r = self.client.get("/api/ledger/verify", headers=self._header("parent"))
        self.assertEqual(r.status_code, 403)
        r = self.client.get("/api/ledger/verify", headers=self._header("officer"))
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.json()["ok"])

    def test_auth_issue(self):
        r = self.client.post("/api/auth/issue", json={"sub": "mom", "role": "parent"})
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.json()["token"])

    def test_me(self):
        r = self.client.get("/api/me", headers=self._header("officer"))
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["role"], "officer")


if __name__ == "__main__":
    unittest.main()