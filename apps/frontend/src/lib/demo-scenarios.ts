import type { SessionLabel } from "@/lib/api/seniors";
import type { BaselineObservation } from "@/lib/api/types";

import { buildCheckinThread } from "./checkin-copy";

export interface DemoScenarioUi {
  label: SessionLabel;
  meal: string;
  tracks: { rhythm: number; self_report: number; language: number };
  replies: { from: "nomi" | "senior"; text: string }[];
  reasons: string[];
  suggested_step: string;
  recentUpdateTitle: string;
  recentUpdateSummary: string;
  recentUpdateConfidence: string;
  followingUpTitle: string;
  followingUpMessage: string;
  followingUpSuggestedStep: string | null;
}

const SENIOR_REPLIES: Record<SessionLabel, [string, string, string]> = {
  as_usual: ["4", "same", "no"],
  changed_from_usual: ["3", "a bit tired today", "ok"],
  needs_you_now: ["1", "worse", "Dizzy, cannot stand up properly. Need help."],
};

const TRACKS: Record<SessionLabel, { rhythm: number; self_report: number; language: number }> = {
  as_usual: { rhythm: 2, self_report: 2, language: 1 },
  changed_from_usual: { rhythm: 2, self_report: 1, language: 2 },
  needs_you_now: { rhythm: 0, self_report: 0, language: 2 },
};

const SUGGESTED_STEPS: Record<SessionLabel, string> = {
  as_usual: "No extra step.",
  changed_from_usual: "Message or call when convenient.",
  needs_you_now: "Call or visit when you can.",
};

function inferLabel(obs: BaselineObservation): SessionLabel {
  if (
    obs.missed_checkin ||
    (obs.wellbeing_score !== null && obs.wellbeing_score <= 1) ||
    (obs.response_latency_minutes !== null && obs.response_latency_minutes >= 120)
  ) {
    return "needs_you_now";
  }
  if (
    obs.wellbeing_score === 3 ||
    (obs.response_latency_minutes !== null && obs.response_latency_minutes >= 45)
  ) {
    return "changed_from_usual";
  }
  return "as_usual";
}

function inferMeal(occurredAt: string): string {
  const hour = new Date(occurredAt).getUTCHours();
  if (hour < 6) return "Breakfast";
  if (hour < 11) return "Lunch";
  return "Dinner";
}

function buildReasons(obs: BaselineObservation, label: SessionLabel): string[] {
  const reasons: string[] = [];

  if (obs.missed_checkin) {
    reasons.push("Check-in was missed — no reply received");
  } else if (obs.response_latency_minutes !== null) {
    if (obs.response_latency_minutes >= 120) {
      reasons.push(
        `Reply took ${obs.response_latency_minutes} minutes — far outside their usual window`,
      );
    } else if (obs.response_latency_minutes >= 45) {
      reasons.push(`Reply time slightly longer than usual (${obs.response_latency_minutes} min)`);
    } else {
      reasons.push(`Reply time within their usual window (${obs.response_latency_minutes} min)`);
    }
  }

  if (obs.wellbeing_score !== null) {
    if (obs.wellbeing_score <= 1) {
      reasons.push(`Wellbeing reported at ${obs.wellbeing_score}/5 — the lowest observed`);
    } else if (obs.wellbeing_score === 3) {
      reasons.push(`Wellbeing dropped to ${obs.wellbeing_score}/5 — below their usual`);
    } else {
      reasons.push(
        `Wellbeing self-reported at ${obs.wellbeing_score}/5 — consistent with baseline`,
      );
    }
  } else if (label !== "as_usual") {
    reasons.push("Wellbeing was not reported in this check-in");
  }

  if (label === "needs_you_now") {
    reasons.push("Language or signals suggest they may need help");
  } else if (label === "changed_from_usual") {
    reasons.push("Language signals mild fatigue or a subtle shift");
  } else {
    reasons.push("Language tone is relaxed and familiar");
  }

  return reasons;
}

