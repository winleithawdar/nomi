"use client";

import { useRouter } from "next/navigation";
import { useEffect, useRef, useState, type ReactNode } from "react";

import { AttentionCard } from "@/components/attention-card";
import { Badge } from "@/components/ui/badge";
import { Card } from "@/components/ui/card";
import { getLatestSession, getSchedule } from "@/lib/api/seniors";
import type {
  SeniorSchedule,
  SessionAssessment,
  SessionLabel,
  SessionThreadMessage,
} from "@/lib/api/seniors";
import type { BaselineObservation } from "@/lib/api/types";
import { DEMO_SCENARIOS, buildScenarioFromObservation } from "@/lib/demo-scenarios";
import { formatCompactDateTime, formatMealName, formatScheduledClock } from "@/lib/format";

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

function parseClosedAtMs(closedAt: string): number {
  const hasTimezone = /(?:Z|[+-]\d{2}:?\d{2})$/i.test(closedAt);
  return Date.parse(hasTimezone ? closedAt : `${closedAt}Z`);
}

function ChatBubble({ from, text }: { from: "nomi" | "senior"; text: string }) {
  const isNomi = from === "nomi";
  return (
    <div className={`flex ${isNomi ? "justify-start" : "justify-end"}`}>
      <div
        className={`max-w-[80%] rounded-2xl px-3.5 py-2.5 text-sm leading-5 ${
          isNomi
            ? "bg-[var(--muted)] text-[var(--muted-foreground)]"
            : "bg-[var(--primary)] text-white"
        }`}
      >
        {!isNomi && <p className="mb-0.5 text-xs font-medium opacity-75">Mdm Tan</p>}
        {text}
      </div>
    </div>
  );
}

