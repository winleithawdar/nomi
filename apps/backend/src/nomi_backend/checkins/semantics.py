from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

LABEL_AS_USUAL = "as_usual"
LABEL_CHANGED_FROM_USUAL = "changed_from_usual"
LABEL_NEEDS_YOU_NOW = "needs_you_now"

STEP_AS_USUAL = "No extra step."
STEP_CHANGED = "Message or call when convenient."
STEP_NEEDS_YOU = "Call or visit when you can."

TFIDF_SHIFT_THRESHOLD = 0.35

LEVEL2_PHRASES: tuple[str, ...] = (
    "not okay",
    "not ok",
    "can't",
    "cannot",
    "help",
    "hurt",
    "pain",
    "fall",
    "fell",
    "scared",
    "dizzy",
    "chest",
)

LEVEL1_PHRASES: tuple[str, ...] = (
    "cannot sleep",
    "no appetite",
    "lonely",
    "tired",
    "worried",
    "worse",
)

USUAL_PHRASES: tuple[str, ...] = (
    "alright",
    "slept",
    "fine",
    "good",
    "ate",
    "ok",
)

_SUGGESTED_STEPS = {
    LABEL_AS_USUAL: STEP_AS_USUAL,
    LABEL_CHANGED_FROM_USUAL: STEP_CHANGED,
    LABEL_NEEDS_YOU_NOW: STEP_NEEDS_YOU,
}

_LABEL_FOR_LEVEL = {
    0: LABEL_AS_USUAL,
    1: LABEL_CHANGED_FROM_USUAL,
    2: LABEL_NEEDS_YOU_NOW,
}


class SessionLabel(str, Enum):
    AS_USUAL = LABEL_AS_USUAL
    CHANGED_FROM_USUAL = LABEL_CHANGED_FROM_USUAL
    NEEDS_YOU_NOW = LABEL_NEEDS_YOU_NOW


@dataclass(frozen=True)
class SessionAssessment:
    label: str
    rhythm_level: int
    self_report_level: int
    language_level: int
    reasons: list[str]
    suggested_step: str
    latency_minutes: float | None
    median_latency: float | None
    wellbeing: float | None
    median_wellbeing: float | None
    tfidf_similarity: float | None
    lexicon_hits: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "label": self.label,
            "rhythm_level": self.rhythm_level,
            "self_report_level": self.self_report_level,
            "language_level": self.language_level,
            "reasons": list(self.reasons),
            "suggested_step": self.suggested_step,
            "latency_minutes": self.latency_minutes,
            "median_latency": self.median_latency,
            "wellbeing": self.wellbeing,
            "median_wellbeing": self.median_wellbeing,
            "tfidf_similarity": self.tfidf_similarity,
            "lexicon_hits": list(self.lexicon_hits),
        }


def assess_session(
    *,
    latency_minutes: float | None,
    median_latency: float | None,
    wellbeing: float | None,
    median_wellbeing: float | None,
    session_text: str,
    prior_session_texts: list[str] | None = None,
    missed: bool = False,
) -> SessionAssessment:
    rhythm_level = _rhythm_level(missed, latency_minutes, median_latency)
    self_report_level = _self_report_level(wellbeing, median_wellbeing)
    lowered = session_text.lower()
    lexicon_level, lexicon_hits = _lexicon_level(lowered)
    tfidf_similarity, tfidf_level = _tfidf_shift(session_text, prior_session_texts or [])
    language_level = max(lexicon_level, tfidf_level)

    reasons: list[str] = []
    reasons.extend(_rhythm_reasons(rhythm_level, missed, latency_minutes, median_latency))
    reasons.extend(_self_report_reasons(self_report_level, wellbeing, median_wellbeing))
    reasons.extend(
        _language_reasons(
            language_level,
            lexicon_level,
            lexicon_hits,
            tfidf_level,
            tfidf_similarity,
        )
    )

    overall = max(rhythm_level, self_report_level, language_level)
    label = _LABEL_FOR_LEVEL[overall]
    return SessionAssessment(
        label=label,
        rhythm_level=rhythm_level,
        self_report_level=self_report_level,
        language_level=language_level,
        reasons=reasons,
        suggested_step=_SUGGESTED_STEPS[label],
        latency_minutes=latency_minutes,
        median_latency=median_latency,
        wellbeing=wellbeing,
        median_wellbeing=median_wellbeing,
        tfidf_similarity=tfidf_similarity,
        lexicon_hits=lexicon_hits,
    )


