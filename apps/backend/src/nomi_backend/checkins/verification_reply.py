from __future__ import annotations

from nomi_backend.verification.models import VerificationOutcome

_HELP_NEEDED_EXACT = frozenset({"1", "2"})
_HELP_NEEDED_SUBSTRINGS = ("help", "not ok", "not okay")


def map_verification_reply(text: str) -> VerificationOutcome:
    """Map a senior's inbound text to a verification outcome. Does not store text."""
    normalized = text.strip().lower()
    if normalized in _HELP_NEEDED_EXACT:
        return VerificationOutcome.HELP_NEEDED
    if any(needle in normalized for needle in _HELP_NEEDED_SUBSTRINGS):
        return VerificationOutcome.HELP_NEEDED
    return VerificationOutcome.REASSURING
