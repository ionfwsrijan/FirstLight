import os
import sys
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "sam")))


class _FakeTable:
    def __init__(self):
        self.items = []
        self.puts = []
        self._counter = 0

    def put_item(self, Item):
        self.puts.append(Item)
        self.items.append(Item)

    def update_item(self, **kw):
        self._counter += 1
        return {"Attributes": {"c": self._counter}}

    def query(self, **kw):
        return {"Items": []}

    def scan(self, **kw):
        return {"Items": []}


class _FakeResource:
    def Table(self, name):
        return _FakeTable()


class _FakeBoto3:
    def resource(self, _name):
        return _FakeResource()
    def client(self, *_a, **_k):
        return object()


class TestShipItMirror(unittest.TestCase):
    def setUp(self):
        os.environ["TABLE_NAME"] = "firstlight-test"
        os.environ["RULESET_VERSION"] = "firstlight-rules-v2@2026-10"
        os.environ["ALERT_HOOK_URL"] = ""
        sys.modules["boto3"] = _FakeBoto3()
        from sam.handlers import morning as m  # noqa: PLC0415
        from sam.handlers import meta as mm  # noqa: PLC0415
        from sam.handlers import talk as t  # noqa: PLC0415

        self.morning = m
        self.meta = mm
        self.talk = t

    @staticmethod
    def _claims(**kw):
        claims = {"sub": "kapoor", "email": "officer@firstlight.demo"}
        claims.update(kw)
        return {"requestContext": {"authorizer": {"claims": claims}}}

    @staticmethod
    def _body(response):
        body = response["body"]
        return body if isinstance(body, dict) else __import__("json").loads(body)

    def test_morning_run_matches_local_verdicts(self):
        from firstlight.engine import decide_all
        from firstlight.pipeline.scenario import morning_inputs

        local = {d.school_id: d.level.name_short for d in decide_all(morning_inputs())}
        event = {"body": "{}", **self._claims()}
        response = self.morning.handler(event, None)
        self.assertEqual(response["statusCode"], 200)
        body = self._body(response)
        cloud = {d["schoolId"]: d["levelName"] for d in body["decisions"]}
        self.assertEqual(cloud, local)
        self.assertEqual(len(body["decisions"]), 7)

    def test_morning_run_denied_for_parent(self):
        event = {"body": "{}", **self._claims(email="parent@firstlight.demo", sub="meera")}
        response = self.morning.handler(event, None)
        self.assertEqual(response["statusCode"], 403)

    def test_agent_question_never_sends(self):
        event = {
            "body": '{"text": "would you send it if it got worse?", "school_id": "s-avini"}',
            **self._claims(email="parent@firstlight.demo", sub="meera"),
        }
        response = self.talk.handler(event, None)
        body = self._body(response)
        self.assertIsNone(body["sent"])

    def test_agent_explicit_yes_sends_for_officer(self):
        event = {
            "body": '{"text": "yes, send it", "school_id": "s-avini"}',
            **self._claims(),
        }
        response = self.talk.handler(event, None)
        body = self._body(response)
        self.assertIsNotNone(body["sent"])
        self.assertEqual(body["sent"]["status"], "sent")
        # Ship It mirrors delivery: a receipt/channel is attached even with no hook set
        self.assertIn("delivery", body["sent"])
        self.assertIn("channel", body["sent"]["delivery"])

    def test_agent_confirmed_send_denied_for_parent(self):
        event = {
            "body": '{"text": "yes, send it", "school_id": "s-avini"}',
            **self._claims(email="parent@firstlight.demo", sub="meera"),
        }
        response = self.talk.handler(event, None)
        body = self._body(response)
        self.assertIsNone(body["sent"])
        self.assertIs(body["consent"]["maySend"], True)
        self.assertIs(body["consent"]["authorized"], False)

    def test_agent_persists_transcript_turns(self):
        event = {
            "body": '{"text": "how is today?", "school_id": "s-avini"}',
            **self._claims(),
        }
        response = self.talk.handler(event, None)
        self.assertEqual(response["statusCode"], 200)
        self.assertIn("turn", self._body(response))

    def test_meta_endpoints_shape(self):
        endpoints = [
            ("/health", None),
            ("/inputs", None),
            ("/schools", None),
            ("/transcript", {"school_id": "s-avini"}),
            ("/ledger", None),
            ("/ledger/verify", None),
            ("/outbox", None),
        ]
        for path, query in endpoints:
            event = {"httpMethod": "GET", "path": path, "queryStringParameters": query,
                     "requestContext": {"authorizer": {"claims": {"sub": "kapoor",
                                                                  "email": "officer@firstlight.demo"}}}}
            response = self.meta.handler(event, None)
            self.assertEqual(response["statusCode"], 200, path)
            self.assertIn("body", response)

    def test_meta_refresh_is_honest_frozen(self):
        event = {"httpMethod": "POST", "path": "/sources/refresh",
                 "requestContext": {"authorizer": {"claims": {"sub": "kapoor",
                                                              "email": "officer@firstlight.demo"}}}}
        response = self.meta.handler(event, None)
        body = self._body(response)
        self.assertEqual(response["statusCode"], 200)
        self.assertEqual(body["source"], "frozen")
        self.assertTrue(body["fallback"])

    def test_unknown_school_404(self):
        event = {"body": '{"text": "hi", "school_id": "nope"}', "requestContext": {}}
        response = self.talk.handler(event, None)
        self.assertEqual(response["statusCode"], 404)


if __name__ == "__main__":
    unittest.main()