function CheckinSummaryBody({
  label,
  title,
  reasons,
  suggested_step,
  tracks,
  thread,
}: {
  label: SessionLabel;
  title: string;
  reasons: string[];
  suggested_step: string;
  tracks: { rhythm: number; self_report: number; language: number };
  thread: SessionThreadMessage[];
}) {
  const maxTrack = Math.max(tracks.rhythm, tracks.self_report, tracks.language);

  return (
    <div className="space-y-5 p-5 sm:p-6">
      <div className="space-y-1">
        <div className="flex flex-wrap items-center gap-2">
          <p className="text-sm font-medium text-[var(--primary)]">This check in</p>
          <Badge variant={labelVariant(label)}>{LABEL_COPY[label]}</Badge>
        </div>
        <h2 className="text-xl font-semibold">{title}</h2>
      </div>

      <div className="grid grid-cols-1 gap-5 md:grid-cols-2">
        <div className="space-y-4">
          <div>
            <p className="mb-1.5 text-xs font-medium uppercase tracking-wide text-[var(--muted-foreground)]">
              What Nomi observed
            </p>
            <ul className="list-disc space-y-1 pl-5 text-sm leading-6">
              {reasons.map((reason, index) => (
                <li key={`${index}-${reason}`}>{reason}</li>
              ))}
            </ul>
          </div>
          <p className="text-sm leading-6">
            <span className="font-medium">Suggested next step:</span> {suggested_step}
          </p>
          <div className="space-y-1.5">
            <p className="text-xs font-medium uppercase tracking-wide text-[var(--muted-foreground)]">
              Signal tracks
            </p>
            <div className="grid grid-cols-1 gap-2 sm:grid-cols-3">
              <TrackCell
                label="Rhythm"
                value={tracks.rhythm}
                emphasized={tracks.rhythm === maxTrack}
              />
              <TrackCell
                label="Self-report"
                value={tracks.self_report}
                emphasized={tracks.self_report === maxTrack}
              />
              <TrackCell
                label="Language"
                value={tracks.language}
                emphasized={tracks.language === maxTrack}
              />
            </div>
            <p className="text-xs leading-5 text-[var(--muted-foreground)]">
              Nomi looks at reply timing, wellbeing, and language. This is not a diagnosis.
            </p>
          </div>
        </div>

        <div className="space-y-2">
          <p className="text-xs font-medium uppercase tracking-wide text-[var(--muted-foreground)]">
            Check-in conversation
          </p>
          <div className="space-y-2">
            {thread.map((message, index) => (
              <ChatBubble key={index} from={message.from} text={message.text} />
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}

function wrapSummary(label: SessionLabel, body: ReactNode) {
  if (label === "needs_you_now") return <AttentionCard>{body}</AttentionCard>;
  return <Card>{body}</Card>;
}

export function SessionAssessmentCard({
  seniorId,
  schedule: initialSchedule,
  session: initialSession,
  pinnedObservation,
  liveFocus = false,
}: {
  seniorId: string;
  schedule: SeniorSchedule | null;
  session: SessionAssessment | null;
  pinnedObservation?: BaselineObservation | null;
  liveFocus?: boolean;
}) {
  const router = useRouter();
  const [schedule, setSchedule] = useState(initialSchedule);
  const [session, setSession] = useState<SessionAssessment | null>(
    liveFocus ? initialSession : null,
  );
  const [thread, setThread] = useState<SessionThreadMessage[] | null>(null);
  const pageOpenedAtRef = useRef<number>(Date.now());
  const navigatedRef = useRef(false);

  useEffect(() => {
    setSchedule(initialSchedule);
  }, [initialSchedule]);

  useEffect(() => {
    if (!liveFocus) return;
    let cancelled = false;

    if (initialSession) {
      setSession(initialSession);
    }

    void (async () => {
      try {
        const latest = await getLatestSession(seniorId);
        if (cancelled) return;
        if (latest?.session) {
          setSession(latest.session);
          setThread(latest.thread ?? null);
        }
      } catch {
        // Keep showing initialSession if fetch fails.
      }
    })();

    const scrollTimer = window.setTimeout(() => {
      document
        .getElementById("section-this-checkin")
        ?.scrollIntoView({ behavior: "smooth", block: "start" });
    }, 50);

    return () => {
      cancelled = true;
      window.clearTimeout(scrollTimer);
    };
  }, [liveFocus, seniorId, initialSession]);

  useEffect(() => {
    const pageOpenedAt = pageOpenedAtRef.current;
    const startedAt = Date.now();
    let cancelled = false;

    const tick = async () => {
      try {
        const [nextSession, nextSchedule] = await Promise.all([
          getLatestSession(seniorId),
          getSchedule(seniorId),
        ]);
        if (cancelled) return;

        const closedAt = nextSession?.session?.closed_at;
        const isFreshClose =
          Boolean(closedAt) && parseClosedAtMs(closedAt!) >= pageOpenedAt;

        if (liveFocus) {
          if (nextSession?.session) {
            setSession(nextSession.session);
            setThread(nextSession.thread ?? null);
          }
        } else if (isFreshClose) {
          if (!navigatedRef.current) {
            navigatedRef.current = true;
            router.replace(`/seniors/${seniorId}?live=1#section-this-checkin`);
          }
          if (!pinnedObservation) {
            setSession(nextSession!.session);
            setThread(nextSession!.thread ?? null);
          }
        }

        if (nextSchedule) setSchedule(nextSchedule);
      } catch {
        // Keep showing the last known card if a poll fails.
      }
    };

    void tick();

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
  }, [seniorId, pinnedObservation, liveFocus, router]);

  if (pinnedObservation && !liveFocus) {
    const scenario =
      DEMO_SCENARIOS[pinnedObservation.occurred_at] ??
      buildScenarioFromObservation(pinnedObservation);

    return wrapSummary(
      scenario.label,
      <CheckinSummaryBody
        label={scenario.label}
        title={`${scenario.meal} · ${formatCompactDateTime(pinnedObservation.occurred_at)}`}
        reasons={scenario.reasons}
        suggested_step={scenario.suggested_step}
        tracks={scenario.tracks}
        thread={scenario.replies}
      />,
    );
  }

  if (!session) {
    return (
      <Card>
        <div className="space-y-5 p-5 sm:p-6">
          <div className="space-y-2">
            <p className="text-sm font-medium text-[var(--primary)]">This check in</p>
            <h2 className="text-xl font-semibold">{nextScheduledLine(schedule)}</h2>
            <p className="text-sm leading-6 text-[var(--muted-foreground)]">
              Send a check-in to start. Nomi will share an update after a few replies.
            </p>
          </div>
        </div>
      </Card>
    );
  }

  return wrapSummary(
    session.label,
    <CheckinSummaryBody
      label={session.label}
      title={`${formatMealName(session.meal)} · Latest check-in`}
      reasons={session.reasons}
      suggested_step={session.suggested_step}
      tracks={{
        rhythm: session.rhythm_level,
        self_report: session.self_report_level,
        language: session.language_level,
      }}
      thread={thread ?? []}
    />,
  );
}
