from __future__ import annotations

import os
import sys
import unittest
from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from nomi_backend.api.app import app, reset_checkin_service, store
from nomi_backend.api.verification import get_db_session, get_verification_service
from nomi_backend.checkins.models import SeniorContact
from nomi_backend.detection.contract import (
  ChangeDirection,
  Confidence,
  DetectionKind,
  DetectionResult,
  DetectionStatus,
  SignalContribution,
)
from nomi_backend.messaging.protocol import ContactRole
from nomi_backend.persistence.repository import VerificationRepository
from nomi_backend.persistence.schema import Base
from nomi_backend.services.verification_service import VerificationService
from nomi_backend.verification.models import AlertStatus, VerificationOutcome, VerificationStatus

START = datetime(2026, 8, 30, 9, 0, tzinfo=UTC)


def _detection_payload(
  *,
  kind: str = "anomaly",
  confidence: str = "moderate",
  detected: bool = True,
  status: str = "ok",
  senior_id: str = "senior-1",
) -> dict:
  return DetectionResult(
    senior_id=senior_id,
    kind=DetectionKind(kind),
    detected=detected,
    status=DetectionStatus(status),
    as_of=START,
    confidence=Confidence(confidence),
    direction=ChangeDirection.RISING,
    contributions=[
      SignalContribution(
        signal="response_latency_minutes",
        status=DetectionStatus.OK,
        flagged=True,
        direction=ChangeDirection.RISING,
        baseline_mean=25.0,
        recent_mean=60.0,
        deviation_pct=0.5,
        standardized_shift=2.0,
        methods_fired=["isolation_forest"],
        recent_series=[{"value": 60.0}],
      )
    ],
    summary="Response times have been slower than usual.",
  ).to_dict()


