import { Skeleton } from "@/components/ui/skeleton";

export function LoadingGrid() {
  return (
    <div className="grid gap-5 md:grid-cols-2 xl:grid-cols-4">
      {Array.from({ length: 4 }).map((_, index) => (
        <Skeleton key={index} className="h-36 rounded-3xl" />
      ))}
    </div>
  );
}
