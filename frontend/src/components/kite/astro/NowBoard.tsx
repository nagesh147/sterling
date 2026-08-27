import type { SlotGrade } from "../../../lib/astro/tape";
import { getIstParts, minutesOfDay, utcFromIstParts } from "../../../lib/astro/time";
import { WEEKDAYS, type DayThesis, type LiveNow, type WindowSlot } from "../../../lib/astro/types";
import { actionTone, gapTone } from "./palette";

const THESIS: Record<DayThesis, string> = {
  "trend-up": "Trend up",
  "trend-down": "Trend down",
  fade: "Fade",
  chop: "Chop",
};

function pad(n: number): string {
  return String(n).padStart(2, "0");
}

function fmtRemain(ms: number): string {
  if (ms < 0) ms = 0;
  const s = Math.floor(ms / 1000);
  const h = Math.floor(s / 3600);
  const m = Math.floor((s % 3600) / 60);
  const sec = s % 60;
  if (h > 0) return `${h}h ${m}m`;
  if (m >= 2) return `${m}m`;
  if (m > 0) return `${m}m ${pad(sec)}s`;
  return `${sec}s`;
}

function clockIst(now: Date): string {
  const p = getIstParts(now);
  const h12 = p.hour % 12 === 0 ? 12 : p.hour % 12;
  return `${h12}:${pad(p.minute)}:${pad(p.second)} ${p.hour < 12 ? "AM" : "PM"}`;
}

function kalamLine(k: LiveNow["kalam"]): string | null {
  if (k.rahu) return "Rahu";
  if (k.yamagandam) return "Yama";
  if (k.gulika) return "Gulika";
  return null;
}

const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

function sessionLabel(iso: string): string {
  const [y, m, d] = iso.split("-").map(Number);
  const p = getIstParts(utcFromIstParts(y, m, d, 9, 0, 0));
  return `${WEEKDAYS[p.weekday].slice(0, 3)}, ${p.day} ${MONTHS[p.month - 1]}`;
}

function windowEndMs(status: LiveNow): number | null {
  if (!status.window) return null;
  const [y, m, d] = status.iso.split("-").map(Number);
  return utcFromIstParts(y, m, d, Math.floor(status.window.toMin / 60), status.window.toMin % 60, 0).getTime();
}

export function NowBoard({
  status,
  now,
  grade,
  viewingIso,
  sessionPnl,
  onOpenSession,
  onOpenWindow,
}: {
  status: LiveNow;
  now: Date;
  grade?: SlotGrade;
  viewingIso: string;
  sessionPnl?: number | null;
  onOpenSession: (iso: string) => void;
  onOpenWindow: (slot: WindowSlot) => void;
}) {
  const gtone = gapTone(status.gap.kind);
  const playTone = actionTone(status.play, status.side);
  const kalam = kalamLine(status.kalam);
  const recap = status.phase === "post" || status.phase === "closed";
  const endMs = windowEndMs(status);
  const windowLeft = status.phase === "live" && endMs !== null ? fmtRemain(endMs - now.getTime()) : null;
  const p = getIstParts(now);
  const nowFrac = minutesOfDay(p.hour, p.minute) + p.second / 60;
  const progress =
    status.phase === "live" && status.window && status.window.toMin > status.window.fromMin
      ? Math.min(1, Math.max(0, (nowFrac - status.window.fromMin) / (status.window.toMin - status.window.fromMin)))
      : null;
  const wrongSession = viewingIso !== status.sessionIso;
  const showJump = Boolean(status.window) && wrongSession;
  const liveTape =
    grade && (grade.kind === "LIVE" || grade.kind === "HIT" || grade.kind === "MISS") && grade.delta !== null
      ? grade.delta
      : null;
  const tape = liveTape !== null ? liveTape : recap && sessionPnl != null ? sessionPnl : null;

  const kicker =
    status.phase === "live" ? "NOW" : status.phase === "pre" ? "OPENS" : status.phase === "post" ? "CLOSED" : "CLOSED";

  const play = recap
    ? `${status.gap.label} · ${THESIS[status.thesis]}`
    : status.play;

  const when =
    status.phase === "live" && windowLeft
      ? [`${windowLeft} left`, status.window ? `${status.window.from}–${status.window.to}` : null, kalam]
          .filter(Boolean)
          .join(" · ")
      : status.phase === "pre"
        ? "09:15 IST"
        : `Next ${sessionLabel(status.nextOpenIso)}`;

  const nextLine =
    status.phase === "live" && status.next && status.next.action !== status.play
      ? `Then ${status.next.action} at ${status.next.from}`
      : null;

  return (
    <div className="ko-now" data-live={status.phase === "live"} role="status">
      <div className="ko-now-top">
        <span className="ko-now-phase" data-live={status.phase === "live"}>
          {kicker}
        </span>
        <span className="ko-now-clock">
          {clockIst(now)} IST
          {tape !== null ? (
            <span className={tape >= 0 ? "text-up" : "text-down"}>
              {" "}
              {tape >= 0 ? "+" : ""}
              {tape.toFixed(0)}
            </span>
          ) : null}
        </span>
      </div>

      <div className={`ko-now-play ${recap ? gtone.fg : playTone}`}>{play}</div>
      <div className="ko-now-sub">{when}</div>

      {status.phase === "live" || status.phase === "pre" ? <p className="ko-now-copy">{status.suggestion}</p> : null}
      {nextLine ? <p className="ko-now-next">{nextLine}</p> : null}

      {progress !== null ? (
        <div className="ko-now-bar" aria-hidden="true">
          <span style={{ width: `${Math.round(progress * 100)}%` }} />
        </div>
      ) : null}

      {wrongSession || showJump ? (
        <div className="ko-now-actions">
          {showJump ? (
            <button type="button" className="ko-link" onClick={() => onOpenWindow(status.window as WindowSlot)}>
              This window
            </button>
          ) : null}
          {wrongSession ? (
            status.phase === "live" ? (
              <button type="button" className="ko-link" onClick={() => onOpenSession(status.sessionIso)}>
                Live session
              </button>
            ) : (
              <span className="text-muted">Showing {sessionLabel(viewingIso)}</span>
            )
          ) : null}
        </div>
      ) : null}
    </div>
  );
}
