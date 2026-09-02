from __future__ import annotations

import os
from dataclasses import dataclass

DEFAULT_PROVIDER = "mock"
DEFAULT_GRAPH_API_VERSION = "v21.0"
DEFAULT_CHECKIN_BODY = (
    "Hi, this is Nomi checking in. How are you today? Reply with a number "
    "from 1 (low) to 5 (good), or any short reply so we know you saw this."
)


@dataclass(frozen=True)
class MessagingSettings:
    provider: str
    access_token: str
    phone_number_id: str
    verify_token: str
    app_secret: str
    graph_api_version: str
    default_checkin_body: str

    @classmethod
    def from_env(cls) -> MessagingSettings:
        provider = os.environ.get("NOMI_MESSAGING_PROVIDER", DEFAULT_PROVIDER)
        access_token = os.environ.get("WHATSAPP_ACCESS_TOKEN", "")
        phone_number_id = os.environ.get("WHATSAPP_PHONE_NUMBER_ID", "")
        verify_token = os.environ.get("WHATSAPP_VERIFY_TOKEN", "")
        app_secret = os.environ.get("WHATSAPP_APP_SECRET", "")
        graph_api_version = os.environ.get(
            "WHATSAPP_GRAPH_API_VERSION", DEFAULT_GRAPH_API_VERSION
        )
        default_checkin_body = os.environ.get("NOMI_CHECKIN_BODY") or DEFAULT_CHECKIN_BODY

        if provider == "whatsapp":
            if not access_token:
                raise RuntimeError("WHATSAPP_ACCESS_TOKEN is required when provider is whatsapp")
            if not phone_number_id:
                raise RuntimeError("WHATSAPP_PHONE_NUMBER_ID is required when provider is whatsapp")

        return cls(
            provider=provider,
            access_token=access_token,
            phone_number_id=phone_number_id,
            verify_token=verify_token,
            app_secret=app_secret,
            graph_api_version=graph_api_version,
            default_checkin_body=default_checkin_body,
        )
