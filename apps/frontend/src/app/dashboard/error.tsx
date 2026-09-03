"use client";

import { AppShell } from "@/components/app-shell";
import { ErrorState } from "@/components/error-state";

export default function DashboardError() {
  return (
    <AppShell>
      <ErrorState
        title="Unable to load the caregiver overview"
        description="Nomi could not reach the baseline service just now. Please try again when the backend is available."
      />
    </AppShell>
  );
}
