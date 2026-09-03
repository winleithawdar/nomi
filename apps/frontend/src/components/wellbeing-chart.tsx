"use client";

import { Bar, BarChart, CartesianGrid, Line, LineChart, XAxis, YAxis } from "recharts";

import { ChartContainer, ChartTooltip, ChartTooltipContent, type ChartConfig } from "@/components/ui/chart";
import type { BaselineObservation } from "@/lib/api/types";

const chartConfig = {
  wellbeing: {
    label: "Wellbeing",
    color: "var(--chart-3)",
  },
} satisfies ChartConfig;

function formatTick(value: string) {
  return new Intl.DateTimeFormat("en-SG", {
    month: "short",
    day: "numeric",
  }).format(new Date(value));
}

export function WellbeingChart({ observations }: { observations: BaselineObservation[] }) {
  const points = observations
    .filter((observation) => observation.wellbeing_score != null)
    .map((observation) => ({
      occurred_at: observation.occurred_at,
      wellbeing: observation.wellbeing_score as number,
    }));

  if (points.length === 0) {
    return null;
  }

  const Chart = points.length > 4 ? LineChart : BarChart;

  return (
    <div className="rounded-3xl border border-[var(--border)] bg-white p-5">
      <div className="mb-4">
        <h3 className="font-semibold">Recent wellbeing check-ins</h3>
        <p className="text-sm text-[var(--muted-foreground)]">
          Self-reported wellbeing from this person&apos;s own recent structured check-ins.
        </p>
      </div>
      <ChartContainer config={chartConfig} className="aspect-auto h-[220px] min-h-[200px] w-full">
        <Chart accessibilityLayer data={points} margin={{ left: 4, right: 8, top: 8, bottom: 0 }}>
          <CartesianGrid vertical={false} stroke="var(--border)" />
          <XAxis
            dataKey="occurred_at"
            tickLine={false}
            axisLine={false}
            tickMargin={8}
            minTickGap={28}
            tickFormatter={formatTick}
          />
          <YAxis tickLine={false} axisLine={false} width={28} domain={[0, 10]} />
          <ChartTooltip
            cursor={{ stroke: "var(--border)" }}
            content={
              <ChartTooltipContent
                labelFormatter={(value) =>
                  typeof value === "string" ? formatTick(value) : String(value ?? "")
                }
                formatter={(value) => (
                  <div className="flex w-full items-center justify-between gap-6">
                    <span className="text-[var(--muted-foreground)]">Wellbeing</span>
                    <span className="font-mono font-medium tabular-nums">
                      {typeof value === "number" ? value.toFixed(1) : "—"}
                    </span>
                  </div>
                )}
              />
            }
          />
          {points.length > 4 ? (
            <Line
              type="monotone"
              dataKey="wellbeing"
              stroke="var(--color-wellbeing)"
              strokeWidth={2.5}
              dot={{ r: 3, fill: "var(--color-wellbeing)", strokeWidth: 0 }}
            />
          ) : (
            <Bar dataKey="wellbeing" fill="var(--color-wellbeing)" radius={6} />
          )}
        </Chart>
      </ChartContainer>
    </div>
  );
}
