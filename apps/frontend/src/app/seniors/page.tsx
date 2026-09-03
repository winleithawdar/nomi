import { AppShell } from "@/components/app-shell";
import { EmptyState } from "@/components/empty-state";
import { PageHeader } from "@/components/page-header";
import { SeniorRow } from "@/components/senior-row";
import { getSeniors } from "@/lib/api/seniors";

export const dynamic = "force-dynamic";

export default async function SeniorsPage() {
  const data = await getSeniors();

  return (
    <AppShell>
      <div className="space-y-6">
        <PageHeader
          eyebrow="People"
          title="People you support"
          description="See recent check-ins and whether Nomi has enough history to understand what is usual for each person."
        />

        {data.seniors.length === 0 ? (
          <EmptyState
            title="No seniors available"
            description="This view will fill in as check-ins begin."
          />
        ) : (
          <div className="space-y-2">
            {data.seniors.map((senior) => (
              <SeniorRow key={senior.id} senior={senior} />
            ))}
          </div>
        )}
      </div>
    </AppShell>
  );
}
