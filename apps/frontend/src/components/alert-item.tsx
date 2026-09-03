import type { Route } from "next";
import Link from "next/link";
import { ChevronRight } from "lucide-react";

import type { CaregiverAlert } from "@/lib/api/types";
import { formatCompactDateTime } from "@/lib/format";
import { cn } from "@/lib/utils";

export function AlertItem({
  alert,
  seniorName,
  className,
}: {
  alert: CaregiverAlert;
  seniorName?: string;
  className?: string;
}) {
  return (
    <Link
      href={`/seniors/${alert.senior_id}` as Route}
      className={cn(
        "flex min-h-14 items-start gap-3 rounded-2xl border border-[var(--border)] bg-white p-4 transition-colors hover:bg-[var(--muted)]/40",
        className,
      )}
    >
      <div className="min-w-0 flex-1 space-y-2">
        <div className="flex flex-wrap items-center gap-2">
          {seniorName ? <p className="text-sm font-medium text-[var(--primary)]">{seniorName}</p> : null}
          <span className="rounded-full bg-[var(--muted)] px-2 py-0.5 text-xs font-medium capitalize text-[var(--muted-foreground)]">
            {alert.status}
          </span>
        </div>
        <p className="font-semibold leading-snug">{alert.what_changed}</p>
        <p className="text-sm leading-6 text-[var(--muted-foreground)]">{alert.context}</p>
        <p className="text-sm">
          <span className="font-medium">Next step:</span> {alert.suggested_action}
        </p>
        <p className="text-xs text-[var(--muted-foreground)]">{formatCompactDateTime(alert.created_at)}</p>
      </div>
      <ChevronRight className="mt-1 h-4 w-4 shrink-0 text-[var(--muted-foreground)]" aria-hidden />
    </Link>
  );
}
