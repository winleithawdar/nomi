import { Skeleton } from "@/components/ui/skeleton";

export default function SeniorsLoading() {
  return (
    <div className="space-y-8">
      <div className="space-y-3">
        <Skeleton className="h-5 w-32" />
        <Skeleton className="h-10 w-56" />
      </div>
      <div className="grid gap-5 lg:grid-cols-2">
        {Array.from({ length: 4 }).map((_, index) => (
          <Skeleton key={index} className="h-60 rounded-3xl" />
        ))}
      </div>
    </div>
  );
}
