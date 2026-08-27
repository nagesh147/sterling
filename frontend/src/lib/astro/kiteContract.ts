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
  return hits[0] ?? null;
}

export function matchOpenPosition(
  positions: Array<Partial<OpenPos> & { tradingsymbol?: string; quantity?: number }>,
  underlying: Underlying,
  strike: number,
  side: "CE" | "PE",
): OpenPos | null {
  const needle = `${strike}${side}`;
  for (const p of positions) {
    const qty = Number(p.quantity) || 0;
    if (!qty) continue;
    const sym = String(p.tradingsymbol ?? "").toUpperCase();
    if (!sym.endsWith(needle)) continue;
    if (underlying === "NIFTY") {
      if (!/^NIFTY(?!BANK|FIN|MID)/.test(sym)) continue;
    } else if (!sym.startsWith(underlying)) {
      continue;
    }
    return {
      tradingsymbol: String(p.tradingsymbol),
      exchange: String(p.exchange ?? optionExchange(underlying)),
      quantity: qty,
      product: String(p.product ?? "MIS"),
      last_price: Number(p.last_price) || 0,
    };
  }
  return null;
}
