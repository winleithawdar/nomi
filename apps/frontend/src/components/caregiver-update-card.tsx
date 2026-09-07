"use client";

import { useEffect, useRef, useState } from "react";

import { Card, CardContent } from "@/components/ui/card";
import { Separator } from "@/components/ui/separator";
import { getLatestSession } from "@/lib/api/seniors";
import {
  LANDING_UPDATE_SCENARIO,
  LIVE_NEEDS_YOU_NOW_UPDATE,
  type DemoScenarioUi,
} from "@/lib/demo-scenarios";

const POLL_INTERVAL_MS = 3_000;
const POLL_DURATION_MS = 180_000;

function parseClosedAtMs(closedAt: string): number {
  const hasTimezone = /(?:Z|[+-]\d{2}:?\d{2})$/i.test(closedAt);
  return Date.parse(hasTimezone ? closedAt : `${closedAt}Z`);
}

export function CaregiverUpdateCard({
  seniorId,
  pinnedScenario,
  liveFocus = false,
}: {
  seniorId: string;
  pinnedScenario: DemoScenarioUi | null;
  liveFocus?: boolean;
}) {
  const [liveNeedsYouNow, setLiveNeedsYouNow] = useState(false);
  const pageOpenedAtRef = useRef<number | null>(null);

  useEffect(() => {
    if (liveFocus) {
      let cancelled = false;
      void (async () => {
        try {
          const latest = await getLatestSession(seniorId);
          if (cancelled) return;
          if (latest?.session?.label === "needs_you_now") {
            setLiveNeedsYouNow(true);
          }
        } catch {
          // Keep showing the landing update if fetch fails.
        }
      })();
      return () => {
        cancelled = true;
      };
    }

    if (pinnedScenario) return;
    if (pageOpenedAtRef.current === null) {
      pageOpenedAtRef.current = Date.now();
    }
    const pageOpenedAt = pageOpenedAtRef.current;
    const startedAt = Date.now();
    let cancelled = false;

    const tick = async () => {
      try {
        const latest = await getLatestSession(seniorId);
        if (cancelled) return;
        const session = latest?.session;
        const closedAt = session?.closed_at;
        if (
          closedAt &&
          parseClosedAtMs(closedAt) >= pageOpenedAt &&
          session.label === "needs_you_now"
        ) {
          setLiveNeedsYouNow(true);
        }
      } catch {
        // Keep showing the landing update if a poll fails.
      }
    };

    const interval = window.setInterval(() => {
      if (Date.now() - startedAt >= POLL_DURATION_MS) {
        window.clearInterval(interval);
        return;
      }
      void tick();
    }, POLL_INTERVAL_MS);

    return () => {
      cancelled = true;
      window.clearInterval(interval);
    };
  }, [seniorId, pinnedScenario, liveFocus]);

  const scenario =
    pinnedScenario ?? (liveNeedsYouNow ? LIVE_NEEDS_YOU_NOW_UPDATE : LANDING_UPDATE_SCENARIO);

  return (
    <Card>
      <CardContent className="space-y-5 p-5 sm:p-6">
        <div className="space-y-2">
          <p className="text-sm font-medium text-[var(--primary)]">Recent update</p>
          <h2 className="text-xl font-semibold">{scenario.recentUpdateTitle}</h2>
          <p className="text-sm leading-6 text-[var(--muted-foreground)]">
            {scenario.recentUpdateSummary}
          </p>
          <p className="text-xs capitalize text-[var(--muted-foreground)]">
            {scenario.recentUpdateConfidence}
          </p>
        </div>
        <Separator />
        <div className="space-y-2">
          <p className="text-sm font-medium text-[var(--primary)]">Following up</p>
          <h2 className="text-xl font-semibold">{scenario.followingUpTitle}</h2>
          <p className="text-sm leading-6 text-[var(--muted-foreground)]">
            {scenario.followingUpMessage}
          </p>
          {scenario.followingUpSuggestedStep ? (
            <p className="text-sm">
              <span className="font-medium">Suggested next step:</span>{" "}
              {scenario.followingUpSuggestedStep}
            </p>
          ) : null}
        </div>
      </CardContent>
    </Card>
  );
}
