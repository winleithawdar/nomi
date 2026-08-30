import type { Route } from "next";
import Link from "next/link";
import { HeartHandshake, LayoutDashboard, Users } from "lucide-react";

import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import { cn } from "@/lib/utils";

const navItems = [
  { href: "/dashboard", label: "Overview", icon: LayoutDashboard },
  { href: "/seniors", label: "Seniors", icon: Users },
] as const satisfies ReadonlyArray<{
  href: Route;
  label: string;
  icon: typeof LayoutDashboard;
}>;

export function AppShell({
  children,
  currentPath,
}: {
  children: React.ReactNode;
  currentPath: string;
}) {
  return (
    <div className="min-h-screen bg-[var(--background)] text-[var(--foreground)]">
      <div className="mx-auto grid min-h-screen max-w-7xl grid-cols-1 lg:grid-cols-[248px_minmax(0,1fr)]">
        <aside className="border-b border-[var(--border)] bg-[var(--sidebar)] px-5 py-6 lg:border-b-0 lg:border-r">
          <div className="flex items-center gap-3">
            <div className="flex h-11 w-11 items-center justify-center rounded-2xl bg-[var(--primary)] text-[var(--primary-foreground)]">
              <HeartHandshake className="h-5 w-5" />
            </div>
            <div>
              <p className="font-semibold tracking-tight">Nomi</p>
              <p className="text-sm text-[var(--muted-foreground)]">Caregiver dashboard</p>
            </div>
          </div>

          <nav className="mt-8 flex flex-wrap gap-2 lg:flex-col" aria-label="Primary navigation">
            {navItems.map((item) => {
              const isActive = currentPath === item.href || currentPath.startsWith(`${item.href}/`);
              const Icon = item.icon;

              return (
                <Link
                  key={item.href}
                  href={item.href}
                  className={cn(
                    "inline-flex items-center gap-3 rounded-2xl px-4 py-3 text-sm font-medium transition-colors",
                    isActive
                      ? "bg-white text-[var(--foreground)] shadow-sm ring-1 ring-[var(--border)]"
                      : "text-[var(--muted-foreground)] hover:bg-white/70 hover:text-[var(--foreground)]",
                  )}
                >
                  <Icon className="h-4 w-4" />
                  <span>{item.label}</span>
                </Link>
              );
            })}
          </nav>

          <div className="mt-8 rounded-3xl border border-[var(--border)] bg-white p-4">
            <p className="text-sm font-medium">Baseline-first support</p>
            <p className="mt-2 break-words text-sm leading-6 text-[var(--muted-foreground)]">
              Nomi learns each senior&apos;s own recent interaction pattern before surfacing changes from usual.
            </p>
          </div>
        </aside>

        <div className="flex min-h-screen flex-col">
          <header className="flex items-center justify-between border-b border-[var(--border)] bg-[var(--background)] px-5 py-4 sm:px-8">
            <div>
              <p className="text-sm text-[var(--muted-foreground)]">Personal normal, not population normal</p>
            </div>
            <div className="flex items-center gap-3">
              <div className="hidden text-right sm:block">
                <p className="text-sm font-medium">Caregiver</p>
                <p className="text-sm text-[var(--muted-foreground)]">Family account</p>
              </div>
              <Avatar>
                <AvatarFallback>CG</AvatarFallback>
              </Avatar>
            </div>
          </header>

          <main className="flex-1 px-5 py-6 sm:px-8 sm:py-8">{children}</main>
        </div>
      </div>
    </div>
  );
}
