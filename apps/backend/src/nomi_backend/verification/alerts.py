from __future__ import annotations

from nomi_backend.detection.contract import DetectionKind, DetectionResult, SignalContribution
from nomi_backend.verification.models import VerificationOutcome


_SIGNAL_LABELS = {
  "response_latency_minutes": "response times",
  "missed_checkin_rate": "missed check-ins",
  "interaction_frequency": "interaction frequency",
  "wellbeing_score": "self-reported wellbeing",
}


def _format_signal_change(contribution: SignalContribution) -> str:
  label = _SIGNAL_LABELS.get(contribution.signal, contribution.signal.replace("_", " "))
  if contribution.baseline_mean is not None and contribution.recent_mean is not None:
    if contribution.signal == "response_latency_minutes":
      return (
        f"{label.title()} have shifted from about {contribution.baseline_mean:.0f} minutes "
        f"to about {contribution.recent_mean:.0f} minutes recently"
      )
    if contribution.signal == "wellbeing_score":
      return (
        f"{label.title()} has moved from about {contribution.baseline_mean:.1f} "
        f"to about {contribution.recent_mean:.1f} recently"
      )
    if contribution.deviation_pct is not None:
      pct = abs(contribution.deviation_pct) * 100
      direction = "higher" if contribution.recent_mean > contribution.baseline_mean else "lower"
      return f"{label.title()} is running about {pct:.0f}% {direction} than usual"
  return f"A change was noticed in {label}"


def build_what_changed(detection: DetectionResult) -> str:
  flagged = [item for item in detection.contributions if item.flagged]
  if detection.summary:
    return detection.summary
  if not flagged:
    kind_label = "sudden shift" if detection.kind == DetectionKind.ANOMALY else "sustained change"
    return f"A behavioural {kind_label} was noticed relative to this senior's usual pattern."
  if len(flagged) == 1:
    return _format_signal_change(flagged[0]).capitalize() + "."
  parts = [_format_signal_change(item) for item in flagged[:3]]
  return "Several signals differ from usual: " + "; ".join(parts) + "."


def build_context(detection: DetectionResult) -> str:
  flagged = [item for item in detection.contributions if item.flagged]
  if not flagged:
    return (
      "This notice is based on recent Nomi check-in interactions compared with "
      "this senior's personal baseline."
    )

  context_parts: list[str] = []
  for contribution in flagged[:3]:
    label = _SIGNAL_LABELS.get(contribution.signal, contribution.signal.replace("_", " "))
    methods = ", ".join(contribution.methods_fired) if contribution.methods_fired else "pattern review"
    if contribution.recent_series:
      point_count = len(contribution.recent_series)
      context_parts.append(
        f"For {label}, {point_count} recent observations were reviewed ({methods})."
      )
    elif contribution.baseline_mean is not None and contribution.recent_mean is not None:
      context_parts.append(
        f"For {label}, the usual level is about {contribution.baseline_mean:.1f} "
        f"and the recent level is about {contribution.recent_mean:.1f}."
      )
    else:
      context_parts.append(f"For {label}, a change was observed using {methods}.")

  kind_note = (
    "This was flagged as a sudden unusual pattern."
    if detection.kind == DetectionKind.ANOMALY
    else "This was flagged as a sustained shift over time."
  )
  return " ".join(context_parts) + " " + kind_note


def build_verification_outcome_text(outcome: VerificationOutcome, response_text: str | None) -> str:
  if outcome == VerificationOutcome.REASSURING:
    if response_text:
      return f"The senior replied and indicated they are doing fine: \"{response_text}\""
    return "The senior replied and indicated they are doing fine."
  if outcome == VerificationOutcome.HELP_NEEDED:
    if response_text:
      return f"The senior indicated they may need help: \"{response_text}\""
    return "The senior indicated they may need help."
  if outcome == VerificationOutcome.NO_RESPONSE:
    return "The senior did not respond to the gentle check-in message within the expected window."
  if outcome == VerificationOutcome.REPEATED_CHANGE:
    return (
      "A further behavioural change was noticed before the previous concern was fully resolved."
    )
  return "Verification outcome is unavailable."


def build_suggested_action(outcome: VerificationOutcome, detection: DetectionResult) -> str:
  if outcome == VerificationOutcome.HELP_NEEDED:
    return "Consider reaching out soon to understand what support may be helpful."
  if outcome == VerificationOutcome.NO_RESPONSE:
    return "Consider a phone call or visit to check in when convenient."
  if outcome == VerificationOutcome.REPEATED_CHANGE:
    if detection.kind == DetectionKind.SUSTAINED_CHANGE:
      return (
        "A pattern has continued after an earlier check-in. "
        "Consider a caring follow-up to see how things are going."
      )
    return "Consider a caring follow-up to see how things are going."
  return "No caregiver action is needed right now."


def build_check_in_message(detection: DetectionResult, senior_name: str | None = None) -> str:
  greeting = f"Hi {senior_name}," if senior_name else "Hi,"
  if detection.kind == DetectionKind.SUSTAINED_CHANGE:
    lead = "We've noticed a small change in your usual check-in pattern lately."
  else:
    lead = "We noticed something a little different in your recent check-in pattern."
  return (
    f"{greeting} {lead} Just checking in — is everything okay on your end? "
    "A quick reply would be lovely."
  )
