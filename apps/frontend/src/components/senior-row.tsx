import type { Route } from "next";
import Link from "next/link";
import { ChevronRight } from "lucide-react";

import { StatusBadge } from "@/components/status-badge";
import type { SeniorSummary } from "@/lib/api/types";
import { formatCompactDateTime } from "@/lib/format";

export function SeniorRow({ senior }: { senior: SeniorSummary }) {
  return (
    <Link
      href={`/seniors/${senior.id}` as Route}
      className="flex min-h-14 items-center gap-3 rounded-2xl border border-[var(--border)] bg-white px-4 py-3 transition-colors hover:bg-[var(--muted)]/50"
    >
      <div className="min-w-0 flex-1">
        <div className="flex items-center gap-2">
          <p className="truncate font-medium">{senior.name}</p>
          <StatusBadge status={senior.baseline_status} />
        </div>
        <p className="mt-1 truncate text-sm text-[var(--muted-foreground)]">
          {senior.relationship} · {formatCompactDateTime(senior.latest_interaction_at)}
        </p>
      </div>
      <ChevronRight className="h-4 w-4 shrink-0 text-[var(--muted-foreground)]" aria-hidden />
    </Link>
  );
}
