/**
 * Tape overlay — grades the astro clock against cash-session OHLC.
 * Never imported by engine.ts. Forecast stays purely astrological.
 */

import type { TradeAction, TradeSide, Underlying, WindowSlot } from "./types";
import { UNDERLYINGS } from "./types";
import { formatIstIsoDate, getIstParts, minutesOfDay, utcFromIstParts } from "./time";

export const YF_SYMBOL: Record<Underlying, string> = {
  NIFTY: "^NSEI",
  BANKNIFTY: "^NSEBANK",
  FINNIFTY: "NIFTY_FIN_SERVICE.NS",
  SENSEX: "^BSESN",
  MIDCPNIFTY: "NIFTY_MID_SELECT.NS",
};

/** Kite candle symbols. Bare `NIFTY` 404s the candles endpoint. */
export const CANDLE_SYMBOL: Record<Underlying, string> = {
  NIFTY: "NSE:NIFTY 50",
  BANKNIFTY: "NSE:NIFTY BANK",
  FINNIFTY: "NSE:NIFTY FIN SERVICE",
  SENSEX: "BSE:SENSEX",
  MIDCPNIFTY: "NSE:NIFTY MID SELECT",
};

export const FLAT_PTS: Record<Underlying, number> = {
  NIFTY: 8,
  BANKNIFTY: 20,
  FINNIFTY: 8,
  SENSEX: 25,
  MIDCPNIFTY: 10,
};

export interface TapeBar {
  t: number;
  o: number;
  h: number;
  l: number;
  c: number;
}

export interface SessionTape {
  iso: string;
  underlying: Underlying;
  symbol: string;
  bars: TapeBar[];
  prevClose: number | null;
  sessionOpen: number | null;
  source: string;
}

export type GradeKind = "HIT" | "MISS" | "SIT" | "LIVE" | "PENDING" | "NONE";

export interface SlotGrade {
  kind: GradeKind;
  label: string;
  delta: number | null;
  favor: number | null;
  dir: "up" | "down" | "flat" | null;
  note: string;
}

export interface TapeSummary {
  hits: number;
  misses: number;
  sits: number;
  directional: number;
  pnl: number;
  hitRate: number | null;
  gapActual: "up" | "down" | "flat" | null;
  gapPts: number | null;
  gapPct: number | null;
  gapHit: boolean | null;
}

export interface BuyContract {
  verb: "BUY" | "HOLD" | "BOOK" | "SIT";
  strike: number | null;
  strikeHi: number | null;
  side: TradeSide;
  label: string;
  short: string;
}

export function istMinOf(unixSec: number): { iso: string; min: number } {
  const d = new Date(unixSec * 1000);
  const p = getIstParts(d);
  return { iso: formatIstIsoDate(d), min: minutesOfDay(p.hour, p.minute) };
}

export function windowOhlc(
  bars: TapeBar[],
  iso: string,
  fromMin: number,
  toMin: number,
): { open: number; high: number; low: number; close: number } | null {
  const last = toMin >= 15 * 60 + 30;
  const slice: TapeBar[] = [];
  for (const b of bars) {
    const p = istMinOf(b.t);
    if (p.iso !== iso) continue;
    const overlaps = p.min + 5 > fromMin && (last ? p.min <= toMin : p.min < toMin);
    if (overlaps) slice.push(b);
  }
  if (!slice.length) return null;
  return {
    open: slice[0].o,
    high: Math.max(...slice.map((b) => b.h)),
    low: Math.min(...slice.map((b) => b.l)),
    close: slice[slice.length - 1].c,
  };
}

const STRIKE = new Intl.NumberFormat("en-IN");

export function roundStrike(spot: number, step: number): number {
  if (step <= 0) return Math.round(spot);
  return Math.round(spot / step) * step;
}

export function spotForSlot(tape: SessionTape | null, fromMin: number, toMin: number): number | null {
  if (!tape) return null;
  const ohlc = windowOhlc(tape.bars, tape.iso, fromMin, toMin);
  if (ohlc) return ohlc.open;
  let last: number | null = null;
  for (const b of tape.bars) {
    const p = istMinOf(b.t);
    if (p.iso !== tape.iso) continue;
    if (p.min <= fromMin) last = b.c;
  }
  if (last != null) return last;
  if (tape.bars.length) return tape.bars[tape.bars.length - 1].c;
  return tape.sessionOpen ?? tape.prevClose;
}

function verbOf(action: TradeAction): BuyContract["verb"] {
  if (action === "WAIT" || action === "AVOID") return "SIT";
  if (action.startsWith("BOOK")) return "BOOK";
  if (action.startsWith("HOLD")) return "HOLD";
  return "BUY";
}

