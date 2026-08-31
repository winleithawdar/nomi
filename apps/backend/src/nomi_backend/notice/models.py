from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Literal


NoticeStatus = Literal["learning", "usual", "watching", "changed"]
NoticeLevel = Literal["watching", "changed"]


@dataclass(frozen=True)
class NoticeFinding:
    signal: str
    level: NoticeLevel
    explanation: str


@dataclass(frozen=True)
class NoticeAssessment:
    status: NoticeStatus
    headline: str
    findings: list[NoticeFinding]

    def to_dict(self) -> dict:
        return asdict(self)
