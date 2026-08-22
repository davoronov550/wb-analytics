"""Notifier adapters (implement NotifierPort) — email + Telegram with retries.

Delivery is best-effort with bounded retries/backoff; a persistent failure is
logged, not raised, so alert evaluation is not derailed by a flaky channel.
Config comes from settings/env (no secrets in source).
"""

from __future__ import annotations

import logging
import time
from collections.abc import Callable

import httpx
from django.conf import settings
from django.core.mail import send_mail

from notifications.domain.alert import EMAIL, TELEGRAM

logger = logging.getLogger("notifications")


def _send_email(message: str) -> None:
    send_mail(
        subject="WB Analytics — price alert",
        message=message,
        from_email=getattr(settings, "SMTP_FROM", None) or "alerts@example.com",
        recipient_list=[getattr(settings, "ALERT_EMAIL_TO", None) or "alerts@example.com"],
        fail_silently=False,
    )


def _send_telegram(message: str) -> None:
    token = getattr(settings, "TELEGRAM_BOT_TOKEN", "")
    chat_id = getattr(settings, "TELEGRAM_DEFAULT_CHAT_ID", "")
    if not token or not chat_id:
        raise RuntimeError("Telegram is not configured")
    httpx.post(
        f"https://api.telegram.org/bot{token}/sendMessage",
        json={"chat_id": chat_id, "text": message},
        timeout=10.0,
    ).raise_for_status()


class ChannelNotifier:
    def __init__(
        self,
        *,
        email: Callable[[str], None] = _send_email,
        telegram: Callable[[str], None] = _send_telegram,
        retries: int = 2,
        backoff_base: float = 0.5,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self._senders = {EMAIL: email, TELEGRAM: telegram}
        self._retries = retries
        self._backoff_base = backoff_base
        self._sleep = sleep

    def send(self, channel: str, message: str) -> None:
        sender = self._senders.get(channel)
        if sender is None:
            logger.warning("Unknown notifier channel: %s", channel)
            return
        for attempt in range(self._retries + 1):
            try:
                sender(message)
                return
            except Exception as exc:  # noqa: BLE001 - retry then give up, never crash
                if attempt < self._retries:
                    self._sleep(self._backoff_base * (2**attempt))
                    continue
                logger.warning("Notification via %s failed after retries: %s", channel, exc)
