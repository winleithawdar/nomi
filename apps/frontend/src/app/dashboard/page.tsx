import type { Route } from "next";
import Link from "next/link";

import { AnimatedList } from "@/components/animated-list";
import { AlertItem } from "@/components/alert-item";
import { AppShell } from "@/components/app-shell";
import { AttentionCard } from "@/components/attention-card";
import { EmptyState } from "@/components/empty-state";
import { MetricCard } from "@/components/metric-card";
import { StatusBadge } from "@/components/status-badge";
import { getAlerts, getSeniors } from "@/lib/api/seniors";

export const dynamic = "force-dynamic";

export default async function DashboardPage() {
  const [data, alerts] = await Promise.all([getSeniors(), getAlerts(10)]);
  const names = new Map(data.seniors.map((senior) => [senior.id, senior.name]));
  const [featuredAlert, ...otherAlerts] = alerts;

  return (
    <AppShell>
      <div className="space-y-7">
        <div className="space-y-1">
          <p className="text-sm text-[var(--muted-foreground)]">Good to see you, Sarah</p>
          <h1 className="text-2xl font-semibold tracking-tight md:text-3xl">How is everyone?</h1>
          <p className="text-sm leading-6 text-[var(--muted-foreground)]">
            Personal normal, not population normal.
          </p>
        </div>

        <section className="space-y-3" aria-label="Needs you now">
          <div className="flex items-end justify-between gap-3">
            <div>
              <h2 className="text-lg font-semibold tracking-tight">Needs you now</h2>
              <p className="text-sm text-[var(--muted-foreground)]">
                Latest caregiver alerts after Nomi checked in.
              </p>
            </div>
            <Link href={"/alerts" as Route} className="text-sm font-medium text-[var(--primary)]">
              All alerts
            </Link>
          </div>
          {alerts.length === 0 ? (
            <EmptyState
              title="Nothing needs you right now"
              description="Nomi only alerts after verifying with the senior or no reassuring reply."
            />
          ) : (
            <AnimatedList>
              {featuredAlert ? (
                <AttentionCard>
                  <AlertItem
                    alert={featuredAlert}
                    seniorName={names.get(featuredAlert.senior_id)}
                    className="border-0 bg-transparent hover:bg-transparent"
                  />
                </AttentionCard>
              ) : null}
              {otherAlerts.slice(0, 2).map((alert) => (
                <AlertItem key={alert.id} alert={alert} seniorName={names.get(alert.senior_id)} />
              ))}
            </AnimatedList>
          )}
        </section>

        <section className="grid grid-cols-3 gap-2" aria-label="Summary">
          <MetricCard label="Monitored" value={data.summary.seniors_monitored} />
          <MetricCard label="Learning" value={data.summary.seniors_learning} />
          <MetricCard label="Recent check-ins" value={data.summary.recent_checkins} />
        </section>

        <section className="space-y-3" aria-label="People">
          <div className="flex items-end justify-between gap-3">
            <div>
              <h2 className="text-lg font-semibold tracking-tight">People</h2>
              <p className="text-sm text-[var(--muted-foreground)]">Open someone to see their usual pattern.</p>
            </div>
            <Link href={"/seniors" as Route} className="text-sm font-medium text-[var(--primary)]">
              View all
            </Link>
          </div>
          {data.seniors.length === 0 ? (
            <EmptyState
              title="No seniors yet"
              description="Once check-ins begin, Nomi will start building a personal baseline here."
              actionHref="/seniors"
              actionLabel="View people"
            />
          ) : (
            <div className="flex flex-wrap gap-2">
              {data.seniors.map((senior) => (
                <Link
                  key={senior.id}
                  href={`/seniors/${senior.id}` as Route}
                  className="inline-flex min-h-11 items-center gap-2 rounded-full border border-[var(--border)] bg-white px-3 py-2 text-sm"
                >
                  <span className="font-medium">{senior.name}</span>
                  <StatusBadge status={senior.baseline_status} />
                </Link>
              ))}
            </div>
          )}
        </section>
      </div>
    </AppShell>
  );
}
