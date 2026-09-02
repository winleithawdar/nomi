import type {
  BaselineStatus,
  SeniorDetailResponse,
  SeniorSummary,
} from "./seniors";

export type { BaselineStatus, SeniorSummary };
export type SeniorProfile = SeniorDetailResponse["senior"];
export type SeniorBaseline = SeniorDetailResponse["baseline"];
export type BaselineObservation = SeniorDetailResponse["recent_observations"][number];
export type ResponseLatencyPoint = SeniorDetailResponse["response_latency_series"][number];