function stepOf(underlying: Underlying): number {
  return UNDERLYINGS.find((u) => u.id === underlying)?.step ?? 50;
}

function familyOf(slot: Pick<WindowSlot, "side" | "action" | "product">):
  | { kind: "sit" }
  | { kind: "straddle" }
  | { kind: "single"; side: "CE" | "PE" } {
  if (slot.side === "WAIT" || slot.action === "WAIT" || slot.action === "AVOID" || slot.product === "No contract") {
    return { kind: "sit" };
  }
  if (slot.side === "BOTH" || /straddle|IRON FLY|STRADDLE/i.test(slot.product)) {
    return { kind: "straddle" };
  }
  return { kind: "single", side: slot.side === "CE" ? "CE" : "PE" };
}

/** ATM family from the book, priced off the tape at the window open. */
export function buyContract(
  slot: Pick<WindowSlot, "fromMin" | "toMin" | "side" | "action" | "product">,
  tape: SessionTape | null,
): BuyContract {
  const sit: BuyContract = { verb: "SIT", strike: null, strikeHi: null, side: "WAIT", label: "—", short: "—" };
  const family = familyOf(slot);
  if (family.kind === "sit") return sit;

  const verb = verbOf(slot.action);
  const spot = spotForSlot(tape, slot.fromMin, slot.toMin);
  const step = tape ? stepOf(tape.underlying) : 50;
  const atm = spot != null ? roundStrike(spot, step) : null;

  if (family.kind === "straddle") {
    const short = atm != null ? `${STRIKE.format(atm)} CE / ${STRIKE.format(atm)} PE` : "—";
    return {
      verb: verb === "SIT" ? "BUY" : verb,
      strike: atm,
      strikeHi: atm,
      side: "BOTH",
      label: short,
      short,
    };
  }

  const short = atm != null ? `${STRIKE.format(atm)} ${family.side}` : "—";
  return {
    verb: verb === "SIT" ? "BUY" : verb,
    strike: atm,
    strikeHi: null,
    side: family.side,
    label: short,
    short,
  };
}

function favorPts(side: string, delta: number): number {
  if (side === "PE") return -delta;
  if (side === "CE") return delta;
  return delta;
}

export function gradeSlot(
  slot: Pick<WindowSlot, "fromMin" | "toMin" | "side" | "action">,
  tape: SessionTape | null,
  nowMin: number | null,
  sameDay: boolean,
): SlotGrade {
  if (!tape || !tape.bars.length) {
    return { kind: "NONE", label: "—", delta: null, favor: null, dir: null, note: "No tape yet" };
  }
  const live = sameDay && nowMin !== null && nowMin >= slot.fromMin && nowMin < slot.toMin;
  const pending = sameDay && nowMin !== null && nowMin < slot.fromMin;
  if (pending) return { kind: "PENDING", label: "—", delta: null, favor: null, dir: null, note: "Not started" };

  const ohlc = windowOhlc(tape.bars, tape.iso, slot.fromMin, slot.toMin);
  if (!ohlc) {
    return { kind: live ? "LIVE" : "NONE", label: live ? "LIVE" : "—", delta: null, favor: null, dir: null, note: live ? "Waiting on first print" : "No bars" };
  }
  const delta = ohlc.close - ohlc.open;
  const favor = favorPts(slot.side, delta);
  const flat = FLAT_PTS[tape.underlying] ?? 8;
  const dir: "up" | "down" | "flat" = Math.abs(delta) < flat ? "flat" : delta > 0 ? "up" : "down";
  const rangePct = ohlc.open ? ((ohlc.high - ohlc.low) / ohlc.open) * 100 : 0;

  if (slot.side === "WAIT" || slot.action === "AVOID" || slot.action === "WAIT") {
    const kind: GradeKind = live ? "LIVE" : "SIT";
    return {
      kind,
      label: live ? "LIVE" : "SIT",
      delta,
      favor,
      dir,
      note: dir === "flat" ? "Sat a quiet window" : `Sat a ${dir} ${Math.abs(delta).toFixed(0)}-pt window`,
    };
  }

  let hit: boolean;
  if (slot.side === "BOTH" || slot.action === "STRADDLE" || slot.action === "IRON FLY") {
    hit = slot.action === "IRON FLY" ? rangePct < 0.12 : rangePct >= 0.12 || Math.abs(delta) >= flat * 2;
  } else if (slot.side === "CE") {
    hit = favor > 0;
  } else {
    hit = favor > 0;
  }

  if (live) {
    return {
      kind: "LIVE",
      label: "LIVE",
      delta,
      favor,
      dir,
      note: `Running ${favor >= 0 ? "+" : ""}${favor.toFixed(0)} for ${slot.side}`,
    };
  }
  return {
    kind: hit ? "HIT" : "MISS",
    label: hit ? "HIT" : "MISS",
    delta,
    favor,
    dir,
    note: `${favor >= 0 ? "+" : ""}${favor.toFixed(0)} for ${slot.side}`,
  };
}

