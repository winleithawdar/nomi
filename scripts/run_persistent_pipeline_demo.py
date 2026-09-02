"""Exercise the persisted check-in -> webhook -> verification -> alert pipeline."""

from __future__ import annotations

import argparse
import hashlib
import hmac
import json
import os
from datetime import UTC, datetime, timedelta
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


def request(
    base_url: str,
    method: str,
    path: str,
    body: dict | None = None,
    headers: dict[str, str] | None = None,
) -> dict:
    data = json.dumps(body).encode() if body is not None else None
    combined_headers = {"Accept": "application/json"}
    if body is not None:
        combined_headers["Content-Type"] = "application/json"
    combined_headers.update(headers or {})
    req = Request(
        f"{base_url.rstrip('/')}{path}",
        data=data,
        method=method,
        headers=combined_headers,
    )
    with urlopen(req, timeout=20) as response:
        return json.loads(response.read().decode())


def signed_webhook(
    base_url: str,
    app_secret: str,
    *,
    wa_id: str,
    wamid: str,
    received_at: datetime,
    reply: str,
) -> dict:
    payload = {
        "object": "whatsapp_business_account",
        "entry": [
            {
                "changes": [
                    {
                        "value": {
                            "messages": [
                                {
                                    "from": wa_id,
                                    "id": wamid,
                                    "timestamp": str(int(received_at.timestamp())),
                                    "type": "text",
                                    "text": {"body": reply},
                                }
                            ]
                        }
                    }
                ]
            }
        ],
    }
    raw = json.dumps(payload).encode()
    signature = "sha256=" + hmac.new(app_secret.encode(), raw, hashlib.sha256).hexdigest()
    req = Request(
        f"{base_url.rstrip('/')}/webhooks/whatsapp",
        data=raw,
        method="POST",
        headers={
            "Content-Type": "application/json",
            "Accept": "application/json",
            "X-Hub-Signature-256": signature,
        },
    )
    with urlopen(req, timeout=30) as response:
        return json.loads(response.read().decode())


def env_value(name: str) -> str:
    if os.getenv(name):
        return os.environ[name]
    env_file = Path(__file__).resolve().parents[1] / ".env"
    if env_file.exists():
        for raw_line in env_file.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, value = line.split("=", 1)
                if key.strip() == name:
                    return value.strip().strip("'\"")
    return ""


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--api-url", default="http://127.0.0.1:8000")
    parser.add_argument("--senior-id", default="senior-1")
    parser.add_argument("--senior-wa-id", default="6581111111")
    parser.add_argument("--caregiver-wa-id", default="6582222222")
    args = parser.parse_args()
    app_secret = env_value("WHATSAPP_APP_SECRET")
    if not app_secret:
        print("Set WHATSAPP_APP_SECRET in the root .env, then restart FastAPI.")
        return 1

    try:
        for role, wa_id in (
            ("senior", args.senior_wa_id),
            ("caregiver", args.caregiver_wa_id),
        ):
            request(
                args.api_url,
                "PUT",
                f"/api/v1/seniors/{args.senior_id}/contacts/{role}",
                {"wa_id": wa_id, "phone_e164": f"+{wa_id}"},
            )
        print("1. Senior and caregiver contacts persisted")

        sent = request(
            args.api_url,
            "POST",
            "/api/v1/checkins",
            {"senior_id": args.senior_id},
        )
        print(f"2. Check-in persisted: {sent['id']}")

        unusual_at = datetime.now(UTC) + timedelta(hours=3)
        unique_suffix = str(int(unusual_at.timestamp()))
        signed_webhook(
            args.api_url,
            app_secret,
            wa_id=args.senior_wa_id,
            wamid=f"wamid.demo-unusual-{unique_suffix}",
            received_at=unusual_at,
            reply="1",
        )
        print("3. Signed WhatsApp reply persisted and detection executed")

        status = request(
            args.api_url,
            "GET",
            f"/api/v1/seniors/{args.senior_id}/verification-status",
        )
        if status["active_verification"] is not None:
            signed_webhook(
                args.api_url,
                app_secret,
                wa_id=args.senior_wa_id,
                wamid=f"wamid.demo-help-{unique_suffix}",
                received_at=unusual_at + timedelta(minutes=1),
                reply="1",
            )
            print("4. Verification help-needed reply processed")
        else:
            print("4. Repeated detection escalated without another verification reply")

        final_status = request(
            args.api_url,
            "GET",
            f"/api/v1/seniors/{args.senior_id}/verification-status",
        )
        alert = final_status["latest_alert"]
        if alert is None:
            raise RuntimeError("No caregiver alert was created.")
        print(f"5. Caregiver alert persisted with status: {alert['status']}")
        print("6. Refresh /dashboard and inspect Supabase tables")
        return 0
    except (HTTPError, URLError, RuntimeError, KeyError) as error:
        print(f"Persistent pipeline demo failed: {error}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
