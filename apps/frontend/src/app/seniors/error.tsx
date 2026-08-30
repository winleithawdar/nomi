"use client";

import { AppShell } from "@/components/app-shell";
import { ErrorState } from "@/components/error-state";

export default function SeniorsError() {
  return (
    <AppShell currentPath="/seniors">
      <ErrorState
        title="Unable to load seniors"
        description="Nomi could not load the senior list. Please try again after the backend is available."
      />
    </AppShell>
  );
}
