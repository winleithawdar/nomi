"use client";

import { useEffect, useRef, useState } from "react";

const items = [
  { id: "section-live", label: "Check-in" },
  { id: "section-this-checkin", label: "This check-in" },
  { id: "section-update", label: "Update" },
  { id: "section-overview", label: "Overview" },
  { id: "section-charts", label: "Charts" },
  { id: "section-history", label: "History" },
] as const;

/** Distance from viewport top where a section counts as “active” (main header + this nav). */
const ACTIVE_OFFSET_PX = 120;
const CLICK_LOCK_MS = 900;

export function SeniorSectionNav() {
  const [activeId, setActiveId] = useState<string>(items[0].id);
  const lockUntilRef = useRef(0);

  useEffect(() => {
    function syncActiveFromScroll() {
      if (Date.now() < lockUntilRef.current) return;

      let current: string = items[0].id;
      for (const item of items) {
        const el = document.getElementById(item.id);
        if (!el) continue;
        if (el.getBoundingClientRect().top <= ACTIVE_OFFSET_PX) {
          current = item.id;
        }
      }
      setActiveId((prev) => (prev === current ? prev : current));
    }

    syncActiveFromScroll();
    window.addEventListener("scroll", syncActiveFromScroll, { passive: true });
    return () => window.removeEventListener("scroll", syncActiveFromScroll);
  }, []);

  function scrollToSection(id: string) {
    const el = document.getElementById(id);
    if (!el) return;

    lockUntilRef.current = Date.now() + CLICK_LOCK_MS;
    setActiveId(id);
    el.scrollIntoView({ behavior: "smooth", block: "start" });
  }

  return (
    <nav
      aria-label="Page sections"
      className="sticky top-[57px] z-20 -mx-4 border-b border-[var(--border)] bg-[var(--background)]/95 px-4 backdrop-blur-md md:-mx-6 md:px-6"
    >
      <div className="flex gap-2 overflow-x-auto py-2 [scrollbar-width:none] [-ms-overflow-style:none] [&::-webkit-scrollbar]:hidden">
        {items.map((item) => {
          const isActive = activeId === item.id;
          return (
            <button
              key={item.id}
              type="button"
              onClick={() => scrollToSection(item.id)}
              className={[
                "shrink-0 whitespace-nowrap rounded-full px-3 py-1.5 text-xs font-medium transition-colors",
                isActive
                  ? "bg-[var(--primary)] text-[var(--primary-foreground)]"
                  : "bg-[var(--muted)] text-[var(--muted-foreground)]",
              ].join(" ")}
              aria-current={isActive ? "true" : undefined}
            >
              {item.label}
            </button>
          );
        })}
      </div>
    </nav>
  );
}
