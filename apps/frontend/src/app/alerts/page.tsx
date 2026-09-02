import { AnimatedList } from "@/components/animated-list";
import { AlertItem } from "@/components/alert-item";
import { AppShell } from "@/components/app-shell";
import { EmptyState } from "@/components/empty-state";
import { PageHeader } from "@/components/page-header";
import { getAlerts, getSeniors } from "@/lib/api/seniors";

export const dynamic = "force-dynamic";

export default async function AlertsPage() {
  const [alerts, seniors] = await Promise.all([getAlerts(), getSeniors()]);
  const names = new Map(seniors.seniors.map((senior) => [senior.id, senior.name]));

  return (
    <AppShell>
      <div className="space-y-6">
        <PageHeader
          eyebrow="Alerts"
          title="Caregiver alerts"
          description="Nomi only alerts after verifying with the senior or no reassuring reply."
        />

        {alerts.length === 0 ? (
          <EmptyState
            title="No caregiver alerts"
            description="Nomi only alerts after verifying with the senior or no reassuring reply."
          />
        ) : (
          <AnimatedList>
            {alerts.map((alert) => (
              <AlertItem key={alert.id} alert={alert} seniorName={names.get(alert.senior_id)} />
            ))}
          </AnimatedList>
        )}
      </div>
    </AppShell>
  );
}
