import { AppShell } from "@/components/app-shell";
import { EmptyState } from "@/components/empty-state";

export default function SeniorNotFound() {
  return (
    <AppShell currentPath="/seniors">
      <EmptyState
        title="Senior not found"
        description="This baseline view is not available yet or the profile could not be found."
        actionHref="/seniors"
        actionLabel="Back to seniors"
      />
    </AppShell>
  );
}
