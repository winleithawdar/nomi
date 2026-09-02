export function formatMinutes(value: number | null, fallback = "Not available"): string {
  if (value === null) return fallback;
  return `${Math.round(value)} min`;
}

export function formatDateTime(value: string | null): string {
  if (!value) return "Not available";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "Not available";
  return new Intl.DateTimeFormat("en-SG", {
    day: "numeric",
    month: "short",
    year: "numeric",
    hour: "numeric",
    minute: "2-digit",
  }).format(date);
}

export function formatObservationLabel(current: number, minimum: number): string {
  return `${current} of ${minimum} observations`;
}

export function formatPercent(value: number | null): string {
  if (value === null) return "Not available";
  return `${Math.round(value * 100)}%`;
}

export function formatDailyRate(value: number | null, windowDays: number): string {
  if (value === null || windowDays <= 0) return "Not available";
  return `${(value / windowDays).toFixed(1)} / day`;
}
