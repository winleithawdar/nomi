import type { Route } from "next";
import Link from "next/link";
import { ArrowRight, Clock3, NotebookPen } from "lucide-react";

import { StatusBadge } from "@/components/status-badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import type { SeniorSummary } from "@/lib/api/types";
import { formatDateTime } from "@/lib/format";

export function SeniorCard({ senior }: { senior: SeniorSummary }) {
  return (
    <Link href={`/seniors/${senior.id}` as Route} className="block">
      <Card className="h-full transition-transform hover:-translate-y-0.5">
        <CardHeader className="gap-4 pb-4">
          <div className="flex items-start justify-between gap-3">
            <div>
              <CardTitle>{senior.name}</CardTitle>
              <p className="mt-1 text-sm text-[var(--muted-foreground)]">
                {senior.relationship} • {senior.age_band}
              </p>
            </div>
            <StatusBadge status={senior.baseline_status} />
          </div>
        </CardHeader>
        <CardContent className="space-y-4">
          <p className="text-sm leading-6 text-[var(--muted-foreground)]">{senior.status_text}</p>
          <div className="grid gap-3 text-sm text-[var(--muted-foreground)] sm:grid-cols-2">
            <div className="flex items-center gap-2">
              <NotebookPen className="h-4 w-4 text-[var(--primary)]" />
              <span>{senior.observation_count} check-ins</span>
            </div>
            <div className="flex items-center gap-2">
              <Clock3 className="h-4 w-4 text-[var(--primary)]" />
              <span>{formatDateTime(senior.latest_interaction_at)}</span>
            </div>
          </div>
          <div className="flex items-center justify-between border-t border-[var(--border)] pt-4 text-sm font-medium text-[var(--foreground)]">
            <span>View recent updates</span>
            <ArrowRight className="h-4 w-4" />
          </div>
        </CardContent>
      </Card>
    </Link>
  );
}
