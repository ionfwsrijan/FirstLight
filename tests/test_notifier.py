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

    def test_sns_channel_uses_topic_arn(self):
        cfg = dataclasses.replace(Settings(), sns_topic_arn="arn:aws:sns:ap-south-2:1:t")
        built = notifier.build("sns", cfg)
        self.assertIsInstance(built, notifier.SnsNotifier)
        self.assertEqual(built.topic_arn, "arn:aws:sns:ap-south-2:1:t")

    def test_telegram_channel_uses_token_and_chat(self):
        cfg = dataclasses.replace(Settings(), telegram_token="tok", telegram_chat_id="42")
        built = notifier.build("telegram", cfg)
        self.assertIsInstance(built, notifier.TelegramNotifier)
        self.assertEqual((built.token, built.chat_id), ("tok", "42"))

    def test_silent_and_default_channels(self):
        self.assertIsInstance(notifier.build("silent", Settings()), notifier.SilentNotifier)
        self.assertIsInstance(notifier.build("anything-else", Settings()), notifier.ConsoleNotifier)


class TestSnsNotifier(unittest.TestCase):
    def test_unconfigured_says_no_subscribers(self):
        receipt = notifier.SnsNotifier("").notify(
            school_id="s-avini", level="CLOSED", message="x"
        )
        self.assertEqual(receipt, "sns-unconfigured-s-avini (no subscribers)")

    def test_publish_uses_topic_and_returns_message_id(self):
        n = notifier.SnsNotifier("arn:aws:sns:ap-south-2:1:alerts")
        client = mock.MagicMock()
        client.publish.return_value = {"MessageId": "abc-123"}
        fake_boto3 = mock.MagicMock()
        fake_boto3.client.return_value = client
        with mock.patch.dict(sys.modules, {"boto3": fake_boto3}):
            receipt = n.notify(school_id="s-guard", level="PROTECTED", message="masks")
        self.assertEqual(receipt, "sns-abc-123")
        self.assertEqual(client.publish.call_args.kwargs["TopicArn"], "arn:aws:sns:ap-south-2:1:alerts")

    def test_failure_is_swallowed_and_recorded(self):
        n = notifier.SnsNotifier("arn:aws:sns:ap-south-2:1:alerts")
        fake_boto3 = mock.MagicMock()
        fake_boto3.client.side_effect = RuntimeError("denied")
        with mock.patch.dict(sys.modules, {"boto3": fake_boto3}), redirect_stdout(io.StringIO()):
            receipt = n.notify(school_id="s-avini", level="CLOSED", message="x")
        self.assertEqual(receipt, "sns-failed-s-avini")


class TestTelegramNotifier(unittest.TestCase):
    def test_unconfigured_says_no_subscribers(self):
        receipt = notifier.TelegramNotifier("", "").notify(
            school_id="s-avini", level="CLOSED", message="x"
        )
        self.assertEqual(receipt, "telegram-unconfigured-s-avini (no subscribers)")

    def test_success_posts_to_bot_api(self):
        n = notifier.TelegramNotifier("tok", "42")
        captured = {}

        def fake_urlopen(req, timeout=0):
            captured["url"] = req.full_url
            captured["body"] = req.data
            return mock.MagicMock()

        with mock.patch.object(notifier.urllib.request, "urlopen", side_effect=fake_urlopen):
            receipt = n.notify(school_id="s-gurugram", level="PROTECTED", message="shut windows")

        self.assertEqual(receipt, "telegram-s-gurugram")
        self.assertIn("api.telegram.org/bottok/sendMessage", captured["url"])
        self.assertEqual(json.loads(captured["body"])["chat_id"], "42")

    def test_failure_is_swallowed(self):
        n = notifier.TelegramNotifier("tok", "42")
        with mock.patch.object(notifier.urllib.request, "urlopen", side_effect=OSError("dns")):
            self.assertEqual(
                n.notify(school_id="s-avini", level="CLOSED", message="x"),
                "telegram-failed-s-avini",
            )


if __name__ == "__main__":
    unittest.main()
