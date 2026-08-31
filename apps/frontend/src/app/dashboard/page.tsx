import { AppShell } from "@/components/app-shell";
import { EmptyState } from "@/components/empty-state";
import { MetricCard } from "@/components/metric-card";
import { PageHeader } from "@/components/page-header";
import { SeniorCard } from "@/components/senior-card";
import { getSeniors } from "@/lib/api/seniors";

export const dynamic = "force-dynamic";

export default async function DashboardPage() {
  const data = await getSeniors();

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
