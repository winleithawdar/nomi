import { apiGet } from "@/lib/api/client";
import type { SeniorDetailResponse, SeniorsListResponse } from "@/lib/api/types";

export function getSeniors() {
  return apiGet<SeniorsListResponse>("/api/v1/seniors");
}

export function getSeniorDetail(seniorId: string) {
  return apiGet<SeniorDetailResponse>(`/api/v1/seniors/${encodeURIComponent(seniorId)}`);
}
