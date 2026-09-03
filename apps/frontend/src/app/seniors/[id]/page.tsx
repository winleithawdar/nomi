import { notFound } from "next/navigation";

import { AppShell } from "@/components/app-shell";
import { BaselineMetricCard } from "@/components/baseline-metric-card";
import { BaselineProgress } from "@/components/baseline-progress";
import { LiveCheckinPanel } from "@/components/live-checkin-panel";
import { RecentObservations } from "@/components/recent-observations";
import { ResponseLatencyChart } from "@/components/response-latency-chart";
import { SessionAssessmentCard } from "@/components/session-assessment-card";
import { StatusBadge } from "@/components/status-badge";
import { WellbeingChart } from "@/components/wellbeing-chart";
import { Card, CardContent } from "@/components/ui/card";
import { Separator } from "@/components/ui/separator";
import {
  getLatestAnomaly,
  getLatestSession,
  getLiveCheckin,
  getSchedule,
  getSeniorDetail,
  getVerificationStatus,
} from "@/lib/api/seniors";
import { ApiError } from "@/lib/api/client";
import { formatDailyRate, formatMinutes, formatPercent } from "@/lib/format";

export const dynamic = "force-dynamic";

export default async function SeniorDetailPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;

  try {
    const [data, detection, verification, live, schedule, latestSession] = await Promise.all([
      getSeniorDetail(id),
      getLatestAnomaly(id),
      getVerificationStatus(id),
      getLiveCheckin(id).catch(() => null),
      getSchedule(id),
      getLatestSession(id),
    ]);
    const { senior, baseline } = data;
    const lastPattern =
      baseline.status === "stable"
        ? `Usual reply around ${formatMinutes(baseline.response_latency_minutes.median)}`
        : "Still learning their usual pattern";

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

          <LiveCheckinPanel
            seniorId={senior.id}
            seniorName={senior.name}
            detected={detection.detected}
            detection={detection}
            initialLive={live}
          />

          <SessionAssessmentCard
            seniorId={senior.id}
            schedule={schedule}
            session={latestSession?.session ?? null}
          />

          <Card>
            <CardContent className="space-y-5 p-5 sm:p-6">
              <div className="space-y-2">
                <p className="text-sm font-medium text-[var(--primary)]">What Nomi noticed</p>
                <h2 className="text-xl font-semibold">
                  {detection.detected ? "Change from their usual pattern" : "No unusual change detected"}
                </h2>
                <p className="text-sm leading-6 text-[var(--muted-foreground)]">
                  {detection.summary ||
                    (detection.status === "insufficient_history"
                      ? "Nomi is still collecting enough personal history for this detector."
                      : "Recent behaviour remains within this senior's usual pattern.")}
                </p>
                <p className="text-xs capitalize text-[var(--muted-foreground)]">
                  {detection.status === "ok" ? `${detection.confidence} confidence` : "Learning"}
                </p>
              </div>
              <Separator />
              <div className="space-y-2">
                <p className="text-sm font-medium text-[var(--primary)]">Checked with them first</p>
                <h2 className="text-xl font-semibold">
                  {verification.active_verification
                    ? "Waiting for a reply"
                    : verification.latest_alert
                      ? "Caregiver attention requested"
                      : "No active check-in"}
                </h2>
                <p className="text-sm leading-6 text-[var(--muted-foreground)]">
                  {verification.active_verification?.check_in_message ??
                    verification.latest_alert?.verification_outcome ??
                    "Nomi will check with them first when something meaningful changes from their usual."}
                </p>
                {verification.latest_alert ? (
                  <p className="text-sm">
                    <span className="font-medium">Suggested next step:</span> {verification.latest_alert.suggested_action}
                  </p>
                ) : null}
              </div>
            </CardContent>
          </Card>

          <section className="grid grid-cols-2 gap-3" aria-label="Personal baseline metrics">
            <BaselineMetricCard
              label="Typical response"
              value={formatMinutes(baseline.response_latency_minutes.median)}
              helper="Median reply time from recent check-ins."
            />
            <BaselineMetricCard
              label="Response variation"
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
              label="How often they reply"
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

          <ResponseLatencyChart points={data.response_latency_series} />
          <WellbeingChart observations={data.recent_observations} />

          <section className="space-y-3">
            <div>
              <h2 className="text-xl font-semibold tracking-tight">Recent observations</h2>
              <p className="text-sm text-[var(--muted-foreground)]">
                The most recent check-ins collected directly through Nomi.
              </p>
            </div>
            <RecentObservations observations={data.recent_observations} />
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
