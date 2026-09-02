from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from nomi_backend.baseline import BaselineCalculator, SeniorInteraction
from nomi_backend.detection import AnomalyDetector, ChangeDetector


@dataclass(frozen=True)
class SeniorProfile:
    id: str
    name: str
    relationship: str
    age_band: str


class DemoBaselineRepository:
    def __init__(
        self,
        seniors: list[SeniorProfile] | None = None,
        interactions: list[SeniorInteraction] | None = None,
    ) -> None:
        self.calculator = BaselineCalculator()
        self.anomaly_detector = AnomalyDetector()
        self.change_detector = ChangeDetector()
        self.seniors = seniors if seniors is not None else [
            SeniorProfile("senior-1", "Mdm Tan", "Mother", "Late 70s"),
            SeniorProfile("senior-2", "Mr Rahman", "Father", "Early 80s"),
            SeniorProfile("senior-3", "Auntie Lee", "Aunt", "Mid 70s"),
        ]
        self.interactions = (
            interactions if interactions is not None else self._build_demo_interactions()
        )

    def list_seniors_payload(self) -> dict:
        summaries = []
        learning_count = 0
        established_count = 0
        recent_checkins = 0

        for senior in self.seniors:
            senior_interactions = self._interactions_for(senior.id)
            baseline = self.calculator.calculate(senior.id, senior_interactions)
            if baseline.status.value == "learning":
                learning_count += 1
            else:
                established_count += 1

            recent_checkins += len(
                [
                    interaction
                    for interaction in senior_interactions
                    if interaction.occurred_at >= self._reference_now() - timedelta(days=7)
                ]
            )

            summaries.append(
                {
                    "id": senior.id,
                    "name": senior.name,
                    "relationship": senior.relationship,
                    "age_band": senior.age_band,
                    "baseline_status": baseline.status.value,
                    "observation_count": baseline.total_interactions,
                    "latest_interaction_at": baseline.as_of.isoformat() if baseline.as_of else None,
                    "status_text": self._status_text(baseline.status.value, senior.name),
                }
            )

        return {
            "summary": {
                "seniors_monitored": len(self.seniors),
                "seniors_learning": learning_count,
                "baselines_established": established_count,
                "recent_checkins": recent_checkins,
            },
            "seniors": summaries,
        }

    def get_senior_detail_payload(self, senior_id: str) -> dict | None:
        senior = next((item for item in self.seniors if item.id == senior_id), None)
        if senior is None:
            return None

        senior_interactions = self._interactions_for(senior_id)
        baseline = self.calculator.calculate(senior_id, senior_interactions)
        recent_observations = [
            {
                "occurred_at": interaction.occurred_at.isoformat(),
                "response_latency_minutes": interaction.response_latency_minutes,
                "missed_checkin": interaction.missed_checkin,
                "interaction_frequency": self._interaction_frequency_at(
                    senior_interactions, interaction.occurred_at
                ),
                "wellbeing_score": interaction.wellbeing_score,
            }
            for interaction in senior_interactions[-10:]
        ]
        response_latency_series = self._response_latency_series(senior_interactions)

        return {
            "senior": {
                "id": senior.id,
                "name": senior.name,
                "relationship": senior.relationship,
                "age_band": senior.age_band,
            },
            "baseline": baseline.to_dict(),
            "recent_observations": recent_observations,
            "response_latency_series": response_latency_series,
        }

    def get_anomaly_payload(self, senior_id: str) -> dict | None:
        if not any(item.id == senior_id for item in self.seniors):
            return None
        return self.anomaly_detector.detect(
            senior_id, self._interactions_for(senior_id)
        ).to_dict()

    def get_change_payload(self, senior_id: str) -> dict | None:
        if not any(item.id == senior_id for item in self.seniors):
            return None
        return self.change_detector.detect(
            senior_id, self._interactions_for(senior_id)
        ).to_dict()

    def _interactions_for(self, senior_id: str) -> list[SeniorInteraction]:
        return [item for item in self.interactions if item.senior_id == senior_id]

    def _response_latency_series(self, interactions: list[SeniorInteraction]) -> list[dict]:
        values: list[float] = []
        series = []

        for interaction in interactions:
            latency = interaction.response_latency_minutes
            if latency is None:
                continue
            values.append(latency)
            rolling_window = values[-20:]
            series.append(
                {
                    "occurred_at": interaction.occurred_at.isoformat(),
                    "response_latency_minutes": latency,
                    "rolling_mean_minutes": sum(rolling_window) / len(rolling_window),
                }
            )

        return series

    def _interaction_frequency_at(
        self,
        interactions: list[SeniorInteraction],
        occurred_at: datetime,
    ) -> int:
        cutoff = occurred_at - timedelta(days=7)
        return len(
            [
                interaction
                for interaction in interactions
                if cutoff <= interaction.occurred_at <= occurred_at
            ]
        )

    def _status_text(self, baseline_status: str, name: str) -> str:
        if baseline_status == "learning":
            return f"Learning {name}'s normal pattern"
        return "Personal baseline established"

    def _reference_now(self) -> datetime:
        return datetime(2026, 8, 30, 9, 0, tzinfo=UTC)

    def _build_demo_interactions(self) -> list[SeniorInteraction]:
        start = datetime(2026, 8, 1, 9, 0, tzinfo=UTC)

        def build(
            senior_id: str,
            day_offset: int,
            latency_minutes: float | None,
            *,
            missed_checkin: bool = False,
            wellbeing_score: float | None = None,
        ) -> SeniorInteraction:
            occurred_at = start + timedelta(days=day_offset)
            sent_at = None if latency_minutes is None else occurred_at - timedelta(minutes=latency_minutes)
            responded_at = None if latency_minutes is None else occurred_at
            return SeniorInteraction(
                senior_id=senior_id,
                occurred_at=occurred_at,
                interaction_type="checkin_missed" if missed_checkin else "checkin_response",
                missed_checkin=missed_checkin,
                checkin_sent_at=sent_at,
                response_received_at=responded_at,
                wellbeing_score=wellbeing_score,
            )

        established_normal = [
            build(
                "senior-1",
                day,
                24 + (day % 5),
                wellbeing_score=4.0 if day % 6 else 3.0,
            )
            for day in range(25)
        ]
        meaningful_change = [
            build("senior-1", 25, 180, wellbeing_score=1.0),
        ]
        other_seniors = [
            build("senior-2", 0, 18),
            build("senior-2", 3, None, missed_checkin=True),
            build("senior-2", 6, 20),
            build("senior-2", 10, None, missed_checkin=True),
            build("senior-3", 20, 14, wellbeing_score=5.0),
            build("senior-3", 22, 16, wellbeing_score=4.0),
            build("senior-3", 24, 17, wellbeing_score=4.0),
        ]
        return [*established_normal, *meaningful_change, *other_seniors]
