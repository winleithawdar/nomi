import type {
  BaselineStatus,
  CaregiverAlert,
  DetectionResponse,
  LatestSessionResponse,
  LiveCheckInResponse,
  SeniorDetailResponse,
  SeniorSchedule,
  SeniorSummary,
  SessionAssessment,
} from "./seniors";

export type {
  BaselineStatus,
  CaregiverAlert,
  DetectionResponse,
  LatestSessionResponse,
  LiveCheckInResponse,
  SeniorSchedule,
  SeniorSummary,
  SessionAssessment,
};
export type SeniorProfile = SeniorDetailResponse["senior"];
export type SeniorBaseline = SeniorDetailResponse["baseline"];
export type BaselineObservation = SeniorDetailResponse["recent_observations"][number];
export type ResponseLatencyPoint = SeniorDetailResponse["response_latency_series"][number];
