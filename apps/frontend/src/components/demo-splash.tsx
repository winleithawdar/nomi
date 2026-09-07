"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { HeartHandshake } from "lucide-react";

import { Button } from "@/components/ui/button";

const LOAD_MS = 1_800;

export function DemoSplash() {
  const router = useRouter();
  const [ready, setReady] = useState(false);
  const [entering, setEntering] = useState(false);

  useEffect(() => {
    const timer = window.setTimeout(() => setReady(true), LOAD_MS);
    return () => window.clearTimeout(timer);
  }, []);

  function onEnter() {
    setEntering(true);
    router.push("/dashboard");
  }

  return (
    <div className="relative flex min-h-dvh flex-col items-center justify-center overflow-hidden px-6">
      <div
        aria-hidden
        className="pointer-events-none absolute inset-0 bg-[linear-gradient(165deg,#0f2a22_0%,#173a2e_42%,#1f4a3c_100%)]"
      />
      <div
        aria-hidden
        className="pointer-events-none absolute inset-0 bg-[radial-gradient(ellipse_80%_60%_at_50%_28%,rgba(95,143,118,0.28),transparent_55%)]"
      />
      <div
        aria-hidden
        className="pointer-events-none absolute inset-0 opacity-[0.07] [background-image:radial-gradient(circle_at_1px_1px,rgba(255,255,255,0.9)_1px,transparent_0)] [background-size:22px_22px]"
      />

      <div className="relative z-10 flex w-full max-w-sm flex-col items-center text-center">
        <div
          className={`mb-8 flex h-16 w-16 items-center justify-center rounded-3xl bg-white/12 text-white shadow-[0_12px_40px_rgba(0,0,0,0.25)] backdrop-blur-sm transition-all duration-700 ${
            ready ? "scale-100 opacity-100" : "scale-95 opacity-90"
          }`}
        >
          <HeartHandshake className="h-8 w-8" aria-hidden />
        </div>

        <p className="font-[family-name:var(--font-heading)] text-5xl font-semibold tracking-tight text-white sm:text-6xl">
          Nomi
        </p>
        <p className="mt-3 max-w-[16rem] text-sm leading-6 text-white/70">
          Check-ins that follow each person&apos;s own usual pattern.
        </p>

        {!ready ? (
          <div className="mt-12 flex flex-col items-center gap-3" aria-live="polite">
            <div
              className="h-1 w-28 overflow-hidden rounded-full bg-white/15"
              role="progressbar"
              aria-label="Loading"
            >
              <div className="nomi-splash-bar h-full w-1/2 rounded-full bg-white/80" />
            </div>
            <p className="text-xs tracking-wide text-white/55">Getting ready…</p>
          </div>
        ) : (
          <div className="nomi-splash-fade mt-12 w-full">
            <Button
              type="button"
              size="lg"
              className="min-h-12 w-full rounded-2xl bg-white text-[#173a2e] hover:bg-white/92"
              onClick={onEnter}
              disabled={entering}
            >
              {entering ? "Opening…" : "Enter"}
            </Button>
            <p className="mt-3 text-xs text-white/50">Sarah&apos;s caregiver view</p>
          </div>
        )}
      </div>
    </div>
  );
}
