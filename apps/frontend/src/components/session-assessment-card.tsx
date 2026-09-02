"use client";

import { useEffect, useState } from "react";

import { AttentionCard } from "@/components/attention-card";
import { Badge } from "@/components/ui/badge";
import { Card } from "@/components/ui/card";
import { getLatestSession, getSchedule } from "@/lib/api/seniors";
import type { SeniorSchedule, SessionAssessment, SessionLabel } from "@/lib/api/seniors";
import { formatMealName, formatScheduledClock } from "@/lib/format";

const POLL_INTERVAL_MS = 3_000;
const POLL_DURATION_MS = 180_000;

const LABEL_COPY: Record<SessionLabel, string> = {
  as_usual: "As usual",
  changed_from_usual: "Changed from usual",
  needs_you_now: "Needs you now",
};

function labelVariant(label: SessionLabel): "stable" | "learning" | "neutral" {
  if (label === "as_usual") return "stable";
  if (label === "changed_from_usual") return "learning";
  return "neutral";
}

function nextScheduledLine(schedule: SeniorSchedule | null): string {
  if (!schedule) return "Next scheduled: Not available";
  const meal = formatMealName(schedule.next_meal);
  const clock = formatScheduledClock(schedule.next_at_iso, schedule.timezone);
  return `Next scheduled: ${meal} ${clock}`;
}

function TrackCell({
  label,
  value,
  emphasized,
}: {
  label: string;
  value: number;
  emphasized: boolean;
}) {
  return (
    <div className="rounded-2xl border border-[var(--border)] bg-white px-3 py-2">
      <p className="text-xs text-[var(--muted-foreground)]">{label}</p>
      <p
        className={
          emphasized
            ? "mt-0.5 text-sm font-semibold tabular-nums"
            : "mt-0.5 text-sm tabular-nums text-[var(--muted-foreground)]"
        }
      >
        {value}
        <span className="font-normal text-[var(--muted-foreground)]"> / 2</span>
      </p>
    </div>
  );
}

export function SessionAssessmentCard({
  seniorId,
  schedule: initialSchedule,
  session: initialSession,
}: {
  seniorId: string;
  schedule: SeniorSchedule | null;
  session: SessionAssessment | null;
}) {
  const [schedule, setSchedule] = useState(initialSchedule);
  const [session, setSession] = useState(initialSession);

  useEffect(() => {
    setSchedule(initialSchedule);
    setSession(initialSession);
  }, [initialSchedule, initialSession]);

  useEffect(() => {
    const startedAt = Date.now();
    let cancelled = false;

    const tick = async () => {
      try {
        const [nextSession, nextSchedule] = await Promise.all([
          getLatestSession(seniorId),
          getSchedule(seniorId),
        ]);
        if (cancelled) return;
        setSession(nextSession?.session ?? null);
        if (nextSchedule) setSchedule(nextSchedule);
      } catch {
        // Keep showing the last known card if a poll fails.
      }
    };

    const interval = window.setInterval(() => {
      if (Date.now() - startedAt >= POLL_DURATION_MS) {
        window.clearInterval(interval);
        return;
      }
      void tick();
    }, POLL_INTERVAL_MS);

    return () => {
      cancelled = true;
      window.clearInterval(interval);
    };
  }, [seniorId]);

  const needsYouNow = session?.label === "needs_you_now";
  const maxTrack = session
    ? Math.max(session.rhythm_level, session.self_report_level, session.language_level)
    : 0;

  const body = (
    <div className="space-y-5 p-5 sm:p-6">
      <div className="space-y-2">
        <div className="flex flex-wrap items-center gap-2">
          <p className="text-sm font-medium text-[var(--primary)]">This meal</p>
          {session ? (
            <Badge variant={labelVariant(session.label)}>{LABEL_COPY[session.label]}</Badge>
          ) : null}
        </div>
        <h2 className="text-xl font-semibold">{nextScheduledLine(schedule)}</h2>
        {session ? (
          <p className="text-sm leading-6 text-[var(--muted-foreground)]">
            Latest {formatMealName(session.meal).toLowerCase()} session.
          </p>
        ) : (
          <p className="text-sm leading-6 text-[var(--muted-foreground)]">
            No meal assessment yet. Nomi will show the three tracks after the third reply.
          </p>
        )}
      </div>

      {session ? (
        <>
          {session.suggested_step ? (
            <p className="text-sm leading-6">
              <span className="font-medium">Suggested next step:</span> {session.suggested_step}
            </p>
          ) : null}

          {session.reasons.length > 0 ? (
            <ul className="list-disc space-y-1 pl-5 text-sm leading-6">
              {session.reasons.map((reason, index) => (
                <li key={`${index}-${reason}`}>{reason}</li>
              ))}
            </ul>
          ) : null}

          <div className="space-y-2">
            <div className="grid grid-cols-3 gap-2" aria-label="Session tracks">
              <TrackCell
                label="Rhythm"
                value={session.rhythm_level}
                emphasized={session.rhythm_level === maxTrack}
              />
              <TrackCell
                label="Self-report"
                value={session.self_report_level}
                emphasized={session.self_report_level === maxTrack}
              />
              <TrackCell
                label="Language"
                value={session.language_level}
                emphasized={session.language_level === maxTrack}
              />
            </div>
            <p className="text-xs leading-5 text-[var(--muted-foreground)]">
              Nomi is not diagnosing. Same three tracks every meal. Label is the highest track, not an
              average. Updates after the third Telegram reply.
            </p>
          </div>
        </>
      ) : null}
    </div>
  );

  if (needsYouNow) {
    return <AttentionCard>{body}</AttentionCard>;
  }

  return <Card>{body}</Card>;
}
