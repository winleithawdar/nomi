from __future__ import annotations

from nomi_backend.baseline.models import (
    BaselineStatus,
    NumericSignalBaseline,
    SeniorBaseline,
    SignalStatus,
)
from nomi_backend.notice.models import NoticeAssessment, NoticeFinding, NoticeLevel


class NoticeDetector:
    """Compare the latest observations with a senior's own baseline.

    Findings stay descriptive. They do not diagnose illness or raise caregiver alerts.
    """

    def assess(self, baseline: SeniorBaseline, name: str) -> NoticeAssessment:
        if baseline.status == BaselineStatus.LEARNING:
            return NoticeAssessment(
                status="learning",
                headline=f"Still learning {name}'s usual pattern. Change detection waits until the baseline is established.",
                findings=[],
            )

        findings: list[NoticeFinding] = []
        findings.extend(self._latency_findings(baseline, name))
        findings.extend(self._missed_findings(baseline, name))
        findings.extend(self._frequency_findings(baseline, name))
        findings.extend(self._wellbeing_findings(baseline, name))

        if any(finding.level == "changed" for finding in findings):
            status = "changed"
            headline = f"{len(findings)} signal{'s' if len(findings) != 1 else ''} differ from {name}'s usual pattern."
        elif findings:
            status = "watching"
            headline = findings[0].explanation
        else:
            status = "usual"
            headline = f"Recent check-ins look in line with {name}'s usual pattern."

        return NoticeAssessment(status=status, headline=headline, findings=findings)

    def _latency_findings(self, baseline: SeniorBaseline, name: str) -> list[NoticeFinding]:
        signal = baseline.response_latency_minutes
        z_score = self._positive_z_score(signal)
        if z_score is None:
            return []

        if z_score >= 2.0:
            return [
                NoticeFinding(
                    signal="response_latency_minutes",
                    level="changed",
                    explanation=self._latency_explanation(name, signal, "slower than usual"),
                )
            ]
        if z_score >= 1.25:
            return [
                NoticeFinding(
                    signal="response_latency_minutes",
                    level="watching",
                    explanation=self._latency_explanation(name, signal, "a little slower than usual"),
                )
            ]
        return []

    def _missed_findings(self, baseline: SeniorBaseline, name: str) -> list[NoticeFinding]:
        signal = baseline.missed_checkin_rate
        if signal.status == SignalStatus.UNAVAILABLE or signal.latest_value != 1 or signal.rate is None:
            return []

        if signal.positive_count >= 2 and signal.rate >= 0.4:
            return [
                NoticeFinding(
                    signal="missed_checkin_rate",
                    level="changed",
                    explanation=f"{name} missed the latest check-in, and missed check-ins are now {round(signal.rate * 100)}% of recent outcomes.",
                )
            ]

        if signal.rate <= 0.25:
            return [
                NoticeFinding(
                    signal="missed_checkin_rate",
                    level="watching",
                    explanation=f"{name} missed the latest check-in, which is uncommon against their usual pattern.",
                )
            ]

        return [
            NoticeFinding(
                signal="missed_checkin_rate",
                level="watching",
                explanation=f"{name} missed the latest check-in.",
            )
        ]

    def _frequency_findings(self, baseline: SeniorBaseline, name: str) -> list[NoticeFinding]:
        signal = baseline.interaction_frequency
        z_score = self._negative_z_score(signal)
        if z_score is None:
            return []

        window_days = int(baseline.metadata.get("frequency_window_days", 7))
        latest = signal.latest_value
        mean = signal.mean
        if latest is None or mean is None:
            return []

        level: NoticeLevel | None = None
        if z_score >= 2.0:
            level = "changed"
        elif z_score >= 1.25:
            level = "watching"

        if level is None:
            return []

        return [
            NoticeFinding(
                signal="interaction_frequency",
                level=level,
                explanation=(
                    f"{name} had {int(latest)} check-ins in the last {window_days} days, "
                    f"below their usual {mean:.1f}."
                ),
            )
        ]

    def _wellbeing_findings(self, baseline: SeniorBaseline, name: str) -> list[NoticeFinding]:
        signal = baseline.wellbeing_score
        z_score = self._negative_z_score(signal)
        if z_score is None:
            return []

        level: NoticeLevel | None = None
        if z_score >= 2.0:
            level = "changed"
        elif z_score >= 1.5:
            level = "watching"

        if level is None or signal.latest_value is None:
            return []

        return [
            NoticeFinding(
                signal="wellbeing_score",
                level=level,
                explanation=f"{name} reported wellbeing of {signal.latest_value:.1f}, below their usual {signal.mean:.1f}.",
            )
        ]

    def _latency_explanation(self, name: str, signal: NumericSignalBaseline, qualifier: str) -> str:
        latest = signal.latest_value or 0
        mean = signal.mean or 0
        extra_minutes = max(0, round(latest - mean))
        return f"{name}'s latest reply took {round(latest)} minutes, {extra_minutes} minutes {qualifier}."

    def _positive_z_score(self, signal: NumericSignalBaseline) -> float | None:
        return self._z_score(signal, direction="high")

    def _negative_z_score(self, signal: NumericSignalBaseline) -> float | None:
        return self._z_score(signal, direction="low")

    def _z_score(self, signal: NumericSignalBaseline, *, direction: str) -> float | None:
        if signal.status != SignalStatus.STABLE:
            return None
        if signal.latest_value is None or signal.mean is None or signal.stddev is None:
            return None

        deviation = signal.latest_value - signal.mean
        if direction == "high" and deviation <= 0:
            return None
        if direction == "low" and deviation >= 0:
            return None

        magnitude = abs(deviation)
        if signal.stddev == 0:
            # A zero-spread baseline still needs a practical personal threshold.
            fallback = 15.0 if direction == "high" else max(1.0, abs(signal.mean) * 0.35)
            return 2.0 if magnitude >= fallback else None

        return magnitude / signal.stddev
