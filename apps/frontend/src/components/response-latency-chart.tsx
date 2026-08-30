import type { ResponseLatencyPoint } from "@/lib/api/types";

function buildPath(
  points: ResponseLatencyPoint[],
  width: number,
  height: number,
  valueKey: "response_latency_minutes" | "rolling_mean_minutes",
) {
  const values = points.map((point) => point[valueKey]);
  const maxValue = Math.max(...values, 1);
  const step = points.length > 1 ? width / (points.length - 1) : width;

  return points
    .map((point, index) => {
      const x = step * index;
      const y = height - (point[valueKey] / maxValue) * height;
      return `${index === 0 ? "M" : "L"} ${x} ${y}`;
    })
    .join(" ");
}

export function ResponseLatencyChart({ points }: { points: ResponseLatencyPoint[] }) {
  if (points.length === 0) {
    return (
      <div className="rounded-3xl border border-dashed border-[var(--border)] bg-[var(--muted)]/40 p-8 text-sm text-[var(--muted-foreground)]">
        No response latency history is available yet.
      </div>
    );
  }

  const width = 520;
  const height = 180;
  const latencyPath = buildPath(points, width, height, "response_latency_minutes");
  const meanPath = buildPath(points, width, height, "rolling_mean_minutes");

  return (
    <div className="rounded-3xl border border-[var(--border)] bg-white p-5">
      <div className="mb-5 flex items-center justify-between gap-4">
        <div>
          <h3 className="font-semibold">Recent response latency</h3>
          <p className="text-sm text-[var(--muted-foreground)]">
            Response timing over recent check-ins with a rolling personal baseline reference.
          </p>
        </div>
        <div className="flex gap-4 text-xs text-[var(--muted-foreground)]">
          <div className="flex items-center gap-2">
            <span className="h-2.5 w-2.5 rounded-full bg-[var(--primary)]" />
            <span>Observed</span>
          </div>
          <div className="flex items-center gap-2">
            <span className="h-2.5 w-2.5 rounded-full bg-[var(--chart-secondary)]" />
            <span>Rolling mean</span>
          </div>
        </div>
      </div>
      <svg viewBox={`0 0 ${width} ${height + 36}`} className="h-[240px] w-full" role="img" aria-label="Response latency chart">
        <line x1="0" y1={height} x2={width} y2={height} stroke="var(--border)" strokeWidth="1" />
        <path d={meanPath} fill="none" stroke="var(--chart-secondary)" strokeWidth="3" strokeLinecap="round" />
        <path d={latencyPath} fill="none" stroke="var(--primary)" strokeWidth="3" strokeLinecap="round" />
        {points.map((point, index) => {
          const values = points.map((item) => item.response_latency_minutes);
          const maxValue = Math.max(...values, 1);
          const step = points.length > 1 ? width / (points.length - 1) : width;
          const x = step * index;
          const y = height - (point.response_latency_minutes / maxValue) * height;

          return <circle key={point.occurred_at} cx={x} cy={y} r="4" fill="var(--primary)" />;
        })}
        {points.map((point, index) => {
          const step = points.length > 1 ? width / (points.length - 1) : width;
          const x = step * index;
          const label = new Intl.DateTimeFormat("en-SG", {
            month: "short",
            day: "numeric",
          }).format(new Date(point.occurred_at));

          return (
            <text key={`${point.occurred_at}-label`} x={x} y={height + 24} textAnchor={index === 0 ? "start" : index === points.length - 1 ? "end" : "middle"} className="fill-[var(--muted-foreground)] text-[11px]">
              {label}
            </text>
          );
        })}
      </svg>
    </div>
  );
}
