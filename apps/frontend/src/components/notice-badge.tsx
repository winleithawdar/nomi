import { Badge } from "@/components/ui/badge";
import type { NoticeStatus } from "@/lib/api/types";

const copy: Record<NoticeStatus, string> = {
  learning: "Learning",
  usual: "In line with usual",
  watching: "Worth a look",
  changed: "Changed from usual",
};

const variant: Record<NoticeStatus, "learning" | "stable" | "watching" | "changed"> = {
  learning: "learning",
  usual: "stable",
  watching: "watching",
  changed: "changed",
};

export function NoticeBadge({ status }: { status: NoticeStatus }) {
  return <Badge variant={variant[status]}>{copy[status]}</Badge>;
}
