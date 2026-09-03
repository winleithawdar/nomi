import { cn } from "@/lib/utils";

export function AttentionCard({
  children,
  className,
}: {
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <div
      className={cn(
        "relative overflow-hidden rounded-3xl p-px",
        "bg-[radial-gradient(120%_90%_at_0%_0%,color-mix(in_oklab,var(--primary)_70%,white),transparent_52%),radial-gradient(90%_80%_at_100%_100%,color-mix(in_oklab,var(--ring)_55%,white),transparent_48%),var(--primary)]",
        className,
      )}
    >
      <div className="relative rounded-[calc(1.5rem-1px)] bg-[var(--card)]">{children}</div>
    </div>
  );
}
