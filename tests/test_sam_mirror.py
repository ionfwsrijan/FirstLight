import os
import sys
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "sam")))


class _FakeTable:
    def __init__(self):
        self.items = []
        self.puts = []

    def put_item(self, Item):
        self.puts.append(Item)
        self.items.append(Item)

    def query(self, **kw):
        return {"Items": []}


class _FakeResource:
    def Table(self, name):
        return _FakeTable()


class _FakeBoto3:
    def resource(self, _name):
        return _FakeResource()


class TestShipItMirror(unittest.TestCase):
    def setUp(self):
        os.environ["TABLE_NAME"] = "firstlight-test"
        os.environ["RULESET_VERSION"] = "firstlight-rules-v2@2026-10"
        os.environ["ALERT_HOOK_URL"] = ""
        sys.modules["boto3"] = _FakeBoto3()
        from sam.handlers import morning as m  # noqa: PLC0415
        from sam.handlers import talk as t  # noqa: PLC0415

        self.morning = m
        self.talk = t

    def test_morning_run_matches_local_verdicts(self):
        from firstlight.engine import decide_all
        from firstlight.pipeline.scenario import morning_inputs

        local = {d.school_id: d.level.name_short for d in decide_all(morning_inputs())}
        event = {"body": "{}", "requestContext": {"authorizer": {"claims": {"sub": "sam-test"}}}}
        response = self.morning.handler(event, None)
        self.assertEqual(response["statusCode"], 200)
        body = response["body"]
        body = body if isinstance(body, dict) else __import__("json").loads(body)
        cloud = {d["schoolId"]: d["levelName"] for d in body["decisions"]}
        self.assertEqual(cloud, local)
        self.assertEqual(len(body["decisions"]), 7)

    def test_agent_question_never_sends(self):
        event = {
            "body": '{"text": "would you send it if it got worse?", "school_id": "s-avini"}',
            "requestContext": {"authorizer": {"claims": {"sub": "parent"}}},
        }
        response = self.talk.handler(event, None)
        body = __import__("json").loads(response["body"])
        self.assertIsNone(body["sent"])

    def test_agent_explicit_yes_sends(self):
        event = {
            "body": '{"text": "yes, send it", "school_id": "s-avini"}',
            "requestContext": {"authorizer": {"claims": {"sub": "parent"}}},
        }
        response = self.talk.handler(event, None)
        body = __import__("json").loads(response["body"])
        self.assertIsNotNone(body["sent"])
        self.assertEqual(body["sent"]["status"], "sent")
        # Ship It mirrors delivery: a receipt/channel is attached even with no hook set
        self.assertIn("delivery", body["sent"])
        self.assertIn("channel", body["sent"]["delivery"])

    def test_unknown_school_404(self):
        event = {"body": '{"text": "hi", "school_id": "nope"}', "requestContext": {}}
        response = self.talk.handler(event, None)
        self.assertEqual(response["statusCode"], 404)


if __name__ == "__main__":
    unittest.main()