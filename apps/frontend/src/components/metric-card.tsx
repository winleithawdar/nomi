import { NumberTicker } from "@/components/number-ticker";

export function MetricCard({
  label,
  value,
}: {
  label: string;
  value: number;
}) {
  return (
    <div className="rounded-2xl border border-[var(--border)] bg-white px-3 py-3 text-center">
      <NumberTicker value={value} className="text-2xl font-semibold" />
      <p className="mt-1 text-xs leading-5 text-[var(--muted-foreground)]">{label}</p>
    </div>
  );
}
