from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from nomi_backend.api.app import app
from nomi_backend.api.verification import get_db_session, get_verification_service
from nomi_backend.persistence.schema import Base
from nomi_backend.services.verification_service import VerificationService


class EndToEndIntegrationTest(unittest.TestCase):
    def setUp(self) -> None:
        engine = create_engine(
            "sqlite://",
            future=True,
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(engine)
        self.session = sessionmaker(bind=engine, future=True)()

        def override_session():
            yield self.session

        def override_service():
            return VerificationService.from_session(self.session)

        app.dependency_overrides[get_db_session] = override_session
        app.dependency_overrides[get_verification_service] = override_service
        self.client = TestClient(app)

    def tearDown(self) -> None:
        app.dependency_overrides.clear()
        self.session.close()

    def test_detection_to_unresolved_verification_to_dashboard_alert(self) -> None:
        seniors = self.client.get("/api/v1/seniors")
        self.assertEqual(seniors.status_code, 200)
        self.assertEqual(seniors.json()["summary"]["seniors_monitored"], 3)

        detection_response = self.client.get(
            "/api/v1/seniors/senior-1/detections/anomaly"
        )
        self.assertEqual(detection_response.status_code, 200)
        detection = detection_response.json()
        self.assertTrue(detection["detected"])
        self.assertEqual(detection["status"], "ok")

        started = self.client.post(
            "/api/v1/verifications",
            json={
                "senior_id": "senior-1",
                "senior_name": "Mdm Tan",
                "detection": detection,
            },
        )
        self.assertEqual(started.status_code, 200)
        verification_id = started.json()["verification"]["id"]

        unresolved = self.client.post(
            f"/api/v1/verifications/{verification_id}/no-response"
        )
        self.assertEqual(unresolved.status_code, 200)
        self.assertEqual(unresolved.json()["verification"]["status"], "escalated")
        self.assertIsNotNone(unresolved.json()["alert"])

        dashboard_feed = self.client.get("/api/v1/alerts?senior_id=senior-1")
        self.assertEqual(dashboard_feed.status_code, 200)
        self.assertEqual(len(dashboard_feed.json()["alerts"]), 1)


if __name__ == "__main__":
    unittest.main()
