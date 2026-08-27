import type { TradeAction, Underlying } from "./types";

export interface OptionHit {
  tradingsymbol: string;
  exchange: "NFO" | "BFO";
  strike: number;
  expiry: string;
  lot_size: number;
  last_price: number;
  instrument_type: "CE" | "PE";
}

export interface OpenPos {
  tradingsymbol: string;
  exchange: string;
  quantity: number;
  product: string;
  last_price: number;
  average_price: number;
}

export interface SearchRow {
  tradingsymbol?: string;
  name?: string;
  exchange?: string;
  strike?: number;
  expiry?: string;
  lot_size?: number;
  last_price?: number;
  instrument_type?: string;
}

export function optionExchange(underlying: Underlying): "NFO" | "BFO" {
  return underlying === "SENSEX" ? "BFO" : "NFO";
}

export function searchQuery(underlying: Underlying, strike: number, side: "CE" | "PE"): string {
  return `${underlying} ${strike} ${side}`;
}

export function productForAction(action: TradeAction | string): "MIS" | "NRML" {
  return String(action).startsWith("HOLD") ? "NRML" : "MIS";
}

function nameMatches(row: SearchRow, underlying: Underlying): boolean {
  const name = `${row.name ?? ""} ${row.tradingsymbol ?? ""}`.toUpperCase();
  const sym = (row.tradingsymbol ?? "").toUpperCase();
  if (underlying === "NIFTY") {
    if (sym.startsWith("BANKNIFTY") || sym.startsWith("FINNIFTY") || sym.startsWith("MIDCPNIFTY") || sym.startsWith("NIFTYNXT")) {
      return false;
    }
    return name.includes("NIFTY") && !name.includes("BANKNIFTY") && !name.includes("FINNIFTY") && !name.includes("MIDCPNIFTY");
  }
  return name.includes(underlying) || sym.startsWith(underlying);
}

function expiryIso(raw?: string): string | null {
  if (!raw) return null;
  const m = raw.match(/^(\d{4}-\d{2}-\d{2})/);
  return m ? m[1] : null;
}

/** Nearest live expiry for this strike. Weekly before monthly when both exist. */
export function pickNearestOption(
  rows: SearchRow[],
  underlying: Underlying,
  strike: number,
  side: "CE" | "PE",
  asOfIso: string,
): OptionHit | null {
  const want = optionExchange(underlying);
  const hits: OptionHit[] = [];
  for (const r of rows) {
    const type = String(r.instrument_type ?? "").toUpperCase();
    if (type !== side) continue;
    if (Math.round(Number(r.strike) || 0) !== strike) continue;
    if (!nameMatches(r, underlying)) continue;
    const exp = expiryIso(r.expiry);
    if (!exp || exp < asOfIso) continue;
    const ex = String(r.exchange ?? want).toUpperCase();
    if (ex && ex !== want) continue;
    const sym = String(r.tradingsymbol ?? "").trim();
    if (!sym) continue;
    hits.push({
      tradingsymbol: sym,
      exchange: want,
      strike,
      expiry: exp,
      lot_size: Math.max(1, Number(r.lot_size) || 1),
      last_price: Number(r.last_price) || 0,
      instrument_type: side,
    });
  }
  hits.sort((a, b) => a.expiry.localeCompare(b.expiry) || a.tradingsymbol.localeCompare(b.tradingsymbol));
  if (hits[0]) return hits[0];
  if (asOfIso !== "0000-01-01") return pickNearestOption(rows, underlying, strike, side, "0000-01-01");
  return null;
}

export function optionSideOf(tradingsymbol: string): "CE" | "PE" | null {
  const s = tradingsymbol.toUpperCase();
  if (s.endsWith("PE")) return "PE";
  if (s.endsWith("CE")) return "CE";
  return null;
}

export function heldStrikeLabel(pos: OpenPos): string {
  const side = optionSideOf(pos.tradingsymbol);
  const m = pos.tradingsymbol.toUpperCase().match(/(\d+)(CE|PE)$/);
  if (!m || !side) return pos.tradingsymbol;
  return `${new Intl.NumberFormat("en-IN").format(Number(m[1]))} ${side}`;
}

function underMatches(sym: string, underlying: Underlying): boolean {
  if (underlying === "NIFTY") return /^NIFTY(?!BANK|FIN|MID)/.test(sym);
  return sym.startsWith(underlying);
}