class VerificationApiTest(unittest.TestCase):
  def setUp(self) -> None:
    self._env = patch.dict(os.environ, {"NOMI_SCHEDULER_ENABLED": "0"})
    self._env.start()
    self.engine = create_engine(
      "sqlite://",
      future=True,
      connect_args={"check_same_thread": False},
      poolclass=StaticPool,
    )
    Base.metadata.create_all(self.engine)
    self.session_factory = sessionmaker(bind=self.engine, autoflush=False, autocommit=False)
    self.session = self.session_factory()

    def override_session():
      try:
        yield self.session
      finally:
        pass

    def override_service():
      return VerificationService.from_session(self.session)

    app.dependency_overrides[get_db_session] = override_session
    app.dependency_overrides[get_verification_service] = override_service
    self.client = TestClient(app)

  def tearDown(self) -> None:
    app.dependency_overrides.clear()
    self.session.close()
    self._env.stop()

  def test_start_verification_endpoint_returns_check_in_message(self) -> None:
    response = self.client.post(
      "/api/v1/verifications",
      json={
        "senior_id": "senior-1",
        "senior_name": "Mdm Tan",
        "detection": _detection_payload(),
      },
    )

    self.assertEqual(response.status_code, 200)
    payload = response.json()
    self.assertEqual(payload["verification"]["status"], VerificationStatus.AWAITING_RESPONSE.value)
    self.assertIn("Mdm Tan", payload["verification"]["check_in_message"])
    self.assertIsNone(payload["alert"])

  def test_start_verification_rejects_non_actionable_detection(self) -> None:
    response = self.client.post(
      "/api/v1/verifications",
      json={
        "senior_id": "senior-1",
        "detection": _detection_payload(detected=False),
      },
    )
    self.assertEqual(response.status_code, 400)

  def test_reassuring_response_endpoint_resolves_verification(self) -> None:
    start = self.client.post(
      "/api/v1/verifications",
      json={"senior_id": "senior-1", "detection": _detection_payload()},
    ).json()
    verification_id = start["verification"]["id"]

    response = self.client.post(
      f"/api/v1/verifications/{verification_id}/response",
      json={"outcome": "reassuring", "response_text": "All good"},
    )

    self.assertEqual(response.status_code, 200)
    payload = response.json()
    self.assertEqual(payload["verification"]["status"], VerificationStatus.RESOLVED_REASSURING.value)
    self.assertIsNone(payload["alert"])

  def test_help_needed_response_creates_alert_for_dashboard(self) -> None:
    start = self.client.post(
      "/api/v1/verifications",
      json={"senior_id": "senior-1", "detection": _detection_payload()},
    ).json()
    verification_id = start["verification"]["id"]

    response = self.client.post(
      f"/api/v1/verifications/{verification_id}/response",
      json={"outcome": "help_needed", "response_text": "Could use a visit"},
    )
    alert_id = response.json()["alert"]["id"]

    detail = self.client.get(f"/api/v1/alerts/{alert_id}")
    self.assertEqual(detail.status_code, 200)
    self.assertIn("what_changed", detail.json())
    self.assertIn("suggested_action", detail.json())

    feed = self.client.get("/api/v1/alerts?senior_id=senior-1")
    self.assertEqual(feed.status_code, 200)
    self.assertEqual(len(feed.json()["alerts"]), 1)

  def test_no_response_endpoint_escalates_high_confidence_anomaly(self) -> None:
    start = self.client.post(
      "/api/v1/verifications",
      json={
        "senior_id": "senior-1",
        "detection": _detection_payload(confidence="high"),
      },
    ).json()
    verification_id = start["verification"]["id"]

    response = self.client.post(f"/api/v1/verifications/{verification_id}/no-response")
    self.assertEqual(response.status_code, 200)
    payload = response.json()
    self.assertEqual(payload["verification"]["status"], VerificationStatus.ESCALATED.value)
    self.assertIsNotNone(payload["alert"])

  def test_check_in_and_caregiver_message_endpoints_for_p3(self) -> None:
    start = self.client.post(
      "/api/v1/verifications",
      json={"senior_id": "senior-1", "detection": _detection_payload(confidence="high")},
    ).json()
    verification_id = start["verification"]["id"]

    check_in = self.client.get(f"/api/v1/verifications/{verification_id}/check-in-message")
    self.assertEqual(check_in.status_code, 200)
    self.assertIn("message", check_in.json())

    escalated = self.client.post(f"/api/v1/verifications/{verification_id}/no-response").json()
    alert_id = escalated["alert"]["id"]

    caregiver_message = self.client.get(f"/api/v1/alerts/{alert_id}/caregiver-message")
    self.assertEqual(caregiver_message.status_code, 200)
    self.assertIn("Suggested next step", caregiver_message.json()["message"])

    delivered = self.client.post(f"/api/v1/alerts/{alert_id}/delivered", json={})
    self.assertEqual(delivered.status_code, 200)
    self.assertEqual(delivered.json()["status"], AlertStatus.DELIVERED.value)

  def test_verification_status_endpoint_for_p5(self) -> None:
    start = self.client.post(
      "/api/v1/verifications",
      json={"senior_id": "senior-1", "detection": _detection_payload()},
    ).json()
    verification_id = start["verification"]["id"]

    active_status = self.client.get("/api/v1/seniors/senior-1/verification-status")
    self.assertEqual(active_status.status_code, 200)
    self.assertIsNotNone(active_status.json()["active_verification"])

    self.client.post(
      f"/api/v1/verifications/{verification_id}/response",
      json={"outcome": "reassuring"},
    )
    resolved_status = self.client.get("/api/v1/seniors/senior-1/verification-status")
    self.assertIsNone(resolved_status.json()["active_verification"])

    history = self.client.get("/api/v1/seniors/senior-1/verifications")
    self.assertEqual(history.status_code, 200)
    self.assertEqual(len(history.json()["verifications"]), 1)

  def test_get_verification_returns_404_for_unknown_id(self) -> None:
    response = self.client.get("/api/v1/verifications/missing-id")
    self.assertEqual(response.status_code, 404)

  def test_start_verification_attempts_outbound_prompt_when_contact_seeded(self) -> None:
    with patch.dict(os.environ, {"NOMI_MESSAGING_PROVIDER": "mock"}):
      reset_checkin_service()
      store.upsert_contact(SeniorContact("senior-1", "123456789", ContactRole.SENIOR))
      with patch(
        "nomi_backend.checkins.pipeline.send_verification_prompt"
      ) as mocked_send:
        response = self.client.post(
          "/api/v1/verifications",
          json={
            "senior_id": "senior-1",
            "senior_name": "Mdm Tan",
            "detection": _detection_payload(),
          },
        )
    self.assertEqual(response.status_code, 200)
    mocked_send.assert_called_once()
    args, kwargs = mocked_send.call_args
    self.assertEqual(args[1], "senior-1")
    self.assertIn("Mdm Tan", args[2])


class VerificationRepositoryTest(unittest.TestCase):
  def setUp(self) -> None:
    self.engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(self.engine)
    session = sessionmaker(bind=self.engine)()
    self.repository = VerificationRepository(session)
    self.repository.create_tables()
    self.service = VerificationService(self.repository)

  def tearDown(self) -> None:
    self.repository.session.close()

  def test_persists_verification_round_trip(self) -> None:
    result = self.service.start_from_detection_payload(_detection_payload())
    assert result is not None
    loaded = self.repository.get_verification(result.verification.id)
    assert loaded is not None
    self.assertEqual(loaded.senior_id, "senior-1")
    self.assertTrue(loaded.detection.detected)

  def test_lists_pending_alerts_by_status(self) -> None:
    start = self.service.start_from_detection_payload(_detection_payload(confidence="high"))
    assert start is not None
    self.service.handle_no_response(start.verification.id)

    pending = self.repository.list_all_alerts(status=AlertStatus.PENDING)
    self.assertEqual(len(pending), 1)
    delivered = self.repository.mark_alert_delivered(
      pending[0].id,
      START + timedelta(hours=1),
    )
    assert delivered is not None
    self.assertEqual(delivered.status, AlertStatus.DELIVERED)


if __name__ == "__main__":
  unittest.main()
