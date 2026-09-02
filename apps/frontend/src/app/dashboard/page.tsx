import { AppShell } from "@/components/app-shell";
import { EmptyState } from "@/components/empty-state";
import { MetricCard } from "@/components/metric-card";
import { PageHeader } from "@/components/page-header";
import { SeniorCard } from "@/components/senior-card";
import { Card, CardContent } from "@/components/ui/card";
import { getAlerts, getSeniors } from "@/lib/api/seniors";

export const dynamic = "force-dynamic";

export default async function DashboardPage() {
  const [data, alerts] = await Promise.all([getSeniors(), getAlerts()]);

  return (
    <AppShell currentPath="/dashboard">
      <div className="space-y-8">
        <PageHeader
          eyebrow="Caregiver overview"
          title="Baseline learning across the people you support"
          description="See who is still building a recent interaction baseline and who already has an established personal pattern."
        />

        <section className="grid gap-5 md:grid-cols-2 xl:grid-cols-4" aria-label="Summary metrics">
          <MetricCard
            label="Seniors monitored"
            value={data.summary.seniors_monitored}
            description="Total people currently included in the caregiver view."
          />
          <MetricCard
            label="Currently learning"
            value={data.summary.seniors_learning}
            description="Seniors whose personal baseline is still being established."
          />
          <MetricCard
            label="Baselines established"
            value={data.summary.baselines_established}
            description="Seniors with enough recent observations for a stable baseline."
          />
          <MetricCard
            label="Recent check-ins"
            value={data.summary.recent_checkins}
            description="Interactions captured over the most recent seven days."
          />
        </section>

        <section className="space-y-4" aria-label="Caregiver alerts">
          <div className="space-y-1">
            <h2 className="text-2xl font-semibold tracking-tight">Latest caregiver alerts</h2>
            <p className="text-sm text-[var(--muted-foreground)]">
              Alerts appear only after Nomi verifies the detected change or receives no reassuring response.
            </p>
          </div>
          {alerts.length === 0 ? (
            <EmptyState
              title="No caregiver alerts"
              description="There are no unresolved changes requiring caregiver attention."
            />
          ) : (
            <div className="grid gap-4 lg:grid-cols-2">
              {alerts.slice(0, 4).map((alert) => (
                <Card key={alert.id}>
                  <CardContent className="space-y-3 p-5">
                    <div className="flex items-center justify-between gap-3">
                      <p className="font-semibold">{alert.what_changed}</p>
                      <span className="rounded-full bg-[var(--muted)] px-2.5 py-1 text-xs font-medium capitalize">
                        {alert.status}
                      </span>
                    </div>
                    <p className="text-sm text-[var(--muted-foreground)]">{alert.context}</p>
                    <p className="text-sm"><span className="font-medium">Next step:</span> {alert.suggested_action}</p>
                  </CardContent>
                </Card>
              ))}
            </div>
          )}
        </section>

        <section className="space-y-4">
          <div className="space-y-1">
            <h2 className="text-2xl font-semibold tracking-tight">Senior overview</h2>
            <p className="text-sm text-[var(--muted-foreground)]">
              Select a senior to review their personal baseline and recent interaction pattern.
            </p>
          </div>
          {data.seniors.length === 0 ? (
            <EmptyState
              title="No seniors yet"
              description="Once check-ins begin, Nomi will start building a personal baseline here."
              actionHref="/seniors"
              actionLabel="View seniors"
            />
          ) : (
            <div className="grid gap-5 lg:grid-cols-2">
              {data.seniors.map((senior) => (
                <SeniorCard key={senior.id} senior={senior} />
              ))}
            </div>
          )}
        </section>
      </div>
    </AppShell>
  );
}
