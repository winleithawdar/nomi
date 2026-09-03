"use client";

import { useEffect, useRef } from "react";
import { useInView, useMotionValue, useSpring } from "motion/react";

import { cn } from "@/lib/utils";

function prefersReducedMotion() {
  if (typeof window === "undefined") return false;
  return window.matchMedia("(prefers-reduced-motion: reduce)").matches;
}

export function NumberTicker({
  value,
  className,
  delay = 0,
  decimalPlaces = 0,
}: {
  value: number;
  className?: string;
  delay?: number;
  decimalPlaces?: number;
}) {
  const ref = useRef<HTMLSpanElement>(null);
  const motionValue = useMotionValue(value);
  const springValue = useSpring(motionValue, {
    damping: 60,
    stiffness: 90,
  });
  const isInView = useInView(ref, { once: true, margin: "0px" });

  useEffect(() => {
    const formatted = Intl.NumberFormat("en-US", {
      minimumFractionDigits: decimalPlaces,
      maximumFractionDigits: decimalPlaces,
    }).format(value);

    if (prefersReducedMotion()) {
      if (ref.current) ref.current.textContent = formatted;
      return;
    }

    if (!isInView) return;

    const timeout = window.setTimeout(() => {
      motionValue.set(value);
    }, delay);

    return () => window.clearTimeout(timeout);
  }, [delay, decimalPlaces, isInView, motionValue, value]);

  useEffect(() => {
    const unsubscribe = springValue.on("change", (latest) => {
      if (!ref.current) return;
      ref.current.textContent = Intl.NumberFormat("en-US", {
        minimumFractionDigits: decimalPlaces,
        maximumFractionDigits: decimalPlaces,
      }).format(Number(latest.toFixed(decimalPlaces)));
    });

    return unsubscribe;
  }, [decimalPlaces, springValue]);

  return (
    <span
      ref={ref}
      className={cn("inline-block tabular-nums tracking-tight", className)}
    >
      {Intl.NumberFormat("en-US", {
        minimumFractionDigits: decimalPlaces,
        maximumFractionDigits: decimalPlaces,
      }).format(value)}
    </span>
  );
}
