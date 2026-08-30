import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

export function MetricCard({
  label,
  value,
  description,
}: {
  label: string;
  value: string | number;
  description: string;
}) {
  return (
    <Card>
      <CardHeader className="pb-3">
        <p className="text-sm text-[var(--muted-foreground)]">{label}</p>
        <CardTitle className="text-3xl">{value}</CardTitle>
      </CardHeader>
      <CardContent>
        <p className="text-sm leading-6 text-[var(--muted-foreground)]">{description}</p>
      </CardContent>
    </Card>
  );
}
