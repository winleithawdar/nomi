from __future__ import annotations

import hashlib
import hmac
from datetime import datetime, timezone

import httpx

from .protocol import MessagingError, OutboundMessage, Recipient
from .settings import MessagingSettings

GRAPH_API_BASE = "https://graph.facebook.com"
DEFAULT_TIMEOUT_SECONDS = 10.0
_SIGNATURE_PREFIX = "sha256="


def verify_meta_signature(raw_body: bytes, header: str | None, app_secret: str) -> bool:
    """Return True if X-Hub-Signature-256 matches HMAC-SHA256 of the raw body."""
    if not header or not app_secret:
        return False
    if not header.startswith(_SIGNATURE_PREFIX):
        return False
    provided = header[len(_SIGNATURE_PREFIX) :]
    expected = hmac.new(
        app_secret.encode("utf-8"),
        raw_body,
        hashlib.sha256,
    ).hexdigest()
    try:
        return hmac.compare_digest(provided, expected)
    except (TypeError, ValueError):
        return False


class WhatsAppCloudProvider:
    """Official WhatsApp Cloud API (Graph) text sender."""

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
            f"{GRAPH_API_BASE}/{self._settings.graph_api_version}"
            f"/{self._settings.phone_number_id}/messages"
        )
        headers = {
            "Authorization": f"Bearer {self._settings.access_token}",
            "Content-Type": "application/json",
        }
        payload = {
            "messaging_product": "whatsapp",
            "to": recipient.wa_id,
            "type": "text",
            "text": {"body": body},
        }
        response = self._client.post(url, headers=headers, json=payload)
        if response.status_code < 200 or response.status_code >= 300:
            raise MessagingError(
                f"WhatsApp Cloud API request failed with status {response.status_code}"
            )

        provider_message_id = _message_id_from_response(response)
        if not provider_message_id:
            raise MessagingError("WhatsApp Cloud API response missing message id")

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
    messages = data.get("messages")
    if not isinstance(messages, list) or not messages:
        return None
    first = messages[0]
    if not isinstance(first, dict):
        return None
    message_id = first.get("id")
    if not isinstance(message_id, str) or not message_id:
        return None
    return message_id
