import type { SlotGrade } from "../../../lib/astro/tape";
import { formatIstDate, getIstParts, minutesOfDay, utcFromIstParts } from "../../../lib/astro/time";
import type { IndexPlay, LiveNow, WindowSlot } from "../../../lib/astro/types";
import { actionTone, gapTone, REGIME_SHORT, regimeTone } from "./palette";

const SHORT: Record<IndexPlay["id"], string> = {
  NIFTY: "Nifty",
  BANKNIFTY: "Bank",
  FINNIFTY: "Fin",
  SENSEX: "Sensex",
  MIDCPNIFTY: "Midcap",
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

function sideMark(side: IndexPlay["side"]): string {
  if (side === "CE") return "CE";
  if (side === "PE") return "PE";
  if (side === "BOTH") return "BOTH";
  return "—";
}

export function NowBoard({
  status,
  now,
  grade,
  viewingIso,
  board,
  bellTithi,
  onOpenSession,
  onOpenWindow,
}: {
  status: LiveNow;
  now: Date;
  grade?: SlotGrade;
  viewingIso: string;
  board: IndexPlay[];
  bellTithi?: string;
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
  const directional = board.filter((row) => row.side === "CE" || row.side === "PE" || row.side === "BOTH");
  const nifty = board.find((x) => x.id === "NIFTY");
  const bank = board.find((x) => x.id === "BANKNIFTY");
  const split = Boolean(nifty && bank && nifty.side !== bank.side && directional.length >= 2);
  const tithi =
    bellTithi && bellTithi !== status.tithiName
      ? `${status.tithiName} (bell ${bellTithi})`
      : status.tithiName;
  const wrongSession = viewingIso !== status.sessionIso;
  const showJump = Boolean(status.window) && wrongSession;
  const tape =
    grade && (grade.kind === "LIVE" || grade.kind === "HIT" || grade.kind === "MISS") && grade.delta !== null
      ? grade.delta
      : null;

  const playLabel =
    status.phase === "post" && status.regime ? REGIME_SHORT[status.regime] : status.play;
  const when =
    status.phase === "live" && windowLeft
      ? [windowLeft, kalam, status.window ? `${status.window.from}–${status.window.to}` : null].filter(Boolean).join(" · ")
      : status.phase === "pre"
        ? "at 09:15 IST"
        : `next ${sessionLabel(status.nextOpenIso)}`;

  return (
    <div className="ko-now">
      <div className="ko-now-top">
        <span className="ko-now-phase" data-live={status.phase === "live"}>
          {phaseLabel(status, now)}
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

      <div
        className={`ko-now-play ${
          status.phase === "post" && status.regime ? regimeTone(status.regime).fg : playTone
        }`}
      >
        <span>{playLabel}</span>
        <span className="ko-now-sub">{when}</span>
      </div>

      <p className="ko-now-copy">{status.suggestion}</p>

      {split && nifty && bank ? (
        <p className="ko-now-copy">
          <span className={gtone.fg}>{status.gap.label}</span>
          {" · "}
          {SHORT.NIFTY} {sideMark(nifty.side)} vs {SHORT.BANKNIFTY} {sideMark(bank.side)}
        </p>
      ) : directional.length > 0 ? (
        <div className="ko-now-board" aria-label="Index plays">
          {directional.map((row) => (
            <span key={row.id} className={actionTone(row.play, row.side)}>
              {SHORT[row.id]} {sideMark(row.side)}
            </span>
          ))}
        </div>
      ) : null}

      <div className="ko-now-meta">
        <span>
          {status.hora.lord} {horaLeft}
        </span>
        <span>
          {status.lagnaSign} {status.lagnaDegree.toFixed(0)}°
        </span>
        <span>
          {tithi} · {status.nakshatra}
        </span>
        {status.choghadiyaKind === "bad" ? <span>{status.choghadiya} · sit</span> : null}
        {status.next && status.phase === "live" && status.next.action !== status.play ? (
          <span>
            then {status.next.action} {status.next.from}
          </span>
        ) : null}
      </div>

      {progress !== null ? (
        <div className="ko-now-bar" aria-hidden="true">
          <span style={{ width: `${Math.round(progress * 100)}%` }} />
        </div>
      ) : null}

      {wrongSession || showJump ? (
        <div className="ko-now-actions">
          {showJump ? (
            <button type="button" className="ko-link" onClick={() => onOpenWindow(status.window as WindowSlot)}>
              Jump to this window
            </button>
          ) : null}
          {wrongSession ? (
            status.phase === "live" ? (
              <button type="button" className="ko-link" onClick={() => onOpenSession(status.sessionIso)}>
                Switch to live session
              </button>
            ) : (
              <span className="text-muted">Timings below are {sessionLabel(viewingIso)}</span>
            )
          ) : null}
        </div>
      ) : null}
    </div>
  );
}