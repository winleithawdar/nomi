from __future__ import annotations

_VALID_SCORES = frozenset({"1", "2", "3", "4", "5"})


def parse_wellbeing_score(text: str | None) -> float | None:
    if text is None:
        return None
    stripped = text.strip()
    if stripped not in _VALID_SCORES:
        return None
    return float(stripped)
