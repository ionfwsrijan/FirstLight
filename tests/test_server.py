import json
import os
import sys
import threading
import unittest
import urllib.request

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from firstlight.server import Handler, PORT  # noqa: F401


def _get(path):
    with urllib.request.urlopen("http://127.0.0.1:8000" + path, timeout=5) as r:
        return r.status, json.loads(r.read().decode())


def _post(path, payload):
    body = json.dumps(payload).encode()
    req = urllib.request.Request(
        "http://127.0.0.1:8000" + path,
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=5) as r:
        return r.status, json.loads(r.read().decode())


class TestServerLive(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from http.server import ThreadingHTTPServer

        cls.server = ThreadingHTTPServer(("127.0.0.1", 8000), Handler)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()

    def test_health(self):
        st, body = _get("/api/health")
        self.assertEqual(st, 200)
        self.assertTrue(body["ok"])

    def test_snapshot(self):
        st, body = _get("/api/snapshot")
        self.assertEqual(st, 200)
        self.assertEqual(len(body["schools"]), 6)

    def test_ledger_endpoint(self):
        st, body = _get("/api/ledger")
        self.assertEqual(st, 200)
        self.assertIn("what_changed", body)

    def test_bands_endpoint(self):
        st, body = _get("/api/bands")
        self.assertEqual(st, 200)
        self.assertEqual(len(body["bands"]), 6)

    def test_turn_endpoint(self):
        st, body = _post("/api/turn", {"caller": "parent", "schoolId": "s-avini", "text": "send it"})
        self.assertEqual(st, 200)
        self.assertTrue(body["ok"])
        self.assertTrue(body["turn"]["notified"])
        self.assertEqual(body["turn"]["decision"]["levelName"], "RED")

    def test_demo_endpoint(self):
        st, body = _get("/api/demo?school=s-avini")
        self.assertEqual(st, 200)
        self.assertEqual(len(body["turns"]), 6)

    def test_index_html(self):
        req = urllib.request.Request("http://127.0.0.1:8000/", method="GET")
        with urllib.request.urlopen(req, timeout=5) as r:
            html = r.read().decode()
        self.assertEqual(r.status, 200)
        self.assertIn("FirstLight", html)


if __name__ == "__main__":
    unittest.main()