/** Any open CE/PE on this index — not a second lot at a new strike. */
export function matchHeldOption(
  positions: Array<Partial<OpenPos> & { tradingsymbol?: string; quantity?: number }>,
  underlying: Underlying,
  prefer?: "CE" | "PE" | null,
): (OpenPos & { optionSide: "CE" | "PE" }) | null {
  let preferred: (OpenPos & { optionSide: "CE" | "PE" }) | null = null;
  let any: (OpenPos & { optionSide: "CE" | "PE" }) | null = null;
  for (const p of positions) {
    const qty = Number(p.quantity) || 0;
    if (!qty) continue;
    const raw = String(p.tradingsymbol ?? "");
    const sym = raw.toUpperCase();
    if (!underMatches(sym, underlying)) continue;
    const optionSide = optionSideOf(sym);
    if (!optionSide) continue;
    const row: OpenPos & { optionSide: "CE" | "PE" } = {
      tradingsymbol: raw,
      exchange: String(p.exchange ?? optionExchange(underlying)),
      quantity: qty,
      product: String(p.product ?? "MIS"),
      last_price: Number(p.last_price) || 0,
      average_price: Number((p as OpenPos).average_price) || 0,
      optionSide,
    };
    if (!any || Math.abs(row.quantity) > Math.abs(any.quantity)) any = row;
    if (prefer && optionSide === prefer) {
      if (!preferred || Math.abs(row.quantity) > Math.abs(preferred.quantity)) preferred = row;
    }
  }
  return preferred ?? any;
}

export type ContinueKind = "buy" | "trail" | "book" | "lock" | "close" | "sit";

export function roundTick(price: number, tick = 0.05): number {
  if (!(price > 0)) return 0;
  return Math.round(price / tick) * tick;
}

export function protectionPrices(
  last: number,
  slPct: number,
  tgtPct: number | null,
): { sl: number; tgt: number | null } {
  let sl = roundTick(last * (1 + slPct / 100));
  let tgt = tgtPct != null ? roundTick(last * (1 + tgtPct / 100)) : null;
  if (sl >= last) sl = roundTick(Math.max(0.05, last - 0.05));
  if (tgt != null && tgt <= last) tgt = roundTick(last + 0.05);
  return { sl, tgt };
}

/** Long option: SL only climbs, target only runs up. Never loosen. */
export function ratchetProtection(
  last: number,
  proposed: { sl: number; tgt: number | null },
  existing: number[],
): { sl: number; tgt: number | null; changed: boolean } {
  const oldSl = existing.filter((t) => t < last).sort((a, b) => b - a)[0];
  const oldTgt = existing.filter((t) => t > last).sort((a, b) => a - b)[0];
  let sl = proposed.sl;
  if (oldSl != null) sl = Math.max(oldSl, proposed.sl);
  if (sl >= last) sl = oldSl ?? roundTick(Math.max(0.05, last - 0.05));
  let tgt = proposed.tgt;
  if (tgt != null && oldTgt != null) tgt = Math.max(oldTgt, tgt);
  if (tgt == null && oldTgt != null && proposed.tgt != null) tgt = oldTgt;
  const changed = sl !== oldSl || tgt !== oldTgt;
  return { sl, tgt, changed };
}

/** Lock to cost when the lot is in profit; otherwise the window's %. */
export function proposedProtect(
  last: number,
  slPct: number,
  tgtPct: number | null,
  avg = 0,
  kind: ContinueKind = "trail",
): { sl: number; tgt: number | null } {
  const pct = protectionPrices(last, slPct, tgtPct);
  if (kind === "lock" && avg > 0 && last > avg) {
    let sl = roundTick(avg);
    if (sl >= last) sl = pct.sl;
    return { sl, tgt: null };
  }
  return pct;
}

export function bookQty(quantity: number, lotSize = 1): number {
  const lot = lotSize > 0 ? lotSize : 1;
  const abs = Math.abs(quantity);
  const snapped = Math.floor(abs / 2 / lot) * lot;
  return snapped > 0 ? snapped : abs;
}

export function optionPnl(pos: { last_price: number; average_price?: number; quantity: number }): number | null {
  const avg = pos.average_price ?? 0;
  if (!(avg > 0) || !Number.isFinite(pos.last_price)) return null;
  return (pos.last_price - avg) * pos.quantity;
}

function inrPx(n: number): string {
  const digits = n >= 20 ? 0 : 1;
  return `₹${n.toLocaleString("en-IN", { minimumFractionDigits: digits, maximumFractionDigits: digits })}`;
}

function manageLabel(
  verb: string,
  mark: string,
  last: number,
  slPct: number | null,
  tgtPct: number | null,
  avg = 0,
  kind: ContinueKind = "trail",
): string {
  const head = mark ? `${verb} ${mark}` : verb;
  if (!(last > 0) || slPct == null) return head;
  const px = proposedProtect(last, slPct, tgtPct, avg, kind);
  return `${head} · SL ${inrPx(px.sl)}${px.tgt != null ? ` · TGT ${inrPx(px.tgt)}` : ""}`;
}

