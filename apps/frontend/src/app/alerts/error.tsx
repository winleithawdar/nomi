"use client";

import { AppShell } from "@/components/app-shell";
import { ErrorState } from "@/components/error-state";

export default function AlertsError() {
  return (
    <AppShell>
      <ErrorState
        title="Unable to load caregiver alerts"
        description="Nomi could not reach the alert feed just now. Please try again when the backend is available."
      />
    </AppShell>
  );
}
