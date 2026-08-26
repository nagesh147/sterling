import { clockFromMinutes, formatIstIsoDate, getIstParts, MARKET_CLOSE_MIN, MARKET_OPEN_MIN, minutesOfDay } from "../../../lib/astro/time";
import type { SessionTape } from "../../../lib/astro/tape";
import type { WindowSlot } from "../../../lib/astro/types";

const W = 750;
const TAPE_TOP = 6;
const TAPE_H = 32;
const BAR_Y = 42;
const BAR_H = 16;
const HORA_Y = 72;
const H = 86;
const SPAN = MARKET_CLOSE_MIN - MARKET_OPEN_MIN;

const TICKS = [MARKET_OPEN_MIN, 600, 660, 720, 780, 840, 900, MARKET_CLOSE_MIN];
const HORA_SHORT: Record<string, string> = {
  Sun: "Su",
  Venus: "Ve",
  Mercury: "Me",
  Moon: "Mo",
  Saturn: "Sa",
  Jupiter: "Ju",
  Mars: "Ma",
};

function xOf(min: number): number {
  return ((min - MARKET_OPEN_MIN) / SPAN) * W;
}

function stripClass(slot: WindowSlot): string {
  if (slot.action === "AVOID" || slot.kalam.yamagandam) return "ko-strip-avoid";
  if (slot.side === "CE") return "ko-strip-ce";
  if (slot.side === "PE") return "ko-strip-pe";
  if (slot.side === "BOTH") return "ko-strip-both";
  return "ko-strip-wait";
}

function horaRuns(slots: WindowSlot[]) {
  const runs: { lord: string; fromMin: number; toMin: number }[] = [];
  for (const s of slots) {
    const last = runs[runs.length - 1];
    if (last && last.lord === s.hora) last.toMin = s.toMin;
    else runs.push({ lord: s.hora, fromMin: s.fromMin, toMin: s.toMin });
  }
  return runs;
}

function mixMinutes(slots: WindowSlot[]) {
  let ce = 0;
  let pe = 0;
  let both = 0;
  let wait = 0;
  for (const s of slots) {
    const d = Math.max(0, s.toMin - s.fromMin);
    if (s.side === "CE") ce += d;
    else if (s.side === "PE") pe += d;
    else if (s.side === "BOTH") both += d;
    else wait += d;
  }
  return { ce, pe, both, wait, total: ce + pe + both + wait || 1 };
}

function tapePoints(tape: SessionTape | null, iso: string): { d: string; up: boolean } | null {
  if (!tape || tape.iso !== iso || !tape.bars.length) return null;
  const pts: { min: number; c: number }[] = [];
  for (const b of tape.bars) {
    const p = getIstParts(new Date(b.t * 1000));
    if (formatIstIsoDate(new Date(b.t * 1000)) !== iso) continue;
    const min = minutesOfDay(p.hour, p.minute);
    if (min < MARKET_OPEN_MIN || min > MARKET_CLOSE_MIN) continue;
    pts.push({ min, c: b.c });
  }
  if (pts.length < 2) return null;
  const lo = Math.min(...pts.map((p) => p.c));
  const hi = Math.max(...pts.map((p) => p.c));
  const span = hi - lo || 1;
  const d = pts
    .map((p, i) => {
      const x = xOf(p.min).toFixed(1);
      const y = (TAPE_TOP + TAPE_H - ((p.c - lo) / span) * TAPE_H).toFixed(1);
      return `${i === 0 ? "M" : "L"}${x} ${y}`;
    })
    .join(" ");
  return { d, up: pts[pts.length - 1].c >= pts[0].c };
}

function tickLabel(min: number): string {
  if (min === MARKET_OPEN_MIN || min === MARKET_CLOSE_MIN) return clockFromMinutes(min).replace(" ", "");
  const h = Math.floor(min / 60);
  const m = min % 60;
  return m === 0 ? `${h > 12 ? h - 12 : h}` : clockFromMinutes(min).replace(" ", "");
}