def _rhythm_level(
    missed: bool,
    latency_minutes: float | None,
    median_latency: float | None,
) -> int:
    if missed:
        return 2
    if (
        latency_minutes is not None
        and median_latency is not None
        and latency_minutes >= 2 * median_latency
    ):
        return 1
    return 0


def _self_report_level(
    wellbeing: float | None,
    median_wellbeing: float | None,
) -> int:
    if wellbeing is not None and wellbeing in {1, 2}:
        return 2
    if wellbeing == 3 and median_wellbeing is not None and median_wellbeing >= 4:
        return 1
    return 0


def _lexicon_level(lowered: str) -> tuple[int, list[str]]:
    level2_hits = [phrase for phrase in LEVEL2_PHRASES if phrase in lowered]
    if level2_hits:
        return 2, level2_hits
    level1_hits = [phrase for phrase in LEVEL1_PHRASES if phrase in lowered]
    if level1_hits:
        return 1, level1_hits
    usual_hits = [phrase for phrase in USUAL_PHRASES if phrase in lowered]
    return 0, usual_hits


def _tfidf_shift(
    session_text: str,
    prior_session_texts: list[str],
) -> tuple[float | None, int]:
    usable = [text for text in prior_session_texts if text.strip()]
    if len(usable) < 2:
        return None, 0
    current = session_text.strip() or " "
    try:
        from sklearn.feature_extraction.text import TfidfVectorizer
        from sklearn.metrics.pairwise import cosine_similarity
        import numpy as np

        vectorizer = TfidfVectorizer()
        prior_matrix = vectorizer.fit_transform(usable)
        mean_vector = np.asarray(prior_matrix.mean(axis=0))
        if mean_vector.ndim == 1:
            mean_vector = mean_vector.reshape(1, -1)
        this_vector = vectorizer.transform([current])
        similarity = float(cosine_similarity(this_vector, mean_vector)[0, 0])
    except ValueError:
        return None, 0
    if similarity < TFIDF_SHIFT_THRESHOLD:
        return similarity, 1
    return similarity, 0


def _rhythm_reasons(
    level: int,
    missed: bool,
    latency_minutes: float | None,
    median_latency: float | None,
) -> list[str]:
    if missed or level == 2:
        return ["No reply to this check-in."]
    if level == 1 and latency_minutes is not None and median_latency is not None:
        ratio = latency_minutes / median_latency if median_latency else 0.0
        return [
            f"Reply {latency_minutes:.0f} min vs usual {median_latency:.0f} "
            f"(about {ratio:.1f}×)."
        ]
    return []


def _self_report_reasons(
    level: int,
    wellbeing: float | None,
    median_wellbeing: float | None,
) -> list[str]:
    if level == 2 and wellbeing is not None:
        return [f"Wellbeing {int(wellbeing)} of 5."]
    if level == 1 and median_wellbeing is not None:
        return [f"Wellbeing dipped to 3 vs usual {int(median_wellbeing)}."]
    return []


def _language_reasons(
    language_level: int,
    lexicon_level: int,
    lexicon_hits: list[str],
    tfidf_level: int,
    tfidf_similarity: float | None,
) -> list[str]:
    reasons: list[str] = []
    if lexicon_level == 2:
        for hit in lexicon_hits:
            reasons.append(f"Message contained '{hit}'.")
    elif lexicon_level == 1:
        for hit in lexicon_hits:
            reasons.append(f"Said '{hit}'.")
    elif language_level == 0 and lexicon_hits:
        reasons.append("Used usual phrasing (" + ", ".join(lexicon_hits) + ").")
    if tfidf_level == 1 and tfidf_similarity is not None:
        reasons.append(
            f"This meal's wording was unlike her last sessions "
            f"(similarity {tfidf_similarity:.2f})."
        )
    return reasons
