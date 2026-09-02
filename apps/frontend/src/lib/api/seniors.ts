import { apiGet } from "./client";

export type BaselineStatus = "learning" | "stable";

export interface SeniorSummary {
  id: string;
  name: string;
  relationship: string;
  age_band: string;
  baseline_status: BaselineStatus;
  observation_count: number;
  latest_interaction_at: string | null;
  status_text: string;
}

export interface SeniorsResponse {
  summary: {
    seniors_monitored: number;
    seniors_learning: number;
    baselines_established: number;
    recent_checkins: number;
  };
  seniors: SeniorSummary[];
}

interface NumericSignalBaseline {
  status: "learning" | "stable" | "unavailable";
  observation_count: number;
  latest_value: number | null;
  mean: number | null;
  median: number | null;
  stddev: number | null;
  latest_deviation_from_mean: number | null;
}

interface BinarySignalBaseline {
  status: "learning" | "stable" | "unavailable";
  observation_count: number;
  positive_count: number;
  rate: number | null;
  latest_value: number | null;
}

export interface SeniorDetailResponse {
  senior: Pick<SeniorSummary, "id" | "name" | "relationship" | "age_band">;
  baseline: {
    senior_id: string;
    as_of: string | null;
    status: BaselineStatus;
    min_observations_for_stable: number;
    total_interactions: number;
    response_latency_minutes: NumericSignalBaseline;
    missed_checkin_rate: BinarySignalBaseline;
    interaction_frequency: NumericSignalBaseline;
    wellbeing_score: NumericSignalBaseline;
    metadata: {
      frequency_window_days: number;
      [key: string]: unknown;
    };
  };
  recent_observations: Array<{
    occurred_at: string;
    response_latency_minutes: number | null;
    missed_checkin: boolean;
    interaction_frequency: number;
    wellbeing_score: number | null;
  }>;
  response_latency_series: Array<{
    occurred_at: string;
    response_latency_minutes: number;
    rolling_mean_minutes: number;
  }>;
}

export interface DetectionResponse {
  senior_id: string;
  kind: "anomaly" | "sustained_change";
  detected: boolean;
  status: "ok" | "insufficient_history";
  confidence: "low" | "moderate" | "high";
  direction: "rising" | "falling" | "none";
  summary: string;
  as_of: string | null;
}

export interface CaregiverAlert {
  id: string;
  senior_id: string;
  verification_request_id: string;
  what_changed: string;
  context: string;
  verification_outcome: string;
  suggested_action: string;
  detection_summary: string;
  status: "pending" | "delivered";
  created_at: string;
  delivered_at: string | null;
}

export interface VerificationStatusResponse {
  senior_id: string;
  active_verification: {
    id: string;
    status: string;
    check_in_message: string;
    created_at: string;
  } | null;
  latest_alert: CaregiverAlert | null;
}

export function getSeniors(): Promise<SeniorsResponse> {
  return apiGet("/api/v1/seniors");
}

export function getSeniorDetail(seniorId: string): Promise<SeniorDetailResponse> {
  return apiGet(`/api/v1/seniors/${encodeURIComponent(seniorId)}`);
}

export function getLatestAnomaly(seniorId: string): Promise<DetectionResponse> {
  return apiGet(`/api/v1/seniors/${encodeURIComponent(seniorId)}/detections/anomaly`);
}

export function getVerificationStatus(seniorId: string): Promise<VerificationStatusResponse> {
  return apiGet(`/api/v1/seniors/${encodeURIComponent(seniorId)}/verification-status`);
}

export async function getAlerts(): Promise<CaregiverAlert[]> {
  const data = await apiGet<{ alerts: CaregiverAlert[] }>("/api/v1/alerts?limit=10");
  return data.alerts;
}