export function SessionStrip({
  slots,
  iso,
  tape,
  nowMin,
  sameDay,
  onPick,
}: {
  slots: WindowSlot[];
  iso: string;
  tape: SessionTape | null;
  nowMin: number | null;
  sameDay: boolean;
  onPick?: (slot: WindowSlot) => void;
}) {
  const spark = tapePoints(tape, iso);
  const mix = mixMinutes(slots);
  const live =
    sameDay && nowMin !== null && nowMin >= MARKET_OPEN_MIN && nowMin <= MARKET_CLOSE_MIN ? nowMin : null;

  return (
    <div className="ko-strip">
      <svg viewBox={`0 0 ${W} ${H}`} role="img" aria-label="Cash session 09:15 to 15:30">
        <defs>
          <pattern id="ko-hatch" width="6" height="6" patternUnits="userSpaceOnUse" patternTransform="rotate(45)">
            <line x1="0" y1="0" x2="0" y2="6" stroke="#9b9b9b" strokeWidth="1" />
          </pattern>
        </defs>
        <rect x="0" y={TAPE_TOP} width={W} height={TAPE_H} className="ko-strip-tapebg" />
        {spark ? (
          <path d={spark.d} fill="none" stroke={spark.up ? "#4caf50" : "#df514c"} strokeWidth="1.4" />
        ) : (
          <text x="8" y={TAPE_TOP + 20} className="ko-strip-empty">
            {tape && tape.bars.length ? "Tape outside this session" : "Tape —"}
          </text>
        )}
        {slots.map((s) => {
          const x = xOf(s.fromMin);
          const w = Math.max(1, xOf(s.toMin) - x);
          const label = `${s.from}–${s.to} · ${s.action} · ${s.regime} · ${s.hora} hora${s.kalam.rahu ? " · Rahu" : ""}${s.kalam.yamagandam ? " · Yamagandam" : ""}`;
          return (
            <g key={`${s.from}-${s.to}`}>
              <title>{label}</title>
              <rect
                x={x}
                y={BAR_Y}
                width={w}
                height={BAR_H}
                className={stripClass(s)}
                onClick={() => onPick?.(s)}
              />
              {s.kalam.rahu ? <rect x={x} y={BAR_Y} width={w} height={BAR_H} fill="url(#ko-hatch)" opacity="0.45" /> : null}
            </g>
          );
        })}
        {horaRuns(slots).map((run) => {
          const x = xOf(run.fromMin);
          const w = xOf(run.toMin) - x;
          if (w < 22) return null;
          const label = w < 48 ? (HORA_SHORT[run.lord] ?? run.lord.slice(0, 2)) : run.lord;
          return (
            <text key={`${run.lord}-${run.fromMin}`} x={x + w / 2} y={HORA_Y} textAnchor="middle" className="ko-strip-hora">
              {label}
            </text>
          );
        })}
        {TICKS.map((t) => (
          <g key={t}>
            <line x1={xOf(t)} y1={BAR_Y + BAR_H} x2={xOf(t)} y2={BAR_Y + BAR_H + 4} className="ko-strip-tick" />
            <text x={xOf(t)} y={84} textAnchor={t === MARKET_OPEN_MIN ? "start" : t === MARKET_CLOSE_MIN ? "end" : "middle"} className="ko-strip-lbl">
              {tickLabel(t)}
            </text>
          </g>
        ))}
        {live !== null ? (
          <line x1={xOf(live)} y1={TAPE_TOP} x2={xOf(live)} y2={BAR_Y + BAR_H} className="ko-strip-now" />
        ) : null}
      </svg>
      <div className="ko-strip-leg">
        <span>
          <i className="ko-swatch-ce" />
          CE {mix.ce}m
        </span>
        <span>
          <i className="ko-swatch-pe" />
          PE {mix.pe}m
        </span>
        {mix.both > 0 ? (
          <span>
            <i className="ko-swatch-both" />
            Both {mix.both}m
          </span>
        ) : null}
        <span>
          <i className="ko-swatch-wait" />
          WAIT {mix.wait}m
        </span>
        <span className="text-muted">09:15–15:30 IST</span>
      </div>
      <div className="ko-mix" aria-hidden="true">
        <span className="ko-mix-ce" style={{ width: `${(mix.ce / mix.total) * 100}%` }} />
        <span className="ko-mix-pe" style={{ width: `${(mix.pe / mix.total) * 100}%` }} />
        <span className="ko-mix-both" style={{ width: `${(mix.both / mix.total) * 100}%` }} />
        <span className="ko-mix-wait" style={{ width: `${(mix.wait / mix.total) * 100}%` }} />
      </div>
    </div>
  );
}
