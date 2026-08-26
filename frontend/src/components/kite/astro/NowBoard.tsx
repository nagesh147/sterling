import type { SlotGrade } from "../../../lib/astro/tape";
import { formatIstDate, getIstParts, minutesOfDay, utcFromIstParts } from "../../../lib/astro/time";
import type { LiveNow, WindowSlot } from "../../../lib/astro/types";
import { actionTone, gapTone } from "./palette";

const THESIS: Record<LiveNow["thesis"], string> = {
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
  if (m > 0) return `${m}m ${pad(sec)}s`;
  return `${sec}s`;
}

function clockIst(now: Date): string {
  const p = getIstParts(now);
  const h12 = p.hour % 12 === 0 ? 12 : p.hour % 12;
  return `${h12}:${pad(p.minute)}:${pad(p.second)} ${p.hour < 12 ? "AM" : "PM"}`;
}

function kalamLine(k: LiveNow["kalam"]): string | null {
  if (k.rahu) return "Rahu Kalam";
  if (k.yamagandam) return "Yamagandam";
  if (k.gulika) return "Gulika";
  return null;
}

function phaseLabel(status: LiveNow, now: Date): string {
  if (status.phase === "live") return "LIVE";
  if (status.phase === "pre") return `OPENS IN ${fmtRemain(status.bellMs - now.getTime())}`;
  if (status.phase === "post") return "CASH CLOSED";
  return "MARKET CLOSED";
}

function sessionLabel(iso: string): string {
  const [y, m, d] = iso.split("-").map(Number);
  return formatIstDate(utcFromIstParts(y, m, d, 9, 0, 0));
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
  onOpenSession,
  onOpenWindow,
}: {
  status: LiveNow;
  now: Date;
  grade?: SlotGrade;
  viewingIso: string;
  onOpenSession: (iso: string) => void;
  onOpenWindow: (slot: WindowSlot) => void;
}) {
  const gtone = gapTone(status.gap.kind);
  const playTone = actionTone(status.play, status.side);
  const kalam = kalamLine(status.kalam);
  const horaLeft = fmtRemain(new Date(status.hora.endsAt).getTime() - now.getTime());
  const endMs = windowEndMs(status);
  const windowLeft = status.phase === "live" && endMs !== null ? fmtRemain(endMs - now.getTime()) : null;
  const p = getIstParts(now);
  const nowFrac = minutesOfDay(p.hour, p.minute) + p.second / 60;
  const progress =
    status.phase === "live" && status.window && status.window.toMin > status.window.fromMin
      ? Math.min(1, Math.max(0, (nowFrac - status.window.fromMin) / (status.window.toMin - status.window.fromMin)))
      : null;

  return (
    <div className="ko-now">
      <div className="ko-now-top">
        <span className="ko-now-phase" data-live={status.phase === "live"}>
          {phaseLabel(status, now)}
        </span>
        <span className="ko-now-clock">{clockIst(now)} IST</span>
      </div>

      <div className={`ko-now-play ${playTone}`}>
        {status.play}
        {status.phase === "live" && windowLeft ? (
          <span className="ko-now-sub">
            {" "}
            {windowLeft} left · {status.window?.from}–{status.window?.to}
          </span>
        ) : (
          <span className="ko-now-sub">
            {" "}
            {status.phase === "pre" ? "at 09:15 IST" : `next open ${sessionLabel(status.sessionIso)}`}
          </span>
        )}
      </div>

      <p className="ko-now-copy">
        <span className={gtone.fg}>{status.gap.label}</span>
        {" · "}
        {THESIS[status.thesis]}
        {status.regime ? ` · ${status.regime}` : ""}
        {grade && (grade.kind === "LIVE" || grade.kind === "HIT" || grade.kind === "MISS") && grade.delta !== null ? (
          <span className={grade.delta >= 0 ? "text-up" : "text-down"}>
            {" "}
            · tape {grade.delta >= 0 ? "+" : ""}
            {grade.delta.toFixed(0)}
          </span>
        ) : null}
      </p>
      <p className="ko-now-copy">{status.suggestion}</p>

      <div className="ko-now-meta">
        <span>
          {status.hora.lord} hora · {horaLeft} left
        </span>
        <span>
          Lagna {status.lagnaSign} {status.lagnaDegree.toFixed(1)}°
        </span>
        <span>
          {status.tithiName} {status.paksha} · {status.nakshatra}
        </span>
        <span>
          {status.yoga} · {status.choghadiya}
          {status.choghadiyaKind === "bad" ? " · sit" : ""}
        </span>
        {kalam ? <span className="text-down">{kalam}</span> : null}
        {status.next ? (
          <span>
            Next {status.next.from} {status.next.action}
          </span>
        ) : null}
      </div>

      {progress !== null ? (
        <div className="ko-now-bar" aria-hidden="true">
          <span style={{ width: `${Math.round(progress * 100)}%` }} />
        </div>
      ) : null}

      <div className="ko-now-actions">
        {status.window ? (
          <button type="button" className="ko-link" onClick={() => onOpenWindow(status.window as WindowSlot)}>
            Jump to this window
          </button>
        ) : (
          <button type="button" className="ko-link" onClick={() => onOpenSession(status.sessionIso)}>
            Open {sessionLabel(status.sessionIso)}
          </button>
        )}
        {viewingIso !== status.sessionIso ? (
          <span className="text-muted">Timings below are {sessionLabel(viewingIso)}</span>
        ) : null}
      </div>
    </div>
  );
}