function buildRecentUpdateCopy(
  label: SessionLabel,
  meal: string,
): Pick<DemoScenarioUi, "recentUpdateTitle" | "recentUpdateSummary" | "recentUpdateConfidence"> {
  if (label === "needs_you_now") {
    return {
      recentUpdateTitle: "Something seems different",
      recentUpdateSummary: `Nomi flagged an unusual pattern at ${meal.toLowerCase()}: response latency and wellbeing signals suggest they may need attention. Nomi checked in with them directly before this alert was sent.`,
      recentUpdateConfidence: "high confidence",
    };
  }
  if (label === "changed_from_usual") {
    return {
      recentUpdateTitle: "Something seems different",
      recentUpdateSummary: `Nomi noticed a subtle shift at ${meal.toLowerCase()}: self-reported wellbeing or reply timing differs from their usual baseline. This is a gentle flag, not an alert.`,
      recentUpdateConfidence: "moderate confidence",
    };
  }
  return {
    recentUpdateTitle: "Everything looks familiar",
    recentUpdateSummary: `${meal} check-in is consistent with their baseline. Reply timing, wellbeing, and language are all within their personal normal.`,
    recentUpdateConfidence: "high confidence",
  };
}

function buildFollowingUpCopy(
  label: SessionLabel,
): Pick<DemoScenarioUi, "followingUpTitle" | "followingUpMessage" | "followingUpSuggestedStep"> {
  if (label === "needs_you_now") {
    return {
      followingUpTitle: "Caregiver attention requested",
      followingUpMessage:
        "They indicated they may need help. Nomi verified with them directly before escalating.",
      followingUpSuggestedStep: "Please reach out soon to understand what support may be helpful.",
    };
  }
  return {
    followingUpTitle: "No follow-up needed",
    followingUpMessage:
      label === "changed_from_usual"
        ? "Nomi will continue monitoring and will check in again before escalating."
        : "If something seems different, Nomi will check in with them before contacting you.",
    followingUpSuggestedStep: null,
  };
}

export function buildScenarioFromObservation(obs: BaselineObservation): DemoScenarioUi {
  const label = inferLabel(obs);
  const meal = inferMeal(obs.occurred_at);
  const tracks = { ...TRACKS[label] };

  if (
    label === "needs_you_now" &&
    obs.response_latency_minutes !== null &&
    obs.response_latency_minutes >= 120
  ) {
    tracks.rhythm = 2;
  }

  return {
    label,
    meal,
    tracks,
    replies: buildCheckinThread(SENIOR_REPLIES[label]),
    reasons: buildReasons(obs, label),
    suggested_step: SUGGESTED_STEPS[label],
    ...buildRecentUpdateCopy(label, meal),
    ...buildFollowingUpCopy(label),
  };
}

