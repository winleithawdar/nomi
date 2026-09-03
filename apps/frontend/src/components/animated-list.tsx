"use client";

import { Children } from "react";
import { motion, useReducedMotion } from "motion/react";

import { cn } from "@/lib/utils";

export function AnimatedList({
  children,
  className,
}: {
  children: React.ReactNode;
  className?: string;
}) {
  const reduceMotion = useReducedMotion();
  const items = Children.toArray(children);

  return (
    <ul className={cn("space-y-3", className)}>
      {items.map((child, index) => (
        <motion.li
          key={index}
          initial={reduceMotion ? false : { opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{
            duration: reduceMotion ? 0 : 0.32,
            delay: reduceMotion ? 0 : index * 0.05,
            ease: "easeOut",
          }}
        >
          {child}
        </motion.li>
      ))}
    </ul>
  );
}
