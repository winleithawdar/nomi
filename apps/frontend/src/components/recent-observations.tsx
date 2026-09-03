import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import type { BaselineObservation } from "@/lib/api/types";
import { formatCompactDateTime, formatDateTime, formatMinutes } from "@/lib/format";

function ObservationCard({ observation }: { observation: BaselineObservation }) {
  return (
    <article className="rounded-2xl border border-[var(--border)] bg-white p-4">
      <p className="text-sm font-medium">{formatCompactDateTime(observation.occurred_at)}</p>
      <dl className="mt-3 grid grid-cols-2 gap-3 text-sm">
        <div>
          <dt className="text-xs text-[var(--muted-foreground)]">Response latency</dt>
          <dd className="mt-0.5 font-medium">{formatMinutes(observation.response_latency_minutes, "Missed")}</dd>
        </div>
        <div>
          <dt className="text-xs text-[var(--muted-foreground)]">Missed check-in</dt>
          <dd className="mt-0.5 font-medium">{observation.missed_checkin ? "Yes" : "No"}</dd>
        </div>
        <div>
          <dt className="text-xs text-[var(--muted-foreground)]">Interaction count</dt>
          <dd className="mt-0.5 font-medium">{observation.interaction_frequency}</dd>
        </div>
        <div>
          <dt className="text-xs text-[var(--muted-foreground)]">Wellbeing</dt>
          <dd className="mt-0.5 font-medium">{observation.wellbeing_score ?? "Not reported"}</dd>
        </div>
      </dl>
    </article>
  );
}

export function RecentObservations({ observations }: { observations: BaselineObservation[] }) {
  if (observations.length === 0) {
    return (
      <div className="rounded-3xl border border-dashed border-[var(--border)] bg-[var(--muted)]/40 p-8 text-sm text-[var(--muted-foreground)]">
        No observations have been collected yet.
      </div>
    );
  }

  return (
    <>
      <div className="space-y-3 md:hidden">
        {observations.map((observation) => (
          <ObservationCard key={observation.occurred_at} observation={observation} />
        ))}
      </div>
      <div className="hidden rounded-3xl border border-[var(--border)] bg-white md:block">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Date</TableHead>
              <TableHead>Response latency</TableHead>
              <TableHead>Missed check-in</TableHead>
              <TableHead>Interaction count</TableHead>
              <TableHead>Wellbeing score</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {observations.map((observation) => (
              <TableRow key={observation.occurred_at}>
                <TableCell>{formatDateTime(observation.occurred_at)}</TableCell>
                <TableCell>{formatMinutes(observation.response_latency_minutes, "Missed")}</TableCell>
                <TableCell>{observation.missed_checkin ? "Yes" : "No"}</TableCell>
                <TableCell>{observation.interaction_frequency}</TableCell>
                <TableCell>{observation.wellbeing_score ?? "Not reported"}</TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>
    </>
  );
}
