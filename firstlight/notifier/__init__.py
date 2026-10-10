"""Notification channel abstraction.

The pipeline emits logical alerts; a notifier turns them into real messages.
Build It default is the console notifier (no network). SMTP and generic
webhook notifiers are provided for a real deployment; the SAM twin wires the
webhook channel via ALERT_HOOK_URL. Failures are logged and never crash the
morning.
"""

from __future__ import annotations

import json
import smtplib
import urllib.request
from abc import ABC, abstractmethod

from ..config import Settings


class Notifier(ABC):
    @abstractmethod
    def notify(self, *, school_id: str, level: str, message: str) -> str:
        """Deliver; returns a provider receipt id."""


class ConsoleNotifier(Notifier):
    def notify(self, *, school_id: str, level: str, message: str) -> str:
        print(f"[notify://console] {school_id} {level}: {message}")
        return f"console-{school_id}"


class SilentNotifier(Notifier):
    def notify(self, *, school_id: str, level: str, message: str) -> str:
        return f"silent-{school_id}"


class SmtpNotifier(Notifier):
    def __init__(self, host: str, port: int, user: str, password: str, to: str):
        self.host, self.port, self.user, self.password, self.to = host, port, user, password, to

    def notify(self, *, school_id: str, level: str, message: str) -> str:
        if not (self.host and self.user):
            return f"smtp-unconfigured-{school_id}"
        try:
            with smtplib.SMTP(self.host, self.port, timeout=10) as s:
                s.starttls()
                s.login(self.user, self.password)
                s.sendmail(self.user, [self.to], f"Subject: [FirstLight] {school_id} {level}\n\n{message}")
            return f"smtp-{school_id}"
        except Exception as exc:  # never take the morning down
            print(f"[notify://smtp] failed {school_id}: {exc}")
            return f"smtp-failed-{school_id}"


class WebhookNotifier(Notifier):
    def __init__(self, url: str):
        self.url = url

    def notify(self, *, school_id: str, level: str, message: str) -> str:
        if not self.url:
            return f"webhook-unconfigured-{school_id}"
        body = json.dumps({"school": school_id, "level": level, "message": message}).encode()
        req = urllib.request.Request(self.url, data=body, headers={"Content-Type": "application/json"}, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=10):
                return f"webhook-{school_id}"
        except Exception:
            return f"webhook-failed-{school_id}"


class SnsNotifier(Notifier):
    """Fan-out via AWS SNS. Publishes are fire-and-forget: SNS accepts a message
    even with zero subscribers, so the receipt states that plainly rather than
    claiming delivery."""

    def __init__(self, topic_arn: str):
        self.topic_arn = topic_arn

    def notify(self, *, school_id: str, level: str, message: str) -> str:
        if not self.topic_arn:
            return f"sns-unconfigured-{school_id} (no subscribers)"
        try:
            import boto3  # lazy: local builds stay offline
        except ImportError:
            return f"sns-unavailable-{school_id} (no boto3)"
        try:
            client = boto3.client("sns")
            resp = client.publish(
                TopicArn=self.topic_arn,
                Subject=f"{level}: {school_id}",
                Message=message,
            )
            return f"sns-{resp.get('MessageId', school_id)}"
        except Exception as exc:  # never take the morning down
            print(f"[notify://sns] failed {school_id}: {exc}")
            return f"sns-failed-{school_id}"


class TelegramNotifier(Notifier):
    def __init__(self, token: str, chat_id: str):
        self.token = token
        self.chat_id = chat_id

    def notify(self, *, school_id: str, level: str, message: str) -> str:
        if not self.token or not self.chat_id:
            return f"telegram-unconfigured-{school_id} (no subscribers)"
        url = f"https://api.telegram.org/bot{self.token}/sendMessage"
        body = json.dumps({"chat_id": self.chat_id, "text": f"{level} · {school_id}\n{message}"}).encode()
        req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"}, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=10):
                return f"telegram-{school_id}"
        except Exception:
            return f"telegram-failed-{school_id}"


def build(channel: str, cfg: Settings) -> Notifier:
    if channel == "smtp":
        return SmtpNotifier(cfg.smtp_host, cfg.smtp_port, cfg.smtp_user, cfg.smtp_password, cfg.smtp_user or "")
    if channel == "webhook":
        return WebhookNotifier(cfg.webhook_url)
    if channel == "sns":
        return SnsNotifier(cfg.sns_topic_arn)
    if channel == "telegram":
        return TelegramNotifier(cfg.telegram_token, cfg.telegram_chat_id)
    if channel == "silent":
        return SilentNotifier()
    return ConsoleNotifier()
