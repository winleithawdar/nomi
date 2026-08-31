import type { Route } from "next";
import Link from "next/link";

import { NoticeBadge } from "@/components/notice-badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import type { SeniorSummary } from "@/lib/api/types";

export function NoticeCard({ senior }: { senior: SeniorSummary }) {
  return (
    <Link href={`/seniors/${senior.id}` as Route} className="block">
      <Card className="h-full">
        <CardHeader className="gap-3 pb-3">
          <div className="flex items-start justify-between gap-3">
            <div>
              <p className="text-sm text-[var(--muted-foreground)]">{senior.name}</p>
              <CardTitle className="mt-1 text-xl">Change from this person&apos;s usual pattern</CardTitle>
            </div>
            <NoticeBadge status={senior.notice.status} />
          </div>
        </CardHeader>
        <CardContent className="space-y-3">
          <p className="text-sm leading-6 text-[var(--muted-foreground)]">{senior.notice.headline}</p>
          {senior.notice.findings.length > 0 ? (
            <ul className="space-y-2 text-sm leading-6 text-[var(--foreground)]">
              {senior.notice.findings.map((finding) => (
                <li key={finding.signal}>{finding.explanation}</li>
              ))}
            </ul>
          ) : null}
        </CardContent>
      </Card>
    </Link>
  );
}
