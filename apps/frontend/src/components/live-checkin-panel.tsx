"use client";

import { useEffect, useState } from "react";
import { MessageCircleHeart, ShieldCheck } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { ApiError } from "@/lib/api/client";
import {
  getLiveCheckin,
  sendCheckIn,
  startSeniorVerification,
  type DetectionResponse,
  type LiveCheckInResponse,
} from "@/lib/api/seniors";
import { formatCompactDateTime } from "@/lib/format";

const POLL_INTERVAL_MS = 3_000;
const POLL_DURATION_MS = 120_000;

function hasOpenCheckin(open: LiveCheckInResponse["open_checkin"]): boolean {
  return open != null;
}

function wellbeingLabel(score: number | null | undefined): string | null {
  if (score === null || score === undefined || Number.isNaN(score)) return null;
  const rounded = Math.round(score);
  if (rounded < 1 || rounded > 5) return null;
  return String(rounded);
}

export function LiveCheckinPanel({
  seniorId,
  seniorName,
  detected,
  detection,
  initialLive,
}: {
  seniorId: string;
  seniorName: string;
  detected: boolean;
  detection: DetectionResponse;
  initialLive: LiveCheckInResponse | null;
}) {
  const [live, setLive] = useState<LiveCheckInResponse | null>(initialLive);
  const [polling, setPolling] = useState(false);
  const [sentCheckinId, setSentCheckinId] = useState<string | null>(null);
  const [sending, setSending] = useState(false);
  const [confirming, setConfirming] = useState(false);
  const [confirmed, setConfirmed] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!polling) return;

    const startedAt = Date.now();
    let cancelled = false;

    const tick = async () => {
      try {
        const next = await getLiveCheckin(seniorId);
        if (cancelled) return;
        if (next) {
          setLive(next);
          const open = next.open_checkin;
          const target =
            next.latest?.id === sentCheckinId
              ? next.latest
              : open?.id === sentCheckinId
                ? open
                : null;
          if (target?.status === "responded") {
            setPolling(false);
            return;
          }
        }
      } catch {
        // Keep polling; a missing live-checkin route still allows Send check-in.
      }
      if (Date.now() - startedAt >= POLL_DURATION_MS) {
        setPolling(false);
      }
    };

    void tick();
    const interval = window.setInterval(() => {
      void tick();
    }, POLL_INTERVAL_MS);
    const timeout = window.setTimeout(() => setPolling(false), POLL_DURATION_MS);

    return () => {
      cancelled = true;
      window.clearInterval(interval);
      window.clearTimeout(timeout);
    };
  }, [polling, seniorId, sentCheckinId]);

  async function onSendCheckIn() {
    setError(null);
    setSending(true);
    try {
      const sent = await sendCheckIn(seniorId);
      setSentCheckinId(sent.id);
      setLive((current) => ({
        senior_id: seniorId,
        contact_configured: current?.contact_configured ?? true,
        open_checkin: {
          id: sent.id,
          status: sent.status === "responded" ? "responded" : "sent",
          sent_at: sent.sent_at,
        },
        latest: current?.latest ?? {
          id: sent.id,
          status: "sent",
          sent_at: sent.sent_at,
          response_received_at: null,
          wellbeing_score: null,
        },
      }));
      setPolling(true);
    } catch (cause) {
      setError(
        cause instanceof ApiError
          ? cause.message
          : "Could not send a check-in. Try again.",
      );
    } finally {
      setSending(false);
    }
  }

  async function onAskToConfirm() {
    setError(null);
    setConfirming(true);
    try {
      await startSeniorVerification(seniorId, seniorName, detection);
      setConfirmed(true);
    } catch (cause) {
      setError(
        cause instanceof ApiError
          ? cause.message
          : "Could not send a confirmation check-in. Try again.",
      );
    } finally {
      setConfirming(false);
    }
  }

  const waiting = polling || hasOpenCheckin(live?.open_checkin ?? null);
  const latest = live?.latest;
  const wellbeing = wellbeingLabel(latest?.wellbeing_score ?? null);
  const repliedAt = latest?.response_received_at ?? null;
  const notLinked = live !== null && live.contact_configured === false;

  let statusTitle = "No live check-in yet";
  let statusDetail = `${seniorName}'s replies stay personal — this is a check-in, not a diagnosis.`;

  if (notLinked && !waiting) {
    statusTitle = "Not linked";
    statusDetail = `${seniorName} is not linked to Telegram yet. You can still try sending a check-in.`;
  } else if (waiting) {
    statusTitle = "Waiting for a Telegram reply";
    statusDetail = "When they reply, you will see wellbeing as 1–5 — never the raw message.";
  } else if (latest?.status === "responded") {
    statusTitle = repliedAt
      ? `Last reply ${formatCompactDateTime(repliedAt)}`
      : "Last reply received";
    statusDetail = wellbeing
      ? `${seniorName} reported wellbeing ${wellbeing} of 5.`
      : "They replied. Wellbeing was not captured as 1–5.";
  } else if (latest?.status === "missed") {
    statusTitle = "Last check-in was missed";
    statusDetail = "You can send another personal check-in when you are ready.";
  }

  return (
    <Card>
      <CardContent className="space-y-5 p-5 sm:p-6">
        <div className="space-y-2">
          <p className="text-sm font-medium text-[var(--primary)]">Live check-in</p>
          <h2 className="text-xl font-semibold">Check in with {seniorName}</h2>
          <p className="text-sm leading-6 text-[var(--muted-foreground)]">
            A personal check-in, not a diagnosis. Nomi only shows a wellbeing score from 1 to 5.
          </p>
        </div>

        <div
          className="rounded-2xl bg-[var(--muted)] px-4 py-3"
          aria-live="polite"
          aria-atomic="true"
        >
          <p className="font-semibold">{statusTitle}</p>
          <p className="mt-1 text-sm leading-6 text-[var(--muted-foreground)]">{statusDetail}</p>
          {latest?.status === "responded" && wellbeing ? (
            <p className="mt-3 text-3xl font-semibold tabular-nums tracking-tight">
              {wellbeing}
              <span className="ml-1 text-base font-medium text-[var(--muted-foreground)]">/ 5</span>
            </p>
          ) : null}
        </div>

        {error ? (
          <p className="text-sm text-[var(--secondary-foreground)]" role="alert">
            {error}
          </p>
        ) : null}

        <div className="flex flex-col gap-2">
          <Button
            type="button"
            size="lg"
            className="min-h-11 w-full"
            onClick={() => void onSendCheckIn()}
            disabled={sending}
          >
            <MessageCircleHeart className="h-4 w-4" aria-hidden />
            {sending ? "Sending…" : "Send Nomi check-in"}
          </Button>

          {detected ? (
            <Button
              type="button"
              variant="outline"
              size="lg"
              className="min-h-11 w-full"
              onClick={() => void onAskToConfirm()}
              disabled={confirming || confirmed}
            >
              <ShieldCheck className="h-4 w-4" aria-hidden />
              {confirmed
                ? "Asked them to confirm"
                : confirming
                  ? "Sending…"
                  : "Ask them to confirm"}
            </Button>
          ) : null}
        </div>
      </CardContent>
    </Card>
  );
}
