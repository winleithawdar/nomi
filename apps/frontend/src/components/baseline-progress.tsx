import { Progress } from "@/components/ui/progress";
import { formatObservationLabel } from "@/lib/format";

export function BaselineProgress({
  current,
  minimum,
}: {
  current: number;
  minimum: number;
}) {
  const percent = Math.min(100, Math.round((current / minimum) * 100));

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between text-sm text-[var(--muted-foreground)]">
        <span>{formatObservationLabel(current, minimum)}</span>
        <span>{percent}%</span>
      </div>
      <Progress value={percent} aria-label="Baseline learning progress" />
    </div>
  );
}
