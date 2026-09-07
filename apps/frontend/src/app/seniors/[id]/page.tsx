import { notFound } from "next/navigation";

import { AppShell } from "@/components/app-shell";
import { BaselineMetricCard } from "@/components/baseline-metric-card";
import { BaselineProgress } from "@/components/baseline-progress";
import { CaregiverUpdateCard } from "@/components/caregiver-update-card";
import { LiveCheckinPanel } from "@/components/live-checkin-panel";
import { RecentObservations } from "@/components/recent-observations";
import { ResponseLatencyChart } from "@/components/response-latency-chart";
import { SeniorSectionNav } from "@/components/senior-section-nav";
import { SessionAssessmentCard } from "@/components/session-assessment-card";
import { StatusBadge } from "@/components/status-badge";
import { WellbeingChart } from "@/components/wellbeing-chart";
import { Card, CardContent } from "@/components/ui/card";
import {
  getLatestSession,
  getLiveCheckin,
  getSchedule,
  getSeniorDetail,
} from "@/lib/api/seniors";
import { ApiError } from "@/lib/api/client";
import { DEMO_SCENARIOS, buildScenarioFromObservation } from "@/lib/demo-scenarios";
import { formatDailyRate, formatMinutes, formatPercent } from "@/lib/format";

export const dynamic = "force-dynamic";

export default async function SeniorDetailPage({
  params,
  searchParams,
}: {
  params: Promise<{ id: string }>;
  searchParams: Promise<{ checkin?: string; live?: string }>;
}) {
  const { id } = await params;
  const { checkin, live: liveParam } = await searchParams;
  const liveFocus = liveParam === "1";

  try {
    const [data, live, schedule, latestSession] = await Promise.all([
      getSeniorDetail(id),
      getLiveCheckin(id).catch(() => null),
      getSchedule(id),
      getLatestSession(id),
    ]);
    const { senior, baseline } = data;
    const pinnedObservation =
      liveFocus
        ? null
        : checkin
          ? (data.recent_observations.find((o) => o.occurred_at === checkin) ?? null)
          : null;
    const pinnedScenario = pinnedObservation
      ? (DEMO_SCENARIOS[pinnedObservation.occurred_at] ?? buildScenarioFromObservation(pinnedObservation))
      : null;
    const lastPattern =
      baseline.status === "stable"
        ? `Usual reply around ${formatMinutes(baseline.response_latency_minutes.median)}`
        : "Still getting to know their routine";

    return (
      <AppShell>
        <div className="space-y-6">
          <Card className="overflow-hidden">
            <CardContent className="space-y-4 p-5 sm:p-6">
              <div className="flex items-start justify-between gap-3">
                <div className="min-w-0 space-y-1">
                  <p className="text-sm font-medium text-[var(--primary)]">{senior.relationship}</p>
                  <h1 className="text-2xl font-semibold tracking-tight md:text-3xl">{senior.name}</h1>
                  <p className="text-sm text-[var(--muted-foreground)]">{lastPattern}</p>
                </div>
                <StatusBadge status={baseline.status} />
              </div>
              {baseline.status === "learning" ? (
                <BaselineProgress current={baseline.total_interactions} minimum={baseline.min_observations_for_stable} />
              ) : (
                <p className="text-sm text-[var(--muted-foreground)]">
                  Recent behaviour is summarised from {senior.name}&apos;s own interaction history.
                </p>
              )}
            </CardContent>
          </Card>

          <SeniorSectionNav />

          <section id="section-live" className="scroll-mt-32">
            <LiveCheckinPanel
              seniorId={senior.id}
              seniorName={senior.name}
              initialLive={live}
            />
          </section>

          <section id="section-this-checkin" className="scroll-mt-32">
            <SessionAssessmentCard
              seniorId={senior.id}
              schedule={schedule}
              session={latestSession?.session ?? null}
              pinnedObservation={pinnedObservation}
              liveFocus={liveFocus}
            />
          </section>

          <section id="section-update" className="scroll-mt-32">
            <CaregiverUpdateCard
              seniorId={senior.id}
              pinnedScenario={pinnedScenario}
              liveFocus={liveFocus}
            />
          </section>

          <section
            id="section-overview"
            className="scroll-mt-32 grid grid-cols-2 gap-3"
            aria-label="Recent check-in overview"
          >
            <BaselineMetricCard
              label="Typical response"
              value={formatMinutes(baseline.response_latency_minutes.median)}
              helper="Typical reply time from recent check-ins."
            />
            <BaselineMetricCard
              label="Reply-time variation"
              value={
                baseline.response_latency_minutes.stddev === null
                  ? "Not available"
                  : `±${Math.round(baseline.response_latency_minutes.stddev)} min`
              }
              helper="Spread from their own recent replies."
            />
            <BaselineMetricCard
              label="Missed check-ins"
              value={formatPercent(baseline.missed_checkin_rate.rate)}
              helper="Recent rate of missed expected check-ins."
            />
            <BaselineMetricCard
              label="Reply frequency"
              value={formatDailyRate(
                baseline.interaction_frequency.mean,
                baseline.metadata.frequency_window_days,
              )}
              helper="Average interactions per day in the rolling window."
            />
            {baseline.wellbeing_score.observation_count > 0 ? (
              <BaselineMetricCard
                label="Wellbeing usual"
                value={baseline.wellbeing_score.mean === null ? "Not available" : baseline.wellbeing_score.mean.toFixed(1)}
                helper="Average self-reported wellbeing from recent check-ins."
              />
            ) : null}
          </section>

          <section id="section-charts" className="scroll-mt-32 space-y-6">
            <ResponseLatencyChart points={data.response_latency_series} />
            <WellbeingChart observations={data.recent_observations} />
          </section>

          <section id="section-history" className="scroll-mt-32 space-y-3">
            <div>
              <h2 className="text-xl font-semibold tracking-tight">Recent check-ins</h2>
              <p className="text-sm text-[var(--muted-foreground)]">
                A quick look at the most recent replies and check-ins.
              </p>
            </div>
            <RecentObservations
              observations={data.recent_observations}
              seniorId={senior.id}
              selectedCheckin={checkin ?? null}
            />
          </section>
        </div>
      </AppShell>
    );
  } catch (error) {
    if (error instanceof ApiError && error.status === 404) {
      notFound();
    }
    throw error;
  }
}
