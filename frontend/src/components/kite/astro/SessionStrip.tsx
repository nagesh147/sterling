import {
  clockFromMinutes,
  formatIstIsoDate,
  getIstParts,
  MARKET_CLOSE_MIN,
  MARKET_OPEN_MIN,
  minutesOfDay,
} from "../../../lib/astro/time";
import type { SessionTape, SlotGrade } from "../../../lib/astro/tape";
import type { WindowSlot } from "../../../lib/astro/types";

const W = 800;
const TAPE_TOP = 10;
const TAPE_H = 52;
const BAR_Y = 70;
const BAR_H = 22;
const HORA_Y = 106;
const AXIS_Y = 122;
const H = 132;
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

function tapeShape(tape: SessionTape | null, iso: string): { line: string; area: string; up: boolean } | null {
  if (!tape || tape.iso !== iso || !tape.bars.length) return null;
  const pts: { min: number; c: number }[] = [];
  for (const b of tape.bars) {
    const t = new Date(b.t * 1000);
    if (formatIstIsoDate(t) !== iso) continue;
    const p = getIstParts(t);
    const min = minutesOfDay(p.hour, p.minute);
    if (min < MARKET_OPEN_MIN || min > MARKET_CLOSE_MIN) continue;
    pts.push({ min, c: b.c });
  }
  if (pts.length < 2) return null;
  const lo = Math.min(...pts.map((p) => p.c));
  const hi = Math.max(...pts.map((p) => p.c));
  const span = hi - lo || 1;
  const coords = pts.map((p) => {
    const x = xOf(p.min).toFixed(1);
    const y = (TAPE_TOP + TAPE_H - ((p.c - lo) / span) * TAPE_H).toFixed(1);
    return { x, y };
  });
  const line = coords.map((p, i) => `${i === 0 ? "M" : "L"}${p.x} ${p.y}`).join(" ");
  const last = coords[coords.length - 1];
  const first = coords[0];
  const base = TAPE_TOP + TAPE_H;
  const area = `${line} L${last.x} ${base} L${first.x} ${base} Z`;
  return { line, area, up: pts[pts.length - 1].c >= pts[0].c };
}

function tickLabel(min: number): string {
  if (min === MARKET_OPEN_MIN || min === MARKET_CLOSE_MIN) return clockFromMinutes(min).replace(" ", "");
  const h = Math.floor(min / 60);
  const m = min % 60;
  return m === 0 ? `${h > 12 ? h - 12 : h}` : clockFromMinutes(min).replace(" ", "");
}

function gradeClass(kind: SlotGrade["kind"] | undefined): string {
  if (kind === "HIT") return "ko-strip-hit";
  if (kind === "MISS") return "ko-strip-miss";
  if (kind === "LIVE") return "ko-strip-live";
  return "";
}

export function SessionStrip({
  slots,
  iso,
  tape,
  nowMin,
  sameDay,
  grades,
  onPick,
}: {
  slots: WindowSlot[];
  iso: string;
  tape: SessionTape | null;
  nowMin: number | null;
  sameDay: boolean;
  grades?: Map<string, SlotGrade>;
  onPick?: (slot: WindowSlot) => void;
}) {
  const spark = tapeShape(tape, iso);
  const mix = mixMinutes(slots);
  const live =
    sameDay && nowMin !== null && nowMin >= MARKET_OPEN_MIN && nowMin <= MARKET_CLOSE_MIN ? nowMin : null;

  return (
    <div className="ko-strip">
      <svg viewBox={`0 0 ${W} ${H}`} role="img" aria-label="Session tape 09:15 to 15:30 IST">
        <defs>
          <pattern id="ko-hatch" width="6" height="6" patternUnits="userSpaceOnUse" patternTransform="rotate(45)">
            <line x1="0" y1="0" x2="0" y2="6" stroke="#9b9b9b" strokeWidth="1" />
          </pattern>
        </defs>
        <rect x="0" y={TAPE_TOP} width={W} height={TAPE_H} className="ko-strip-tapebg" />
        {spark ? (
          <>
            <path d={spark.area} className={spark.up ? "ko-strip-upfill" : "ko-strip-downfill"} />
            <path d={spark.line} fill="none" className={spark.up ? "ko-strip-upline" : "ko-strip-downline"} strokeWidth="1.6" />
          </>
        ) : (
          <text x="10" y={TAPE_TOP + 30} className="ko-strip-empty">
            {tape && tape.bars.length ? "Tape is for another session" : "Tape loading"}
          </text>
        )}
        {slots.map((s) => {
          const x = xOf(s.fromMin);
          const w = Math.max(1, xOf(s.toMin) - x);
          const label = `${s.from}–${s.to} · ${s.action} · ${s.hora} hora${s.kalam.rahu ? " · Rahu" : ""}${s.kalam.yamagandam ? " · Yama" : ""}`;
          const g = grades?.get(`${s.from}-${s.to}`);
          const mark = w >= 28 ? (s.side === "WAIT" ? "" : s.side === "BOTH" ? "±" : s.side) : "";
          return (
            <g key={`${s.from}-${s.to}`}>
              <rect
                x={x}
                y={BAR_Y}
                width={w}
                height={BAR_H}
                className={stripClass(s)}
                role="button"
                tabIndex={0}
                aria-label={label}
                onClick={() => onPick?.(s)}
                onKeyDown={(e) => {
                  if (e.key === "Enter" || e.key === " ") {
                    e.preventDefault();
                    onPick?.(s);
                  }
                }}
              />
              {s.kalam.rahu ? <rect x={x} y={BAR_Y} width={w} height={BAR_H} fill="url(#ko-hatch)" opacity="0.4" pointerEvents="none" /> : null}
              {g ? <rect x={x} y={BAR_Y} width={w} height="2.5" className={gradeClass(g.kind)} pointerEvents="none" /> : null}
              {mark && w >= 28 ? (
                <text x={x + w / 2} y={BAR_Y + 15} textAnchor="middle" className="ko-strip-side">
                  {mark}
                </text>
              ) : null}
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
            <line x1={xOf(t)} y1={BAR_Y + BAR_H} x2={xOf(t)} y2={BAR_Y + BAR_H + 5} className="ko-strip-tick" />
            <text
              x={xOf(t)}
              y={AXIS_Y}
              textAnchor={t === MARKET_OPEN_MIN ? "start" : t === MARKET_CLOSE_MIN ? "end" : "middle"}
              className="ko-strip-lbl"
            >
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
          Sit {mix.wait}m
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
