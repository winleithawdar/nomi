export type BaselineStatus = "learning" | "stable";
export type SignalStatus = "learning" | "stable" | "unavailable";
export type NoticeStatus = "learning" | "usual" | "watching" | "changed";

export interface SeniorSummary {
  id: string;
  name: string;
  relationship: string;
  age_band: string;
  baseline_status: BaselineStatus;
  observation_count: number;
  latest_interaction_at: string | null;
  status_text: string;
  notice: NoticeAssessment;
}

export interface SeniorProfile {
  id: string;
  name: string;
  relationship: string;
  age_band: string;
}

export interface NumericSignalBaseline {
  status: SignalStatus;
  observation_count: number;
  latest_value: number | null;
  mean: number | null;
  median: number | null;
  stddev: number | null;
  latest_deviation_from_mean: number | null;
}

export interface BinarySignalBaseline {
  status: SignalStatus;
  observation_count: number;
  positive_count: number;
  rate: number | null;
  latest_value: number | null;
}

export interface SeniorBaseline {
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
    numeric_window_size: number;
    binary_window_size: number;
    frequency_window_days: number;
  };
}

export interface BaselineObservation {
  occurred_at: string;
  response_latency_minutes: number | null;
  missed_checkin: boolean;
  interaction_frequency: number;
  wellbeing_score: number | null;
}

export interface ResponseLatencyPoint {
  occurred_at: string;
  response_latency_minutes: number;
  rolling_mean_minutes: number;
}

export interface NoticeFinding {
  signal: string;
  level: Exclude<NoticeStatus, "learning" | "usual">;
  explanation: string;
}

export interface NoticeAssessment {
  status: NoticeStatus;
  headline: string;
  findings: NoticeFinding[];
}

export interface SeniorsListResponse {
  summary: {
    seniors_monitored: number;
    seniors_learning: number;
    baselines_established: number;
    recent_checkins: number;
    changes_from_usual: number;
  };
  seniors: SeniorSummary[];
}

export interface SeniorDetailResponse {
  senior: SeniorProfile;
  baseline: SeniorBaseline;
  notice: NoticeAssessment;
  recent_observations: BaselineObservation[];
  response_latency_series: ResponseLatencyPoint[];
}
