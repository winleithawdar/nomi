export type SeniorStatus = "stable" | "monitoring" | "attention";

export type Senior = {
  id: string;
  name: string;
  age: number;
  initials: string;
  status: SeniorStatus;
  baselineConfidence: number;
  observationDays: number;
  activity: {
    current: number;
    baseline: number;
    deviation: number;
  };
  sleep: {
    current: number;
    baseline: number;
    deviation: number;
  };
  responseLatency: {
    current: number;
    baseline: number;
    deviation: number;
  };
  latestChange?: {
    metric: string;
    title: string;
    description: string;
    severity: "low" | "medium" | "high";
    detectedAt: string;
  };
};

const seniors: Senior[] = [
  {
    id: "1",
    name: "Mary Tan",
    age: 78,
    initials: "MT",
    status: "attention",
    baselineConfidence: 91,
    observationDays: 28,
    activity: {
      current: 3.1,
      baseline: 4.4,
      deviation: -30,
    },
    sleep: {
      current: 7.2,
      baseline: 7.4,
      deviation: -3,
    },
    responseLatency: {
      current: 8.4,
      baseline: 6.2,
      deviation: 35,
    },
    latestChange: {
      metric: "Activity",
      title: "Activity is below Mary's usual pattern",
      description:
        "Activity has remained significantly below her personal baseline for the past 2 days.",
      severity: "high",
      detectedAt: "2 hours ago",
    },
  },
  {
    id: "2",
    name: "Robert Lim",
    age: 82,
    initials: "RL",
    status: "monitoring",
    baselineConfidence: 84,
    observationDays: 21,
    activity: {
      current: 3.9,
      baseline: 4.1,
      deviation: -5,
    },
    sleep: {
      current: 6.1,
      baseline: 7.0,
      deviation: -13,
    },
    responseLatency: {
      current: 6.8,
      baseline: 6.5,
      deviation: 5,
    },
    latestChange: {
      metric: "Sleep",
      title: "Sleep duration has shifted",
      description:
        "Robert has been sleeping slightly less than his recent personal baseline.",
      severity: "medium",
      detectedAt: "5 hours ago",
    },
  },
  {
    id: "3",
    name: "Amy Lee",
    age: 75,
    initials: "AL",
    status: "stable",
    baselineConfidence: 96,
    observationDays: 35,
    activity: {
      current: 4.7,
      baseline: 4.6,
      deviation: 2,
    },
    sleep: {
      current: 7.3,
      baseline: 7.2,
      deviation: 1,
    },
    responseLatency: {
      current: 6.1,
      baseline: 6.3,
      deviation: -3,
    },
  },
  {
    id: "4",
    name: "David Wong",
    age: 80,
    initials: "DW",
    status: "stable",
    baselineConfidence: 89,
    observationDays: 24,
    activity: {
      current: 4.2,
      baseline: 4.1,
      deviation: 2,
    },
    sleep: {
      current: 7.0,
      baseline: 7.1,
      deviation: -1,
    },
    responseLatency: {
      current: 6.4,
      baseline: 6.6,
      deviation: -3,
    },
  },
];

export async function getSeniors() {
  return {
    summary: {
      seniors_monitored: seniors.length,
      seniors_learning: seniors.filter(
        (senior) => senior.observationDays < 21
      ).length,
      baselines_established: seniors.filter(
        (senior) => senior.observationDays >= 21
      ).length,
      recent_checkins: 37,
      detected_changes: seniors.filter((senior) => senior.latestChange).length,
      needs_attention: seniors.filter(
        (senior) =>
          senior.status === "attention" || senior.status === "monitoring"
      ).length,
    },
    seniors,
  };
}

export async function getSenior(id: string) {
  return seniors.find((senior) => senior.id === id) ?? null;
}
