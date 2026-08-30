import { AppShell } from "@/components/app-shell";
import { EmptyState } from "@/components/empty-state";
import { PageHeader } from "@/components/page-header";
import { SeniorCard } from "@/components/senior-card";
import { getSeniors } from "@/lib/api/seniors";

export const dynamic = "force-dynamic";

export default async function SeniorsPage() {
  const data = await getSeniors();

  return (
    <AppShell currentPath="/seniors">
      <div className="space-y-8">
        <PageHeader
          eyebrow="Seniors"
          title="People you support"
          description="Each card shows whether Nomi is still learning a personal baseline or has enough recent history to describe the usual pattern."
        />

        {data.seniors.length === 0 ? (
          <EmptyState
            title="No seniors available"
            description="This view will populate once Nomi begins collecting direct check-in observations."
          />
        ) : (
          <div className="grid gap-5 lg:grid-cols-2">
            {data.seniors.map((senior) => (
              <SeniorCard key={senior.id} senior={senior} />
            ))}
          </div>
        )}
      </div>
    </AppShell>
  );
}
