import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import type { BaselineObservation } from "@/lib/api/types";
import { formatDateTime, formatMinutes } from "@/lib/format";

export function RecentObservations({ observations }: { observations: BaselineObservation[] }) {
  if (observations.length === 0) {
    return (
      <div className="rounded-3xl border border-dashed border-[var(--border)] bg-[var(--muted)]/40 p-8 text-sm text-[var(--muted-foreground)]">
        No observations have been collected yet.
      </div>
    );
  }

  return (
    <div className="rounded-3xl border border-[var(--border)] bg-white">
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
  );
}
