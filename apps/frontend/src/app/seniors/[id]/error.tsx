"use client";

import { AppShell } from "@/components/app-shell";
import { ErrorState } from "@/components/error-state";

export default function SeniorDetailError() {
  return (
    <AppShell>
      <ErrorState
        title="Unable to load this baseline view"
        description="Nomi could not retrieve the senior's recent baseline data. Please try again after the backend is reachable."
      />
    </AppShell>
  );
}