export interface WindowPlan {
  kind: ContinueKind;
  label: string;
  slPct: number | null;
  tgtPct: number | null;
  note: string;
}

/** Same side = trail the open lot. Flip / avoid = close. Never a second Buy. */
export function planWindow(
  action: string,
  windowSide: "CE" | "PE" | "BOTH" | "WAIT",
  held: { optionSide: "CE" | "PE"; last_price?: number; average_price?: number } | null,
  mark: string,
): WindowPlan {
  const sit: WindowPlan = { kind: "sit", label: "—", slPct: null, tgtPct: null, note: "" };
  const last = held?.last_price ?? 0;
  const avg = held?.average_price ?? 0;
  if (!held) {
    if (windowSide === "WAIT" || windowSide === "BOTH" || action === "WAIT" || action === "AVOID" || action.startsWith("BOOK")) {
      return sit;
    }
    return {
      kind: "buy",
      label: mark && mark !== "—" ? mark : "—",
      slPct: action.startsWith("SCALP") ? -20 : action.startsWith("HOLD") ? -15 : -25,
      tgtPct: action.startsWith("SCALP") ? 30 : action.startsWith("HOLD") ? 80 : 50,
      note: "First lot. Same-side windows trail this — they do not add.",
    };
  }

  const tag = mark || held.optionSide;
  if ((windowSide === "CE" || windowSide === "PE") && windowSide !== held.optionSide) {
    return { kind: "close", label: `Close ${tag}`, slPct: null, tgtPct: null, note: "Side flipped — square off, do not reverse from here." };
  }
  if (action.startsWith("BOOK")) {
    return {
      kind: "book",
      label: manageLabel("Book", tag, last, -10, 15, avg, "book"),
      slPct: -10,
      tgtPct: 15,
      note: "Book half (one lot if that's all you have). Trail the rest.",
    };
  }
  if (action === "AVOID" || action === "WAIT") {
    const inProfit = avg > 0 && last > avg;
    return {
      kind: "lock",
      label: manageLabel("Lock", tag, last, -12, null, avg, "lock"),
      slPct: -12,
      tgtPct: null,
      note: inProfit ? "In profit — stop to cost. No add." : "Stop tightens. No add.",
    };
  }
  const slPct = action.startsWith("HOLD") ? -15 : action.startsWith("SCALP") ? -20 : -25;
  const tgtPct = action.startsWith("HOLD") ? 80 : action.startsWith("SCALP") ? 30 : 50;
  return {
    kind: "trail",
    label: manageLabel("Trail", tag, last, slPct, tgtPct, avg, "trail"),
    slPct,
    tgtPct,
    note: "Same side — trail SL/TGT, do not add.",
  };
}

export function findGtt(
  list: unknown,
  tradingsymbol: string,
): { id: number; triggers: number[] } | null {
  if (!Array.isArray(list)) return null;
  const want = tradingsymbol.toUpperCase();
  for (const raw of list) {
    const g = raw as {
      id?: number;
      trigger_id?: number;
      status?: string;
      tradingsymbol?: string;
      trigger_values?: number[];
      condition?: { tradingsymbol?: string; trigger_values?: number[] };
    };
    const status = String(g.status ?? "active").toLowerCase();
    if (status && status !== "active") continue;
    const sym = String(g.tradingsymbol ?? g.condition?.tradingsymbol ?? "").toUpperCase();
    if (sym !== want) continue;
    const id = Number(g.id ?? g.trigger_id);
    if (!id) continue;
    const triggers = (g.condition?.trigger_values ?? g.trigger_values ?? []).map(Number).filter((n) => n > 0);
    return { id, triggers };
  }
  return null;
}

export function gttBody(pos: OpenPos, last: number, sl: number, tgt: number | null) {
  const qty = Math.abs(pos.quantity);
  const product = pos.product || "MIS";
  const leg = (price: number) => ({
    tradingsymbol: pos.tradingsymbol,
    exchange: pos.exchange,
    transaction_type: "SELL" as const,
    quantity: qty,
    order_type: "LIMIT",
    product,
    price,
  });
  if (tgt != null) {
    const pair = [sl, tgt].sort((a, b) => a - b);
    return {
      trigger_type: "two-leg" as const,
      tradingsymbol: pos.tradingsymbol,
      exchange: pos.exchange,
      last_price: last,
      trigger_values: pair,
      orders: pair.map(leg),
    };
  }
  return {
    trigger_type: "single" as const,
    tradingsymbol: pos.tradingsymbol,
    exchange: pos.exchange,
    last_price: last,
    trigger_values: [sl],
    orders: [leg(sl)],
  };
}
