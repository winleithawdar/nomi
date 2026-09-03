from __future__ import annotations

import hmac
from datetime import datetime, timezone

import httpx

from .protocol import MessagingError, OutboundMessage, Recipient
from .settings import MessagingSettings

TELEGRAM_API_BASE = "https://api.telegram.org"
DEFAULT_TIMEOUT_SECONDS = 10.0


def verify_telegram_secret(header: str | None, expected: str) -> bool:
    """Return True if X-Telegram-Bot-Api-Secret-Token matches expected.

    An empty expected secret skips the check (local/dev).
    """
    if not expected:
        return True
    if header is None:
        return False
    try:
        return hmac.compare_digest(header, expected)
    except (TypeError, ValueError):
        return False


class TelegramBotProvider:
    """Official Telegram Bot API text sender."""

    def __init__(
        self,
        settings: MessagingSettings,
        *,
        client: httpx.Client | None = None,
    ) -> None:
        self._settings = settings
        self._client = client or httpx.Client(
            timeout=DEFAULT_TIMEOUT_SECONDS,
            trust_env=False,
        )

    def send_text(
        self,
        recipient: Recipient,
        body: str,
        *,
        correlation_id: str | None = None,
    ) -> OutboundMessage:
        url = (
            f"{TELEGRAM_API_BASE}/bot{self._settings.telegram_bot_token}/sendMessage"
        )
        payload = {
            "chat_id": recipient.wa_id,
            "text": body,
        }
        response = self._client.post(url, json=payload)
        if response.status_code < 200 or response.status_code >= 300:
            raise MessagingError(
                f"Telegram Bot API request failed with status {response.status_code}"
            )

        provider_message_id = _message_id_from_response(response)
        if not provider_message_id:
            raise MessagingError("Telegram Bot API response missing message id")

        return OutboundMessage(
            provider_message_id=provider_message_id,
            recipient=recipient,
            sent_at=datetime.now(timezone.utc),
            correlation_id=correlation_id,
        )


def _message_id_from_response(response: httpx.Response) -> str | None:
    try:
        data = response.json()
    except (ValueError, TypeError):
        return None
    if not isinstance(data, dict):
        return None
    result = data.get("result")
    if not isinstance(result, dict):
        return None
    message_id = result.get("message_id")
    if isinstance(message_id, bool) or message_id is None:
        return None
    if isinstance(message_id, int):
        return str(message_id)
    if isinstance(message_id, str) and message_id:
        return message_id
    return None
