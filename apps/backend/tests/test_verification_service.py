from __future__ import annotations

import sys
import unittest
from datetime import UTC, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from nomi_backend.detection.contract import (
    ChangeDirection,
    Confidence,
    DetectionKind,
    DetectionResult,
    DetectionStatus,
    SignalContribution,
)
from nomi_backend.persistence.repository import VerificationRepository
from nomi_backend.persistence.schema import Base
from nomi_backend.services.verification_service import VerificationService
from nomi_backend.verification.models import VerificationOutcome, VerificationStatus


def _detection(**overrides) -> DetectionResult:
    base = {
        "senior_id": "senior-1",
        "kind": DetectionKind.SUSTAINED_CHANGE,
        "detected": True,
        "status": DetectionStatus.OK,
        "as_of": datetime(2026, 9, 1, 9, 0, tzinfo=UTC),
        "confidence": Confidence.MODERATE,
        "direction": ChangeDirection.RISING,
        "contributions": [
            SignalContribution(
                signal="response_latency_minutes",
                status=DetectionStatus.OK,
                flagged=True,
                direction=ChangeDirection.RISING,
                baseline_mean=25.0,
                recent_mean=40.0,
                deviation_pct=0.6,
                standardized_shift=2.0,
                methods_fired=["level_shift"],
                estimated_onset=datetime(2026, 9, 1, 9, 0, tzinfo=UTC),
                recent_series=[],
            )
        ],
        "summary": "Response latency is running above the usual baseline.",
        "metadata": {},
    }
    base.update(overrides)
    return DetectionResult(**base)


class VerificationServiceTest(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = create_engine("sqlite:///:memory:", future=True)
        Base.metadata.create_all(self.engine)
        self.session = sessionmaker(bind=self.engine, future=True)()
        self.service = VerificationService.from_session(self.session)

    def tearDown(self) -> None:
        self.session.close()

    def test_start_and_list_verification(self) -> None:
        detection = _detection()
        result = self.service.start_from_detection_payload(detection.to_dict())
        self.assertIsNotNone(result)
        assert result is not None
        self.assertEqual(result.verification.status, VerificationStatus.AWAITING_RESPONSE)

        listed = self.service.repository.list_verifications("senior-1")
        self.assertEqual(len(listed), 1)
        self.assertEqual(listed[0].id, result.verification.id)

    def test_record_reassuring_response_persists_resolution(self) -> None:
        started = self.service.start_from_detection_payload(_detection().to_dict())
        assert started is not None
        result = self.service.record_response(
            started.verification.id,
            VerificationOutcome.REASSURING,
            response_text="I'm fine",
        )
        assert result is not None
        self.assertEqual(result.verification.status, VerificationStatus.RESOLVED_REASSURING)
        stored = self.service.repository.get_verification(started.verification.id)
        assert stored is not None
        self.assertEqual(stored.response_text, "I'm fine")

    def test_help_needed_creates_persisted_alert(self) -> None:
        started = self.service.start_from_detection_payload(_detection().to_dict())
        assert started is not None
        result = self.service.record_response(
            started.verification.id,
            VerificationOutcome.HELP_NEEDED,
            response_text="Please call me",
        )
        assert result is not None
        self.assertIsNotNone(result.alert)
        alerts = self.service.repository.list_alerts("senior-1")
        self.assertEqual(len(alerts), 1)
        self.assertIn("Please call me", alerts[0].verification_outcome)


if __name__ == "__main__":
    unittest.main()
