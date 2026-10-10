import dataclasses
import io
import json
import os
import sys
import unittest
from contextlib import redirect_stdout
from unittest import mock

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import firstlight.notifier as notifier  # noqa: E402
from firstlight.config import Settings  # noqa: E402


class TestConsoleAndSilent(unittest.TestCase):
    def test_console_prints_and_returns_receipt(self):
        buf = io.StringIO()
        with redirect_stdout(buf):
            receipt = notifier.ConsoleNotifier().notify(
                school_id="s-avini", level="CLOSED", message="go online"
            )
        self.assertEqual(receipt, "console-s-avini")
        self.assertIn("s-avini", buf.getvalue())
        self.assertIn("CLOSED", buf.getvalue())

    def test_silent_returns_receipt_without_output(self):
        buf = io.StringIO()
        with redirect_stdout(buf):
            receipt = notifier.SilentNotifier().notify(
                school_id="s-guard", level="PROTECTED", message="masks"
            )
        self.assertEqual(receipt, "silent-s-guard")
        self.assertEqual(buf.getvalue(), "")


class TestSmtpNotifier(unittest.TestCase):
    def test_unconfigured_is_a_clear_receipt_not_a_crash(self):
        n = notifier.SmtpNotifier(host="", port=587, user="", password="", to="")
        self.assertEqual(
            n.notify(school_id="s-apj", level="CLOSED", message="x"),
            "smtp-unconfigured-s-apj",
        )

    def test_success_path_starttls_login_sendmail(self):
        n = notifier.SmtpNotifier("smtp.example", 587, "bot@example", "pw", "ops@example")
        server = mock.MagicMock()
        server.__enter__.return_value = server
        with mock.patch.object(notifier.smtplib, "SMTP", return_value=server) as smtp:
            receipt = n.notify(school_id="s-noida", level="CLOSED", message="hi")
        self.assertEqual(receipt, "smtp-s-noida")
        smtp.assert_called_once_with("smtp.example", 587, timeout=10)
        server.starttls.assert_called_once()
        server.login.assert_called_once_with("bot@example", "pw")
        server.sendmail.assert_called_once()

    def test_failure_is_swallowed_and_recorded(self):
        n = notifier.SmtpNotifier("smtp.example", 587, "bot@example", "pw", "ops@example")
        with mock.patch.object(notifier.smtplib, "SMTP", side_effect=OSError("refused")):
            buf = io.StringIO()
            with redirect_stdout(buf):
                receipt = n.notify(school_id="s-dwarka", level="CLOSED", message="hi")
        self.assertEqual(receipt, "smtp-failed-s-dwarka")
        self.assertIn("failed s-dwarka", buf.getvalue())


class TestWebhookNotifier(unittest.TestCase):
    def test_unconfigured_is_a_clear_receipt_not_a_crash(self):
        self.assertEqual(
            notifier.WebhookNotifier("").notify(
                school_id="s-spring", level="CLOSED", message="x"
            ),
            "webhook-unconfigured-s-spring",
        )

    def test_success_posts_json_body(self):
        n = notifier.WebhookNotifier("https://hooks.example/x")
        captured = {}

        def fake_urlopen(req, timeout=0):
            captured["url"] = req.full_url
            captured["body"] = req.data
            captured["method"] = req.get_method()
            return mock.MagicMock()

        with mock.patch.object(notifier.urllib.request, "urlopen", side_effect=fake_urlopen):
            receipt = n.notify(school_id="s-gurugram", level="PROTECTED", message="keep windows shut")

        self.assertEqual(receipt, "webhook-s-gurugram")
        self.assertEqual(captured["url"], "https://hooks.example/x")
        self.assertEqual(captured["method"], "POST")
        payload = json.loads(captured["body"])
        self.assertEqual(payload, {
            "school": "s-gurugram",
            "level": "PROTECTED",
            "message": "keep windows shut",
        })

    def test_failure_is_swallowed(self):
        n = notifier.WebhookNotifier("https://hooks.example/x")
        with mock.patch.object(notifier.urllib.request, "urlopen", side_effect=OSError("dns")):
            self.assertEqual(
                n.notify(school_id="s-avini", level="CLOSED", message="x"),
                "webhook-failed-s-avini",
            )


class TestBuildFactory(unittest.TestCase):
    def test_smtp_channel_uses_smtp_settings(self):
        cfg = dataclasses.replace(
            Settings(), smtp_host="h", smtp_port=2525, smtp_user="u", smtp_password="p"
        )
        n = notifier.build("smtp", cfg)
        self.assertIsInstance(n, notifier.SmtpNotifier)
        self.assertEqual(n.host, "h")
        self.assertEqual(n.port, 2525)

    def test_webhook_channel_uses_webhook_url(self):
        cfg = dataclasses.replace(Settings(), webhook_url="https://hooks.example/y")
        built = notifier.build("webhook", cfg)
        self.assertIsInstance(built, notifier.WebhookNotifier)
        self.assertEqual(built.url, "https://hooks.example/y")

    def test_silent_and_default_channels(self):
        self.assertIsInstance(notifier.build("silent", Settings()), notifier.SilentNotifier)
        self.assertIsInstance(notifier.build("anything-else", Settings()), notifier.ConsoleNotifier)


if __name__ == "__main__":
    unittest.main()
