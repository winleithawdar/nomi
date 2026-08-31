const dateTimeFormatter = new Intl.DateTimeFormat("en-SG", {
  dateStyle: "medium",
  timeStyle: "short",
});

export function formatDateTime(value: string | null | undefined) {
  if (!value) {
    return "No interactions yet";
  }

  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) {
    return "No interactions yet";
  }

  return dateTimeFormatter.format(parsed);
}

export function formatMinutes(value: number | null | undefined, empty = "Not available") {
  if (value === null || value === undefined) {
    return empty;
  }

  return `${Math.round(value)} min`;
}

export function formatPercent(value: number | null | undefined) {
  if (value === null || value === undefined) {
    return "Not available";
  }

  return `${Math.round(value * 100)}%`;
}

export function formatDailyRate(mean: number | null | undefined, windowDays: number) {
  if (mean === null || mean === undefined || windowDays <= 0) {
    return "Not available";
  }

  return `${(mean / windowDays).toFixed(1)} / day`;
}

export function formatObservationLabel(current: number, minimum: number) {
  return `${current} of ${minimum} observations collected`;
}