export const DEMO_SCENARIOS: Record<string, DemoScenarioUi> = {
  "2026-09-03T00:00:00+00:00": {
    label: "as_usual",
    meal: "Breakfast",
    tracks: { rhythm: 2, self_report: 2, language: 1 },
    replies: [
      { from: "nomi", text: "Good morning Mdm Tan! How are you feeling today? 😊" },
      { from: "senior", text: "Good lah, just had coffee" },
      { from: "nomi", text: "Glad to hear! Could you rate your wellbeing from 1–5?" },
      { from: "senior", text: "4" },
      { from: "nomi", text: "Thank you Mdm Tan! See you at lunch 🌿" },
      { from: "senior", text: "Ok ok" },
    ],
    reasons: [
      "Reply time within her usual 20–30 min window",
      "Wellbeing self-reported at 4/5 — consistent with baseline",
      "Language tone is relaxed and familiar",
    ],
    suggested_step: "No extra step.",
    recentUpdateTitle: "Everything looks familiar",
    recentUpdateSummary:
      "Breakfast check-in is consistent with Mdm Tan's 25-day baseline. Reply timing, wellbeing, and language are all within her personal normal.",
    recentUpdateConfidence: "high confidence",
    followingUpTitle: "No follow-up needed",
    followingUpMessage:
      "If something seems different, Nomi will check in with Mdm Tan before contacting you.",
    followingUpSuggestedStep: null,
  },

  "2026-09-03T04:30:00+00:00": {
    label: "changed_from_usual",
    meal: "Lunch",
    tracks: { rhythm: 2, self_report: 1, language: 2 },
    replies: [
      { from: "nomi", text: "Hi Mdm Tan, lunchtime check-in! How are you doing? 🍲" },
      { from: "senior", text: "Abit tired today, not so hungry" },
      { from: "nomi", text: "Thank you for sharing. Could you rate your wellbeing 1–5?" },
      { from: "senior", text: "3" },
      { from: "nomi", text: "Noted. Rest well — I'll check in at dinner 🌙" },
      { from: "senior", text: "Mmm ok" },
    ],
    reasons: [
      "Reply time slightly longer than usual but within range",
      "Wellbeing dropped to 3/5 — below her usual 4",
      "Language signals mild fatigue: 'abit tired', 'not so hungry'",
    ],
    suggested_step: "Message or call when convenient.",
    recentUpdateTitle: "Something seems different",
    recentUpdateSummary:
      "Nomi noticed a subtle shift at lunch: Mdm Tan's self-reported wellbeing dropped to 3/5, and her language suggests mild fatigue. This is a gentle flag, not an alert.",
    recentUpdateConfidence: "moderate confidence",
    followingUpTitle: "No follow-up needed",
    followingUpMessage:
      "Nomi will continue monitoring and will check in with Mdm Tan at dinner before escalating.",
    followingUpSuggestedStep: null,
  },

  "2026-09-03T10:30:00+00:00": {
    label: "as_usual",
    meal: "Dinner",
    tracks: { rhythm: 2, self_report: 2, language: 1 },
    replies: [
      { from: "nomi", text: "Good evening Mdm Tan! Dinner time 🍲 How are you feeling?" },
      { from: "senior", text: "Just finished eating, feeling okay" },
      { from: "nomi", text: "Glad to hear! Could you rate your wellbeing from 1–5?" },
      { from: "senior", text: "4" },
      { from: "nomi", text: "Thank you Mdm Tan! Rest well 🌿" },
      { from: "senior", text: "Ok ok" },
    ],
    reasons: [
      "Reply time within her usual 20–30 min window",
      "Wellbeing self-reported at 4/5 — consistent with baseline",
      "Language tone is relaxed and familiar",
    ],
    suggested_step: "No extra step.",
    recentUpdateTitle: "Everything looks familiar",
    recentUpdateSummary:
      "Dinner check-in is consistent with Mdm Tan's 25-day baseline. Reply timing, wellbeing, and language are all within her personal normal.",
    recentUpdateConfidence: "high confidence",
    followingUpTitle: "No follow-up needed",
    followingUpMessage:
      "If something seems different, Nomi will check in with Mdm Tan before contacting you.",
    followingUpSuggestedStep: null,
  },
};

export const LUNCH_CHECKIN_AT = "2026-09-03T04:30:00+00:00";

export const LANDING_UPDATE_SCENARIO = DEMO_SCENARIOS[LUNCH_CHECKIN_AT]!;

/** Used after a live Needs you now check-in scores in this visit (not tied to a seeded row). */
export const LIVE_NEEDS_YOU_NOW_UPDATE: DemoScenarioUi = {
  label: "needs_you_now",
  meal: "Live check-in",
  tracks: { rhythm: 0, self_report: 0, language: 2 },
  replies: [
    { from: "nomi", text: "Hi Mdm Tan! It's Nomi checking in 😊 How are you feeling right now?" },
    { from: "senior", text: "1" },
    {
      from: "nomi",
      text: "Thanks for sharing. How are you feeling compared with this morning — same, better, or worse? 🌿",
    },
    { from: "senior", text: "worse" },
    { from: "nomi", text: "Is there anything you need help with today? 🙏" },
    { from: "senior", text: "Dizzy, cannot stand up properly. Need help." },
    { from: "nomi", text: "Thank you, I've noted this. Take care 💚" },
  ],
  reasons: [
    "Wellbeing reported at 1/5 — the lowest observed",
    "Language signals distress: 'dizzy', 'cannot stand up', 'need help'",
  ],
  suggested_step: "Call or visit when you can.",
  recentUpdateTitle: "Something seems different",
  recentUpdateSummary:
    "Mdm Tan's latest check-in showed a wellbeing of 1/5 and distress language. Nomi checked in with her directly before this alert was sent.",
  recentUpdateConfidence: "high confidence",
  followingUpTitle: "Caregiver attention requested",
  followingUpMessage:
    "Mdm Tan indicated she may need help. Nomi verified with her directly before escalating.",
  followingUpSuggestedStep:
    "Please reach out soon to understand what support may be helpful.",
};

