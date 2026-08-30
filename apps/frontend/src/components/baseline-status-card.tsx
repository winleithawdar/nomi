import { CheckCircle2, Sparkles } from "lucide-react";

import { BaselineProgress } from "@/components/baseline-progress";
import { StatusBadge } from "@/components/status-badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import type { SeniorBaseline, SeniorProfile } from "@/lib/api/types";
import { formatDateTime } from "@/lib/format";

export function BaselineStatusCard({
  senior,
  baseline,
}: {
  senior: SeniorProfile;
  baseline: SeniorBaseline;
}) {
  const isStable = baseline.status === "stable";

  return (
    <Card>
      <CardHeader className="gap-4">
        <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
          <div className="space-y-2">
            <div className="flex items-center gap-2">
              {isStable ? <CheckCircle2 className="h-5 w-5 text-[var(--primary)]" /> : <Sparkles className="h-5 w-5 text-[var(--primary)]" />}
              <CardTitle>{isStable ? "Personal baseline established" : `Learning ${senior.name}'s normal interaction pattern`}</CardTitle>
            </div>
            <p className="text-sm leading-6 text-[var(--muted-foreground)]">
              {isStable
                ? "Recent behaviour is summarised from this senior's own interaction history."
                : "Observations are still being collected, so Nomi should not make strong judgments from this pattern yet."}
            </p>
          </div>
          <StatusBadge status={baseline.status} />
        </div>
      </CardHeader>
      <CardContent className="space-y-5">
        <div className="grid gap-4 sm:grid-cols-3">
          <div>
            <p className="text-sm text-[var(--muted-foreground)]">Observations collected</p>
            <p className="mt-1 text-2xl font-semibold">{baseline.total_interactions}</p>
          </div>
          <div>
            <p className="text-sm text-[var(--muted-foreground)]">Baseline threshold</p>
            <p className="mt-1 text-2xl font-semibold">{baseline.min_observations_for_stable}</p>
          </div>
          <div>
            <p className="text-sm text-[var(--muted-foreground)]">Last updated</p>
            <p className="mt-1 text-sm font-medium">{formatDateTime(baseline.as_of)}</p>
          </div>
        </div>
        {!isStable ? (
          <BaselineProgress current={baseline.total_interactions} minimum={baseline.min_observations_for_stable} />
        ) : null}
      </CardContent>
    </Card>
  );
}
