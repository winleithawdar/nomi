from __future__ import annotations

import hashlib
import hmac
import json
from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from nomi_backend.persistence.schema import Base, SeniorInteractionRecord


def _signature(body: bytes, secret: str) -> str:
    digest = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    return f"sha256={digest}"


def _webhook(wa_id: str, wamid: str, timestamp: datetime, reply: str) -> dict:
    return {
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
                                    "timestamp": str(int(timestamp.timestamp())),
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


def main() -> None:
    from nomi_backend.persistence.database import get_database_url

    engine = create_engine(
        get_database_url(),
        future=True,
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(engine)
    with engine.begin() as connection:
        connection.execute(
            text(
                """
                create table if not exists senior_profiles (
                    id text primary key,
                    name text not null,
                    relationship text not null,
                    age_band text not null,
                    active boolean not null default true
                )
                """
            )
        )
        connection.execute(
            text(
                """
                insert into senior_profiles (id, name, relationship, age_band, active)
                values ('senior-1', 'Mdm Tan', 'Mother', 'Late 70s', true)
                """
            )
        )

    factory = sessionmaker(bind=engine, future=True)
    baseline_start = datetime(2026, 8, 1, 9, 0, tzinfo=UTC)
    with factory() as session:
        for day in range(25):
            occurred_at = baseline_start + timedelta(days=day)
            latency = 24 + day % 5
            session.add(
                SeniorInteractionRecord(
                    senior_id="senior-1",
                    occurred_at=occurred_at,
                    interaction_type="checkin_response",
                    checkin_sent_at=occurred_at - timedelta(minutes=latency),
                    response_received_at=occurred_at,
                    response_latency_minutes=latency,
                    missed_checkin=False,
                    wellbeing_score=4,
                    source="nomi",
                )
            )
        session.commit()

    # Import only after database-mode environment variables and seed tables are ready.
    from nomi_backend.api.app import app

    client = TestClient(app)
    senior_wa_id = "6581111111"
    caregiver_wa_id = "6582222222"
    for role, wa_id in (("senior", senior_wa_id), ("caregiver", caregiver_wa_id)):
        response = client.put(
            f"/api/v1/seniors/senior-1/contacts/{role}",
            json={"wa_id": wa_id, "phone_e164": f"+{wa_id}"},
        )
        assert response.status_code == 200, response.text

    sent = client.post("/api/v1/checkins", json={"senior_id": "senior-1"})
    assert sent.status_code == 201, sent.text

    unusual_at = datetime.now(UTC) + timedelta(hours=3)
    first_payload = json.dumps(
        _webhook(senior_wa_id, "wamid.unusual", unusual_at, "1")
    ).encode()
    first = client.post(
        "/webhooks/whatsapp",
        content=first_payload,
        headers={"X-Hub-Signature-256": _signature(first_payload, "test-secret")},
    )
    assert first.status_code == 200, first.text

    status = client.get("/api/v1/seniors/senior-1/verification-status").json()
    active = status["active_verification"]
    assert active is not None, status

    help_payload = json.dumps(
        _webhook(senior_wa_id, "wamid.help", unusual_at + timedelta(minutes=1), "1")
    ).encode()
    help_response = client.post(
        "/webhooks/whatsapp",
        content=help_payload,
        headers={"X-Hub-Signature-256": _signature(help_payload, "test-secret")},
    )
    assert help_response.status_code == 200, help_response.text

    final_status = client.get("/api/v1/seniors/senior-1/verification-status").json()
    assert final_status["active_verification"] is None, final_status
    alert = final_status["latest_alert"]
    assert alert is not None, final_status
    assert alert["status"] == "delivered", alert

    with factory() as session:
        count = session.scalar(
            text(
                "select count(*) from senior_interactions "
                "where senior_id = 'senior-1' and checkin_id is not null"
            )
        )
        assert count == 1, count


if __name__ == "__main__":
    main()
