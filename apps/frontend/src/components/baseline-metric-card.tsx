import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

export function BaselineMetricCard({
  label,
  value,
  helper,
}: {
  label: string;
  value: string;
  helper: string;
}) {
  return (
    <Card>
      <CardHeader className="pb-2">
        <p className="text-sm text-[var(--muted-foreground)]">{label}</p>
      </CardHeader>
      <CardContent>
        <CardTitle className="text-3xl">{value}</CardTitle>
        <p className="mt-2 text-sm leading-6 text-[var(--muted-foreground)]">{helper}</p>
      </CardContent>
    </Card>
  );
}