export function summariseTape(
  slots: WindowSlot[],
  tape: SessionTape | null,
  nowMin: number | null,
  sameDay: boolean,
  predictedGap: "up" | "down" | "flat" | null,
): TapeSummary {
  let hits = 0;
  let misses = 0;
  let sits = 0;
  let pnl = 0;
  for (const s of slots) {
    const g = gradeSlot(s, tape, nowMin, sameDay);
    if (g.kind === "HIT") {
      hits += 1;
      if (g.favor !== null) pnl += g.favor;
    } else if (g.kind === "MISS") {
      misses += 1;
      if (g.favor !== null) pnl += g.favor;
    } else if (g.kind === "SIT") sits += 1;
  }
  const directional = hits + misses;
  let gapPts: number | null = null;
  let gapPct: number | null = null;
  let gapActual: TapeSummary["gapActual"] = null;
  let gapHit: boolean | null = null;
  if (tape?.prevClose && tape.sessionOpen) {
    gapPts = tape.sessionOpen - tape.prevClose;
    gapPct = (gapPts / tape.prevClose) * 100;
    gapActual = Math.abs(gapPct) < 0.12 ? "flat" : gapPts > 0 ? "up" : "down";
    if (predictedGap) gapHit = gapActual === predictedGap;
  }
  return {
    hits,
    misses,
    sits,
    directional,
    pnl,
    hitRate: directional ? hits / directional : null,
    gapActual,
    gapPts,
    gapPct,
    gapHit,
  };
}

export function sessionBoundsUnix(iso: string): { p1: number; p2: number } {
  const [y, m, d] = iso.split("-").map(Number);
  const p1 = Math.floor(utcFromIstParts(y, m, d, 9, 0, 0).getTime() / 1000);
  const p2 = Math.floor(utcFromIstParts(y, m, d, 16, 0, 0).getTime() / 1000);
  return { p1, p2 };
}

export function parseYahooChart(json: unknown, iso: string, underlying: Underlying): SessionTape {
  const empty: SessionTape = { iso, underlying, symbol: YF_SYMBOL[underlying], bars: [], prevClose: null, sessionOpen: null, source: "yahoo" };
  const chart = json as {
    chart?: {
      result?: Array<{
        meta?: { chartPreviousClose?: number; previousClose?: number; regularMarketPrice?: number };
        timestamp?: number[];
        indicators?: { quote?: Array<{ open?: (number | null)[]; high?: (number | null)[]; low?: (number | null)[]; close?: (number | null)[] }> };
      }>;
    };
  };
  const r = chart.chart?.result?.[0];
  if (!r?.timestamp?.length) return empty;
  const q = r.indicators?.quote?.[0];
  if (!q) return empty;
  const bars: TapeBar[] = [];
  for (let i = 0; i < r.timestamp.length; i++) {
    const o = q.open?.[i];
    const h = q.high?.[i];
    const l = q.low?.[i];
    const c = q.close?.[i];
    if (o == null || h == null || l == null || c == null) continue;
    const p = istMinOf(r.timestamp[i]);
    if (p.iso !== iso) continue;
    bars.push({ t: r.timestamp[i], o, h, l, c });
  }
  const prevClose = r.meta?.chartPreviousClose ?? r.meta?.previousClose ?? null;
  const sessionOpen = bars[0]?.o ?? null;
  return { iso, underlying, symbol: YF_SYMBOL[underlying], bars, prevClose, sessionOpen, source: "yahoo" };
}

export function barsFromOhlcv(
  rows: Array<{ time: number; open: number; high: number; low: number; close: number }>,
  iso: string,
  underlying: Underlying,
  prevClose: number | null = null,
): SessionTape {
  const bars: TapeBar[] = [];
  let inferredPrev: number | null = prevClose;
  for (const r of rows) {
    const t = r.time > 1e12 ? Math.floor(r.time / 1000) : r.time;
    const p = istMinOf(t);
    if (p.iso < iso) inferredPrev = r.close;
    if (p.iso !== iso) continue;
    bars.push({ t, o: r.open, h: r.high, l: r.low, c: r.close });
  }
  return {
    iso,
    underlying,
    symbol: YF_SYMBOL[underlying],
    bars,
    prevClose: inferredPrev,
    sessionOpen: bars[0]?.o ?? null,
    source: "candles",
  };
}
