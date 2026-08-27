/** One-lot same-side run: enter the first CE/PE play, hold through WAIT gaps, exit when the run ends. */

import { runAhead, sameSidePlay } from "./kiteContract";
import { istMinOf, windowOhlc, type SessionTape, type TapeBar } from "./tape";
import type { Underlying, WindowSlot } from "./types";
import { UNDERLYINGS } from "./types";

/** ATM option ≈ 0.5 delta. One index point in favor ≈ 0.5 × lot in rupees. */
export const ATM_DELTA = 0.5;

export function lotOf(underlying: Underlying): number {
  return UNDERLYINGS.find((u) => u.id === underlying)?.lot ?? 65;
}

export function rupees(pts: number, underlying: Underlying): number {
  return Math.round(pts * lotOf(underlying) * ATM_DELTA);
}

export interface SimTrade {
  iso: string;
  side: "CE" | "PE";
  from: string;
  to: string;
  fromMin: number;
  toMin: number;
  windows: number;
  entry: number;
  exit: number;
  pts: number;
  hit: boolean;
  why: "run" | "stop" | "target" | "trail";
}

export interface SimDay {
  iso: string;
  weekday: string;
  trades: SimTrade[];
  pts: number;
  hits: number;
  misses: number;
  skipped: boolean;
  reason?: string;
}

export interface SimMonth {
  year: number;
  month: number;
  underlying: Underlying;
  days: SimDay[];
  trades: number;
  hits: number;
  misses: number;
  pts: number;
  pePts: number;
  cePts: number;
  inr: number;
  peInr: number;
  ceInr: number;
  lot: number;
  best: SimTrade | null;
  worst: SimTrade | null;
  loaded: number;
  missing: number;
}

function entrySide(slot: Pick<WindowSlot, "side" | "action">): "CE" | "PE" | null {
  if (slot.action === "WAIT" || slot.action === "AVOID") return null;
  if (slot.action.startsWith("BOOK")) return null;
  if (slot.side === "CE" || slot.side === "PE") return slot.side;
  return null;
}

function protections(action: string, underlying: Underlying): { sl: number; tgt: number; lock: number; trail: number } {
  const wide = underlying === "BANKNIFTY" || underlying === "SENSEX";
  if (action.startsWith("HOLD")) {
    return wide ? { sl: -80, tgt: 200, lock: 40, trail: 40 } : { sl: -40, tgt: 120, lock: 25, trail: 25 };
  }
  return wide ? { sl: -50, tgt: 90, lock: 25, trail: 25 } : { sl: -25, tgt: 50, lock: 15, trail: 15 };
}

function favorAt(side: "CE" | "PE", entry: number, px: number): number {
  return side === "PE" ? entry - px : px - entry;
}

function walkRun(
  side: "CE" | "PE",
  entry: number,
  bars: TapeBar[],
  fromMin: number,
  toMin: number,
  iso: string,
  action: string,
  underlying: Underlying,
): { pts: number; exit: number; why: SimTrade["why"] } {
  const { sl, tgt, lock, trail } = protections(action, underlying);
  let stop = sl;
  let water = 0;
  let last = entry;
  for (const b of bars) {
    const p = istMinOf(b.t);
    if (p.iso !== iso) continue;
    if (p.min + 5 <= fromMin) continue;
    if (p.min > toMin) break;
    const hi = favorAt(side, entry, side === "PE" ? b.l : b.h);
    const lo = favorAt(side, entry, side === "PE" ? b.h : b.l);
    const close = favorAt(side, entry, b.c);
    water = Math.max(water, hi);
    if (water >= lock) stop = Math.max(stop, 0);
    if (water >= lock + trail) stop = Math.max(stop, water - trail);
    if (lo <= stop) return { pts: Math.round(stop * 10) / 10, exit: b.c, why: stop >= 0 ? "trail" : "stop" };
    if (close >= tgt) return { pts: Math.round(tgt * 10) / 10, exit: b.c, why: "target" };
    last = b.c;
  }
  const pts = Math.round(favorAt(side, entry, last) * 10) / 10;
  return { pts, exit: last, why: "run" };
}

export function simulateDay(
  slots: Array<Pick<WindowSlot, "from" | "to" | "fromMin" | "toMin" | "side" | "action" | "date">>,
  tape: SessionTape | null,
  weekday = "",
): SimDay {
  const iso = tape?.iso || slots[0]?.date || "";
  if (!tape || !tape.bars.length) {
    return { iso, weekday, trades: [], pts: 0, hits: 0, misses: 0, skipped: true, reason: "No tape" };
  }

  const trades: SimTrade[] = [];
  let i = 0;
  while (i < slots.length) {
    const start = slots[i];
    const side = entrySide(start);
    if (!side) {
      i += 1;
      continue;
    }
    let endIdx = i;
    for (let j = i + 1; j < slots.length; j++) {
      const s = slots[j];
      if (sameSidePlay(s.side, s.action, side)) {
        endIdx = j;
        continue;
      }
      if (runAhead(slots, side, s.fromMin)) continue;
      break;
    }
    const end = slots[endIdx];
    const entryBar = windowOhlc(tape.bars, tape.iso, start.fromMin, start.toMin);
    const exitBar = windowOhlc(tape.bars, tape.iso, end.fromMin, end.toMin);
    if (!entryBar || !exitBar) {
      i = endIdx + 1;
      continue;
    }
    const raw = walkRun(side, entryBar.open, tape.bars, start.fromMin, end.toMin, tape.iso, start.action, tape.underlying);
    trades.push({
      iso: tape.iso,
      side,
      from: start.from,
      to: end.to,
      fromMin: start.fromMin,
      toMin: end.toMin,
      windows: endIdx - i + 1,
      entry: entryBar.open,
      exit: raw.exit,
      pts: raw.pts,
      hit: raw.pts > 0,
      why: raw.why,
    });
    i = endIdx + 1;
  }

  const pts = trades.reduce((a, t) => a + t.pts, 0);
  return {
    iso: tape.iso,
    weekday,
    trades,
    pts,
    hits: trades.filter((t) => t.hit).length,
    misses: trades.filter((t) => !t.hit && t.pts !== 0).length,
    skipped: false,
  };
}

export function rollMonth(
  year: number,
  month: number,
  underlying: Underlying,
  days: SimDay[],
): SimMonth {
  const done = days.filter((d) => !d.skipped);
  const trades = done.flatMap((d) => d.trades);
  const ranked = [...trades].sort((a, b) => b.pts - a.pts);
  return {
    year,
    month,
    underlying,
    days,
    trades: trades.length,
    hits: trades.filter((t) => t.hit).length,
    misses: trades.filter((t) => !t.hit && t.pts !== 0).length,
    pts: trades.reduce((a, t) => a + t.pts, 0),
    pePts: trades.filter((t) => t.side === "PE").reduce((a, t) => a + t.pts, 0),
    cePts: trades.filter((t) => t.side === "CE").reduce((a, t) => a + t.pts, 0),
    inr: rupees(trades.reduce((a, t) => a + t.pts, 0), underlying),
    peInr: rupees(trades.filter((t) => t.side === "PE").reduce((a, t) => a + t.pts, 0), underlying),
    ceInr: rupees(trades.filter((t) => t.side === "CE").reduce((a, t) => a + t.pts, 0), underlying),
    lot: lotOf(underlying),
    best: ranked[0] ?? null,
    worst: ranked.length ? ranked[ranked.length - 1] : null,
    loaded: done.length,
    missing: days.filter((d) => d.skipped).length,
  };
}
