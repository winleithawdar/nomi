import Link from "next/link";
import {
  Activity,
  ArrowRight,
  Bell,
  CheckCircle2,
  Clock3,
  Moon,
  TrendingDown,
  Users,
} from "lucide-react";

import { AppShell } from "@/components/app-shell";
import { getSeniors } from "@/lib/api/seniors";

export const dynamic = "force-dynamic";

export default async function DashboardPage() {
  const [data, alerts] = await Promise.all([getSeniors(), getAlerts(10)]);
  const names = new Map(data.seniors.map((senior) => [senior.id, senior.name]));
  const [featuredAlert, ...otherAlerts] = alerts;

  const attentionSeniors = data.seniors.filter(
    (senior) => senior.status !== "stable"
  );

  return (
    <AppShell currentPath="/dashboard">
      <div className="space-y-8">
        {/* Header */}
        <section>
          <p className="text-sm font-medium text-[var(--muted-foreground)]">
            Caregiver overview
          </p>

          <div className="mt-2 flex flex-col justify-between gap-4 md:flex-row md:items-end">
            <div>
              <h1 className="text-3xl font-semibold tracking-tight">
                Good morning
              </h1>

              <p className="mt-2 max-w-2xl text-sm text-[var(--muted-foreground)]">
                Here&apos;s what Nomi noticed about the people you support.
              </p>
            </div>

            <div className="flex items-center gap-2 rounded-full border bg-white px-4 py-2 text-sm shadow-sm">
              <span className="h-2 w-2 rounded-full bg-emerald-500" />
              Monitoring is active
            </div>
          </div>
        </section>

        {/* Summary */}
        <section className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
          <SummaryCard
            icon={<Users className="h-5 w-5" />}
            label="Seniors monitored"
            value={data.summary.seniors_monitored}
            description="Currently in your care view"
          />

          <SummaryCard
            icon={<Bell className="h-5 w-5" />}
            label="Detected changes"
            value={data.summary.detected_changes}
            description="Meaningful changes recently detected"
          />

          <SummaryCard
            icon={<TrendingDown className="h-5 w-5" />}
            label="Needs attention"
            value={data.summary.needs_attention}
            description="Seniors outside their usual pattern"
            emphasis
          />

          <SummaryCard
            icon={<Clock3 className="h-5 w-5" />}
            label="Recent check-ins"
            value={data.summary.recent_checkins}
            description="Interactions over the last 7 days"
          />
        </section>

        {/* Main alert */}
        <section>
          <div className="mb-4">
            <h2 className="text-xl font-semibold">Meaningful changes</h2>
            <p className="mt-1 text-sm text-[var(--muted-foreground)]">
              Nomi highlights behaviour that differs from each senior&apos;s
              own normal pattern.
            </p>
          </div>

          {attentionSeniors.length > 0 ? (
            <div className="space-y-4">
              {attentionSeniors.map((senior) => (
                <ChangeCard key={senior.id} senior={senior} />
              ))}
            </div>
          ) : (
            <div className="rounded-3xl border bg-white p-8">
              <div className="flex items-center gap-3">
                <CheckCircle2 className="h-6 w-6 text-emerald-500" />

                <div>
                  <p className="font-semibold">
                    Everything looks within normal range
                  </p>

                  <p className="text-sm text-[var(--muted-foreground)]">
                    Nomi has not detected any meaningful changes.
                  </p>
                </div>
              </div>
            </div>
          )}
        </section>

        {/* Senior overview */}
        <section>
          <div className="mb-4 flex items-end justify-between">
            <div>
              <h2 className="text-xl font-semibold">Your seniors</h2>
              <p className="mt-1 text-sm text-[var(--muted-foreground)]">
                A quick view of each person&apos;s current status.
              </p>
            </div>

            <Link
              href="/seniors"
              className="hidden items-center gap-1 text-sm font-medium hover:underline sm:flex"
            >
              View all
              <ArrowRight className="h-4 w-4" />
            </Link>
          </div>

          <div className="grid gap-4 md:grid-cols-2">
            {data.seniors.map((senior) => (
              <SeniorOverviewCard key={senior.id} senior={senior} />
            ))}
          </div>
        </section>
      </div>
    </AppShell>
  );
}

function SummaryCard({
  icon,
  label,
  value,
  description,
  emphasis = false,
}: {
  icon: React.ReactNode;
  label: string;
  value: number;
  description: string;
  emphasis?: boolean;
}) {
  return (
    <div
      className={`rounded-3xl border bg-white p-5 shadow-sm ${
        emphasis ? "border-orange-200" : ""
      }`}
    >
      <div className="flex items-center justify-between">
        <div className="rounded-xl bg-slate-100 p-2">
          {icon}
        </div>

        {emphasis && (
          <span className="rounded-full bg-orange-100 px-2.5 py-1 text-xs font-medium text-orange-700">
            Attention
          </span>
        )}
      </div>

      <div className="mt-5">
        <p className="text-3xl font-semibold">{value}</p>
        <p className="mt-1 text-sm font-medium">{label}</p>
        <p className="mt-1 text-xs text-[var(--muted-foreground)]">
          {description}
        </p>
      </div>
    </div>
  );
}

