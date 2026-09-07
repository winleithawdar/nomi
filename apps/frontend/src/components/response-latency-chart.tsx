"use client";

import { CartesianGrid, Line, LineChart, XAxis, YAxis } from "recharts";

import { ChartContainer, ChartTooltip, ChartTooltipContent, type ChartConfig } from "@/components/ui/chart";
import type { ResponseLatencyPoint } from "@/lib/api/types";

const chartConfig = {
  observed: {
    label: "Observed",
    color: "var(--chart-1)",
  },
  mean: {
    label: "Rolling mean",
    color: "var(--chart-2)",
  },
} satisfies ChartConfig;

function formatTick(value: string) {
  return new Intl.DateTimeFormat("en-SG", {
    month: "short",
    day: "numeric",
  }).format(new Date(value));
}

export function ResponseLatencyChart({ points }: { points: ResponseLatencyPoint[] }) {
  if (points.length === 0) {
    return (
      <div className="rounded-3xl border border-dashed border-[var(--border)] bg-[var(--muted)]/40 p-8 text-sm text-[var(--muted-foreground)]">
        No response latency history is available yet.
      </div>
    );
  }

  const data = points.map((point) => ({
    occurred_at: point.occurred_at,
    observed: point.response_latency_minutes,
    mean: point.rolling_mean_minutes,
  }));

  // For demo readability, keep the axis stable.
  // The demo’s “normal” range is ~20-30min, so we clamp to 0–40.
  const AXIS_MIN = 0;
  const AXIS_MAX = 40;

  const observedValues = data
    .map((d) => d.observed)
    .filter((v): v is number => typeof v === "number" && !Number.isNaN(v));

  const plotData = data.map((d) => {
    const observed = typeof d.observed === "number" ? d.observed : null;
    const observedLine = observed != null && observed <= AXIS_MAX ? observed : null;
    // Clamp outliers to the top of the chart for a consistent 0–40 axis.
    const observedOutlierDot =
      observed != null && observed > AXIS_MAX ? AXIS_MAX : null;

    return {
      ...d,
      observedLine,
      observedOutlierDot,
    };
  });

  return (
    <div className="rounded-3xl border border-[var(--border)] bg-white p-5">
      <div className="mb-4 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h3 className="font-semibold">Reply timing</h3>
          <p className="text-sm text-[var(--muted-foreground)]">
            Each point shows how long it took to reply. The lighter line shows their recent usual time.
          </p>
        </div>
        <div className="flex gap-4 text-xs text-[var(--muted-foreground)]">
          <div className="flex items-center gap-2">
            <span className="h-2.5 w-2.5 rounded-full bg-[var(--chart-1)]" />
            <span>Reply time</span>
          </div>
          <div className="flex items-center gap-2">
            <span className="h-2.5 w-2.5 rounded-full bg-[var(--chart-2)]" />
            <span>Usual time</span>
          </div>
        </div>
      </div>
      <ChartContainer
        config={chartConfig}
        className="aspect-auto h-[240px] min-h-[220px] w-full"
      >
        <LineChart
          accessibilityLayer
          data={plotData}
          margin={{ left: 4, right: 8, top: 8, bottom: 0 }}
        >
          <CartesianGrid vertical={false} stroke="var(--border)" />
          <XAxis
            dataKey="occurred_at"
            tickLine={false}
            axisLine={false}
            tickMargin={8}
            minTickGap={28}
            tickFormatter={formatTick}
          />
          <YAxis
            tickLine={false}
            axisLine={false}
            width={36}
            domain={[AXIS_MIN, AXIS_MAX]}
            tickFormatter={(value: number) => `${Math.round(value)}`}
          />
          <ChartTooltip
            cursor={{ stroke: "var(--border)" }}
            content={
              <ChartTooltipContent
                labelFormatter={(value) =>
                  typeof value === "string" ? formatTick(value) : String(value ?? "")
                }
                formatter={(value, name) => (
                  <div className="flex w-full items-center justify-between gap-6">
                    <span className="text-[var(--muted-foreground)]">
                      {name === "mean" ? "Rolling mean" : "Observed"}
                    </span>
                    <span className="font-mono font-medium tabular-nums">
                      {typeof value === "number" ? `${Math.round(value)} min` : "—"}
                    </span>
                  </div>
                )}
              />
            }
          />
          <Line
            type="monotone"
            dataKey="mean"
            stroke="var(--color-mean)"
            strokeWidth={2}
            dot={false}
          />

          {/* Normal observed replies (zoomed axis) */}
          <Line
            type="monotone"
            dataKey="observedLine"
            name="observed"
            stroke="var(--color-observed)"
            strokeWidth={2.5}
            dot={{ r: 3, fill: "var(--color-observed)", strokeWidth: 0 }}
            activeDot={{ r: 5 }}
          />

          {/* Outlier replies as a dot-only marker (no connecting line). */}
          <Line
            type="monotone"
            dataKey="observedOutlierDot"
            name="observed_outlier"
            stroke="transparent"
            strokeWidth={0}
            dot={{ r: 4, fill: "var(--color-observed)", strokeWidth: 0 }}
            activeDot={{ r: 6 }}
          />
        </LineChart>
      </ChartContainer>
    </div>
  );
}
