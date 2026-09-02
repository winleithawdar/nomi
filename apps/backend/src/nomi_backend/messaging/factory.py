from __future__ import annotations

from .mock_provider import MockMessagingProvider
from .protocol import MessagingProvider
from .settings import MessagingSettings


def build_messaging_provider(settings: MessagingSettings) -> MessagingProvider:
    if settings.provider == "mock":
        return MockMessagingProvider()
    if settings.provider == "whatsapp":
        from .whatsapp_cloud import WhatsAppCloudProvider

        return WhatsAppCloudProvider(settings)
    raise ValueError(f"Unknown messaging provider: {settings.provider}")
