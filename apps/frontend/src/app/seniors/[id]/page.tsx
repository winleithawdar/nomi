import { notFound } from "next/navigation";

import { AppShell } from "@/components/app-shell";
import { BaselineMetricCard } from "@/components/baseline-metric-card";
import { BaselineStatusCard } from "@/components/baseline-status-card";
import { RecentObservations } from "@/components/recent-observations";
import { ResponseLatencyChart } from "@/components/response-latency-chart";
import { StatusBadge } from "@/components/status-badge";
import { Card, CardContent } from "@/components/ui/card";
import {
  getLatestAnomaly,
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
    const [data, detection, verification] = await Promise.all([
      getSeniorDetail(id),
      getLatestAnomaly(id),
      getVerificationStatus(id),
    ]);
    const { senior, baseline } = data;

    return (
      <AppShell currentPath="/seniors">
        <div className="space-y-8">
          <Card className="overflow-hidden">
            <CardContent className="flex flex-col gap-5 p-6 sm:p-8">
              <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
                <div className="space-y-2">
                  <p className="text-sm font-medium text-[var(--primary)]">Senior baseline</p>
                  <h1 className="text-3xl font-semibold tracking-tight">{senior.name}</h1>
                  <p className="text-sm text-[var(--muted-foreground)]">
                    {senior.relationship} • {senior.age_band}
                  </p>
                </div>
                <div className="flex flex-wrap items-center gap-3">
                  <StatusBadge status={baseline.status} />
                  <div className="rounded-full bg-[var(--muted)] px-3 py-1 text-sm text-[var(--muted-foreground)]">
                    {baseline.total_interactions} observations
                  </div>
                </div>
              </div>
            </CardContent>
          </Card>

          <BaselineStatusCard senior={senior} baseline={baseline} />

          <section className="grid gap-5 lg:grid-cols-2" aria-label="Detection and verification">
            <Card>
              <CardContent className="space-y-3 p-6">
                <p className="text-sm font-medium text-[var(--primary)]">Latest detection</p>
                <h2 className="text-xl font-semibold">
                  {detection.detected ? "Change noticed" : "No unusual change detected"}
                </h2>
                <p className="text-sm text-[var(--muted-foreground)]">
                  {detection.summary ||
                    (detection.status === "insufficient_history"
                      ? "Nomi is still collecting enough personal history for this detector."
                      : "Recent behaviour remains within this senior's usual pattern.")}
                </p>
                <p className="text-xs capitalize text-[var(--muted-foreground)]">
                  {detection.status === "ok" ? `${detection.confidence} confidence` : "Learning"}
                </p>
              </CardContent>
            </Card>

            <Card>
              <CardContent className="space-y-3 p-6">
                <p className="text-sm font-medium text-[var(--primary)]">Verification</p>
                <h2 className="text-xl font-semibold">
                  {verification.active_verification
                    ? "Waiting for senior response"
                    : verification.latest_alert
                      ? "Caregiver attention requested"
                      : "No active verification"}
                </h2>
                <p className="text-sm text-[var(--muted-foreground)]">
                  {verification.active_verification?.check_in_message ??
                    verification.latest_alert?.verification_outcome ??
                    "Nomi will check with the senior first when a meaningful change is detected."}
                </p>
                {verification.latest_alert ? (
                  <p className="text-sm"><span className="font-medium">Suggested next step:</span> {verification.latest_alert.suggested_action}</p>
                ) : null}
              </CardContent>
            </Card>
          </section>

          <section className="grid gap-5 md:grid-cols-2 xl:grid-cols-4">
            <BaselineMetricCard
              label="Typical response time"
              value={formatMinutes(baseline.response_latency_minutes.median)}
              helper="Median response latency over recent check-ins."
            />
            <BaselineMetricCard
              label="Response variation"
              value={baseline.response_latency_minutes.stddev === null ? "Not available" : `±${Math.round(baseline.response_latency_minutes.stddev)} min`}
              helper="Rolling standard deviation from this senior's own recent responses."
            />
            <BaselineMetricCard
              label="Missed check-in rate"
              value={formatPercent(baseline.missed_checkin_rate.rate)}
              helper="Recent rate of missed expected check-ins."
            />
            <BaselineMetricCard
              label="Interaction frequency"
              value={formatDailyRate(
                baseline.interaction_frequency.mean,
                baseline.metadata.frequency_window_days,
              )}
              helper="Average recent interaction count per day within the rolling window."
            />
            {baseline.wellbeing_score.observation_count > 0 ? (
              <BaselineMetricCard
                label="Wellbeing baseline"
                value={baseline.wellbeing_score.mean === null ? "Not available" : baseline.wellbeing_score.mean.toFixed(1)}
                helper="Average self-reported wellbeing from recent structured check-ins."
              />
            ) : null}
          </section>

          <ResponseLatencyChart points={data.response_latency_series} />

          <section className="space-y-4">
            <div>
              <h2 className="text-2xl font-semibold tracking-tight">Recent observations</h2>
              <p className="text-sm text-[var(--muted-foreground)]">
                The most recent check-ins collected directly through Nomi for this senior.
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
