import { NoticeBadge } from "@/components/notice-badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import type { NoticeAssessment } from "@/lib/api/types";

export function NoticePanel({ notice }: { notice: NoticeAssessment }) {
  return (
    <Card>
      <CardHeader className="gap-3">
        <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
          <div className="space-y-2">
            <p className="text-sm font-medium text-[var(--primary)]">Notice layer</p>
            <CardTitle>Compared with this senior&apos;s own recent pattern</CardTitle>
            <p className="text-sm leading-6 text-[var(--muted-foreground)]">
              Nomi describes behavioural change from personal normal. It does not diagnose illness or alert a caregiver from this screen.
            </p>
          </div>
          <NoticeBadge status={notice.status} />
        </div>
      </CardHeader>
      <CardContent className="space-y-4">
        <p className="text-sm leading-6">{notice.headline}</p>
        {notice.findings.length > 0 ? (
          <ul className="space-y-3">
            {notice.findings.map((finding) => (
              <li
                key={finding.signal}
                className="rounded-2xl border border-[var(--border)] bg-[var(--muted)]/50 px-4 py-3 text-sm leading-6"
              >
                {finding.explanation}
              </li>
            ))}
          </ul>
        ) : (
          <p className="text-sm leading-6 text-[var(--muted-foreground)]">
            No change-from-usual findings on the latest observations.
          </p>
        )}
      </CardContent>
    </Card>
  );
}