function ChangeCard({
  senior,
}: {
  senior: Awaited<ReturnType<typeof getSeniors>>["seniors"][number];
}) {
  const isHigh = senior.latestChange?.severity === "high";

  return (
    <div
      className={`rounded-3xl border bg-white p-6 shadow-sm ${
        isHigh ? "border-orange-200" : "border-amber-200"
      }`}
    >
      <div className="flex flex-col gap-5 md:flex-row md:items-center md:justify-between">
        <div className="flex items-start gap-4">
          <div className="flex h-12 w-12 shrink-0 items-center justify-center rounded-2xl bg-orange-100 text-lg font-semibold text-orange-700">
            {senior.initials}
          </div>

          <div>
            <div className="flex flex-wrap items-center gap-2">
              <h3 className="font-semibold">{senior.name}</h3>

              <span className="rounded-full bg-orange-100 px-2.5 py-1 text-xs font-medium text-orange-700">
                {isHigh ? "Needs attention" : "Monitoring"}
              </span>
            </div>

            <p className="mt-1 text-sm font-medium">
              {senior.latestChange?.title}
            </p>

            <p className="mt-1 max-w-2xl text-sm text-[var(--muted-foreground)]">
              {senior.latestChange?.description}
            </p>
          </div>
        </div>

        <Link
          href={`/seniors/${senior.id}`}
          className="inline-flex shrink-0 items-center justify-center gap-2 rounded-xl bg-slate-900 px-4 py-2.5 text-sm font-medium text-white hover:bg-slate-800"
        >
          View senior
          <ArrowRight className="h-4 w-4" />
        </Link>
      </div>

      <div className="mt-6 grid gap-3 border-t pt-5 sm:grid-cols-3">
        <MiniMetric
          icon={<Activity className="h-4 w-4" />}
          label="Activity"
          value={`${senior.activity.deviation > 0 ? "+" : ""}${senior.activity.deviation}%`}
          abnormal={Math.abs(senior.activity.deviation) > 10}
        />

        <MiniMetric
          icon={<Moon className="h-4 w-4" />}
          label="Sleep"
          value={`${senior.sleep.deviation > 0 ? "+" : ""}${senior.sleep.deviation}%`}
          abnormal={Math.abs(senior.sleep.deviation) > 10}
        />

        <MiniMetric
          icon={<Clock3 className="h-4 w-4" />}
          label="Response"
          value={`${senior.responseLatency.deviation > 0 ? "+" : ""}${senior.responseLatency.deviation}%`}
          abnormal={Math.abs(senior.responseLatency.deviation) > 10}
        />
      </div>
    </div>
  );
}

function MiniMetric({
  icon,
  label,
  value,
  abnormal,
}: {
  icon: React.ReactNode;
  label: string;
  value: string;
  abnormal: boolean;
}) {
  return (
    <div className="flex items-center gap-3 rounded-2xl bg-slate-50 p-3">
      <div className="text-[var(--muted-foreground)]">{icon}</div>

      <div>
        <p className="text-xs text-[var(--muted-foreground)]">{label}</p>

        <p
          className={`text-sm font-semibold ${
            abnormal ? "text-orange-700" : ""
          }`}
        >
          {value} from baseline
        </p>
      </div>
    </div>
  );
}

function SeniorOverviewCard({
  senior,
}: {
  senior: Awaited<ReturnType<typeof getSeniors>>["seniors"][number];
}) {
  const status =
    senior.status === "stable"
      ? {
          label: "Stable",
          className: "bg-emerald-100 text-emerald-700",
        }
      : senior.status === "monitoring"
        ? {
            label: "Monitoring",
            className: "bg-amber-100 text-amber-700",
          }
        : {
            label: "Needs attention",
            className: "bg-orange-100 text-orange-700",
          };

  return (
    <Link
      href={`/seniors/${senior.id}`}
      className="group rounded-3xl border bg-white p-5 shadow-sm transition hover:-translate-y-0.5 hover:shadow-md"
    >
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="flex h-11 w-11 items-center justify-center rounded-2xl bg-slate-100 text-sm font-semibold">
            {senior.initials}
          </div>

          <div>
            <p className="font-semibold">{senior.name}</p>
            <p className="text-xs text-[var(--muted-foreground)]">
              Age {senior.age}
            </p>
          </div>
        </div>

        <span
          className={`rounded-full px-2.5 py-1 text-xs font-medium ${status.className}`}
        >
          {status.label}
        </span>
      </div>

      <div className="mt-5">
        <div className="mb-2 flex justify-between text-xs">
          <span className="text-[var(--muted-foreground)]">
            Baseline confidence
          </span>
          <span className="font-medium">{senior.baselineConfidence}%</span>
        </div>

        <div className="h-2 overflow-hidden rounded-full bg-slate-100">
          <div
            className="h-full rounded-full bg-slate-800"
            style={{ width: `${senior.baselineConfidence}%` }}
          />
        </div>
      </div>

      <div className="mt-5 flex items-center justify-between border-t pt-4 text-sm">
        <span className="text-[var(--muted-foreground)]">
          {senior.observationDays} days of observations
        </span>

        <span className="flex items-center gap-1 font-medium group-hover:underline">
          Details
          <ArrowRight className="h-4 w-4" />
        </span>
      </div>
    </Link>
  );
}