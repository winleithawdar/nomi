import { Badge } from "@/components/ui/badge";
import type { BaselineStatus } from "@/lib/api/types";

export function StatusBadge({ status }: { status: BaselineStatus }) {
  return <Badge variant={status === "stable" ? "stable" : "learning"}>{status === "stable" ? "Established" : "Learning"}</Badge>;
}
