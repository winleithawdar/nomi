export function ErrorState({
  title,
  description,
}: {
  title: string;
  description: string;
}) {
  return (
    <div className="rounded-3xl border border-[var(--border)] bg-white p-8">
      <h2 className="text-xl font-semibold">{title}</h2>
      <p className="mt-3 text-sm leading-6 text-[var(--muted-foreground)]">{description}</p>
    </div>
  );
}
