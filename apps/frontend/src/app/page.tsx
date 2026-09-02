import Link from "next/link";
import { ArrowLeft, Activity, Clock3, Moon, TrendingDown, TrendingUp } from "lucide-react";

import { AppShell } from "@/components/app-shell";
import { StatusBadge } from "@/components/status-badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { getSenior } from "@/lib/api/seniors";

export const dynamic = "force-dynamic";

export default async function SeniorDetailPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  const senior = await getSenior(id);

  if (!senior) {
    return (
      <AppShell currentPath="/seniors">
        <div className="space-y-6">
          <Link
            href="/seniors"
            className="inline-flex items-center gap-2 text-sm font-medium text-[var(--muted-foreground)] hover:text-[var(--foreground)]"
          >
            <ArrowLeft className="h-4 w-4" />
            Back to seniors
          </Link>

          <Card>
            <CardContent className="p-8">
              <h1 className="text-2xl font-semibold">Senior not found</h1>
              <p className="mt-2 text-sm text-[var(--muted-foreground)]">
                We could not find the senior you are looking for.
              </p>
            </CardContent>
          </Card>
        </div>
      </AppShell>
    );
  }

  const metrics = [
    {
      label: "Daily activity",
      icon: Activity,
      current: `${senior.activity.current} hrs`,
      baseline: `${senior.activity.baseline} hrs`,
      deviation: senior.activity.deviation,
      description: "Average activity compared with their personal baseline.",
    },
    {
      label: "Sleep duration",
      icon: Moon,
      current: `${senior.sleep.current} hrs`,
      baseline: `${senior.sleep.baseline} hrs`,
      deviation: senior.sleep.deviation,
      description: "Recent sleep duration compared with their usual pattern.",
    },
    {
      label: "Response latency",
      icon: Clock3,
      current: `${senior.responseLatency.current} min`,
      baseline: `${senior.responseLatency.baseline} min`,
      deviation: senior.responseLatency.deviation,
      description: "Typical response time compared with their personal baseline.",
    },
  ];

  return (
    <AppShell currentPath="/seniors">
      <div className="space-y-8">

        {/* Back navigation */}
        <Link
          href="/seniors"
          className="inline-flex items-center gap-2 text-sm font-medium text-[var(--muted-foreground)] transition-colors hover:text-[var(--foreground)]"
        >
          <ArrowLeft className="h-4 w-4" />
          Back to seniors
        </Link>

        {/* Senior header */}
        <Card className="overflow-hidden">
          <CardContent className="p-6 sm:p-8">
            <div className="flex flex-col gap-6 sm:flex-row sm:items-center sm:justify-between">

              <div className="flex items-center gap-4">
                <div className="flex h-16 w-16 shrink-0 items-center justify-center rounded-2xl bg-[var(--primary)] text-lg font-semibold text-[var(--primary-foreground)]">
                  {senior.initials}
                </div>

                <div>
                  <p className="text-sm font-medium text-[var(--primary)]">
                    Personal baseline
                  </p>

                  <h1 className="mt-1 text-3xl font-semibold tracking-tight">
                    {senior.name}
                  </h1>

                  <p className="mt-1 text-sm text-[var(--muted-foreground)]">
                    Age {senior.age} • {senior.observationDays} days of observations
                  </p>
                </div>
              </div>

              <StatusBadge status={senior.status} />
            </div>
          </CardContent>
        </Card>

        {/* Baseline confidence */}
        <Card>
          <CardHeader>
            <CardTitle>Personal baseline</CardTitle>
          </CardHeader>

          <CardContent>
            <div className="flex flex-col gap-5 sm:flex-row sm:items-center sm:justify-between">
              <div>
                <p className="text-sm text-[var(--muted-foreground)]">
                  Baseline confidence
                </p>

                <p className="mt-1 text-4xl font-semibold tracking-tight">
                  {senior.baselineConfidence}%
                </p>
              </div>

              <div className="w-full max-w-md">
                <div className="h-3 overflow-hidden rounded-full bg-[var(--muted)]">
                  <div
                    className="h-full rounded-full bg-[var(--primary)]"
                    style={{ width: `${senior.baselineConfidence}%` }}
                  />
                </div>

                <p className="mt-2 text-sm text-[var(--muted-foreground)]">
                  Based on {senior.observationDays} days of recent observations.
                </p>
              </div>
            </div>
          </CardContent>
        </Card>

        {/* Behaviour metrics */}
        <section className="space-y-4">
          <div>
            <h2 className="text-2xl font-semibold tracking-tight">
              Behaviour patterns
            </h2>

            <p className="mt-1 text-sm text-[var(--muted-foreground)]">
              Current behaviour compared with {senior.name}&apos;s own recent baseline.
            </p>
          </div>

          <div className="grid gap-5 lg:grid-cols-3">
            {metrics.map((metric) => {
              const Icon = metric.icon;
              const isPositive = metric.deviation > 0;

              return (
                <Card key={metric.label}>
                  <CardContent className="p-6">
                    <div className="flex items-center justify-between">
                      <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-[var(--muted)]">
                        <Icon className="h-5 w-5 text-[var(--primary)]" />
                      </div>

                      <div className="flex items-center gap-1 text-sm font-medium">
                        {isPositive ? (
                          <TrendingUp className="h-4 w-4" />
                        ) : (
                          <TrendingDown className="h-4 w-4" />
                        )}

                        {Math.abs(metric.deviation)}%
                      </div>
                    </div>

                    <p className="mt-5 text-sm font-medium">
                      {metric.label}
                    </p>

                    <p className="mt-2 text-3xl font-semibold tracking-tight">
                      {metric.current}
                    </p>

                    <p className="mt-1 text-sm text-[var(--muted-foreground)]">
                      Usual: {metric.baseline}
                    </p>

                    <p className="mt-4 text-sm leading-6 text-[var(--muted-foreground)]">
                      {metric.description}
                    </p>
                  </CardContent>
                </Card>
              );
            })}
          </div>
        </section>

        {/* Detected change */}
        {senior.latestChange ? (
          <Card>
            <CardHeader>
              <div className="flex items-center justify-between gap-4">
                <div>
                  <p className="text-sm font-medium text-[var(--primary)]">
                    Detected change
                  </p>

                  <CardTitle className="mt-1">
                    {senior.latestChange.title}
                  </CardTitle>
                </div>

                <span className="shrink-0 rounded-full bg-[var(--muted)] px-3 py-1 text-xs font-medium capitalize">
                  {senior.latestChange.severity} priority
                </span>
              </div>
            </CardHeader>

            <CardContent>
              <p className="max-w-3xl text-sm leading-6 text-[var(--muted-foreground)]">
                {senior.latestChange.description}
              </p>

              <div className="mt-5 flex flex-wrap gap-4 text-sm text-[var(--muted-foreground)]">
                <span>
                  Metric:{" "}
                  <span className="font-medium text-[var(--foreground)]">
                    {senior.latestChange.metric}
                  </span>
                </span>

                <span>
                  Detected:{" "}
                  <span className="font-medium text-[var(--foreground)]">
                    {senior.latestChange.detectedAt}
                  </span>
                </span>
              </div>
            </CardContent>
          </Card>
        ) : (
          <Card>
            <CardContent className="p-6">
              <p className="text-sm font-medium">No meaningful changes detected</p>
              <p className="mt-1 text-sm text-[var(--muted-foreground)]">
                Recent observations are currently within {senior.name}&apos;s
                usual personal pattern.
              </p>
            </CardContent>
          </Card>
        )}

        {/* Demo note */}
        <div className="rounded-2xl border border-dashed border-[var(--border)] bg-[var(--muted)]/40 p-5">
          <p className="text-sm font-medium">
            Demo data
          </p>

          <p className="mt-1 text-sm leading-6 text-[var(--muted-foreground)]">
            These values are currently mock data for the frontend. The backend
            integration will replace them with live baseline and detection
            results.
          </p>
        </div>

      </div>
    </AppShell>
  );
}