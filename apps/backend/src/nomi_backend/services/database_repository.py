from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import text

from nomi_backend.baseline import SeniorInteraction
from nomi_backend.persistence.database import SessionLocal
from nomi_backend.services.demo_repository import DemoBaselineRepository, SeniorProfile


class DatabaseBaselineRepository:
    """Read dashboard and detection inputs from the shared PostgreSQL schema."""

    def _delegate(self) -> DemoBaselineRepository:
        with SessionLocal() as session:
            profile_rows = session.execute(
                text(
                    """
                    select id, name, relationship, age_band
                    from senior_profiles
                    where active = true
                    order by name
                    """
                )
            ).mappings().all()
            interaction_rows = session.execute(
                text(
                    """
                    select senior_id, occurred_at, interaction_type, missed_checkin,
                           checkin_sent_at, response_received_at, wellbeing_score,
                           checkin_id, source
                    from senior_interactions
                    order by occurred_at
                    """
                )
            ).mappings().all()

        seniors = [
            SeniorProfile(
                id=str(row["id"]),
                name=row["name"],
                relationship=row["relationship"],
                age_band=row["age_band"],
            )
            for row in profile_rows
        ]
        interactions = [
            SeniorInteraction(
                senior_id=str(row["senior_id"]),
                occurred_at=_aware(row["occurred_at"]),
                interaction_type=row["interaction_type"],
                missed_checkin=bool(row["missed_checkin"]),
                checkin_sent_at=_aware(row["checkin_sent_at"]),
                response_received_at=_aware(row["response_received_at"]),
                wellbeing_score=row["wellbeing_score"],
                checkin_id=str(row["checkin_id"]) if row["checkin_id"] else None,
                source=row["source"],
            )
            for row in interaction_rows
        ]
        return DemoBaselineRepository(seniors=seniors, interactions=interactions)

    def list_seniors_payload(self) -> dict:
        return self._delegate().list_seniors_payload()

    def get_senior_detail_payload(self, senior_id: str) -> dict | None:
        return self._delegate().get_senior_detail_payload(senior_id)

    def get_anomaly_payload(self, senior_id: str) -> dict | None:
        return self._delegate().get_anomaly_payload(senior_id)

    def get_change_payload(self, senior_id: str) -> dict | None:
        return self._delegate().get_change_payload(senior_id)


def _aware(value: datetime | str | None) -> datetime | None:
    if isinstance(value, str):
        value = datetime.fromisoformat(value)
    if value is None or value.tzinfo is not None:
        return value
    return value.replace(tzinfo=UTC)
