/**
 * Pure order-ticket logic for the Kite order window.
 *
 * Kept free of React so the lot/price/trigger/validation maths can be reasoned
 * about (and unit-tested) in isolation. Mirrors Kite Connect v3 order semantics:
 *   POST /orders/{variety}  — https://kite.trade/docs/connect/v3/orders/
 *
 *  - `quantity` is the TOTAL quantity (lots × lot_size), never the lot count.
 *  - `price` is sent only for LIMIT / SL orders.
 *  - `trigger_price` is sent only for SL / SL-M orders.
 *  - product depends on segment: equity cash → MIS/CNC, derivatives → MIS/NRML.
 */
import type { PlaceOrderBody, PlaceGttBody } from '../../types/kite';

export type Side = 'BUY' | 'SELL';
export type OrderType = 'MARKET' | 'LIMIT' | 'SL' | 'SL-M';
export type Product = 'MIS' | 'CNC' | 'NRML';
export type Validity = 'DAY' | 'IOC' | 'TTL';
export type Variety = 'regular' | 'amo';

export const ORDER_TYPES: OrderType[] = ['MARKET', 'LIMIT', 'SL', 'SL-M'];

const DERIVATIVE_EXCHANGES = new Set(['NFO', 'BFO', 'CDS', 'BCD', 'MCX']);

/** F&O / currency / commodity segments carry margin and use MIS/NRML. */
export function isDerivative(exchange: string): boolean {
  return DERIVATIVE_EXCHANGES.has((exchange || '').toUpperCase());
}

export interface ProductOption {
  value: Product;
  label: string;   // primary label shown in the toggle
  code: string;    // the Kite product code shown beside it (MIS/CNC/NRML)
}

/**
 * The two product choices Kite offers per segment. Intraday (MIS) is always the
 * first; the carry option is CNC for equity delivery, NRML for derivatives.
 */
export function productsForExchange(exchange: string): ProductOption[] {
  if (isDerivative(exchange)) {
    return [
      { value: 'MIS', label: 'Intraday', code: 'MIS' },
      { value: 'NRML', label: 'Overnight', code: 'NRML' },
    ];
  }
  return [
    { value: 'MIS', label: 'Intraday', code: 'MIS' },
    { value: 'CNC', label: 'Longterm', code: 'CNC' },
  ];
}

/** Zerodha's ticket defaults: equity → CNC (delivery), F&O → NRML (carry). */
export function defaultProduct(exchange: string): Product {
  return isDerivative(exchange) ? 'NRML' : 'CNC';
}

/** Funds bucket the margin is drawn from: commodity for MCX, else equity. */
export function marginSegment(exchange: string): 'equity' | 'commodity' {
  return (exchange || '').toUpperCase() === 'MCX' ? 'commodity' : 'equity';
}

// ─── Lot maths ────────────────────────────────────────────────────────────────

/** Effective lot size — never below 1 (equity trades in single units). */
export function effectiveLot(lotSize?: number | null): number {
  return lotSize && lotSize > 0 ? Math.floor(lotSize) : 1;
}

export function lotsFromQty(qty: number, lotSize?: number | null): number {
  const lot = effectiveLot(lotSize);
  return qty / lot;
}

/** Round an arbitrary quantity to the nearest whole lot (minimum one lot). */
export function snapToLot(qty: number, lotSize?: number | null): number {
  const lot = effectiveLot(lotSize);
  if (!Number.isFinite(qty) || qty <= 0) return lot;
  const lots = Math.max(1, Math.round(qty / lot));
  return lots * lot;
}

/** Step the quantity up/down by exactly one lot, clamped to a single lot. */
export function stepQty(qty: number, lotSize: number | null | undefined, dir: 1 | -1): number {
  const lot = effectiveLot(lotSize);
  const lots = Math.max(1, Math.round(qty / lot) + dir);
  return lots * lot;
}

/** Whole lots → total quantity (the value Kite's `quantity` field expects). */
export function lotsToQty(lots: number, lotSize?: number | null): number {
  const lot = effectiveLot(lotSize);
  return Math.max(1, Math.round(lots)) * lot;
}

/** Round to the nearest exchange tick (0.05 default) — keeps GTT/limit prices valid. */
export function roundTick(price: number, tick = 0.05): number {
  if (!(price > 0)) return 0;
  return Math.round(price / tick) * tick;
}

// ─── Order-type field rules ─────────────────────────────────────────────────

/** LIMIT and SL (stop-loss limit) carry a price. */
export function needsPrice(orderType: OrderType): boolean {
  return orderType === 'LIMIT' || orderType === 'SL';
}

/** SL and SL-M carry a trigger price. */
export function needsTrigger(orderType: OrderType): boolean {
  return orderType === 'SL' || orderType === 'SL-M';
}

// ─── Validation ──────────────────────────────────────────────────────────────

export interface TicketState {
  side: Side;
  exchange: string;
  quantity: number;
  lotSize?: number | null;
  orderType: OrderType;
  price: number;
  trigger: number;
  ltp?: number;
}

/**
 * Client-side guard for the obvious mistakes. Kite still validates the
 * trigger/price ordering server-side and returns a precise error, so we only
 * enforce what we can be certain about here (positives + lot multiples).
 */
export function validateTicket(s: TicketState): string | null {
  const lot = effectiveLot(s.lotSize);
  if (!Number.isFinite(s.quantity) || s.quantity <= 0) {
    return 'Enter a quantity greater than 0';
  }
  if (lot > 1 && s.quantity % lot !== 0) {
    return `Quantity must be in multiples of ${lot}`;
  }
  if (needsPrice(s.orderType) && !(s.price > 0)) {
    return 'Enter a valid limit price';
  }
  if (needsTrigger(s.orderType) && !(s.trigger > 0)) {
    return 'Enter a valid trigger price';
  }
  return null;
}

// ─── Builders ────────────────────────────────────────────────────────────────

export interface BuildArgs {
  tradingsymbol: string;
  exchange: string;
  side: Side;
  quantity: number;
  product: Product;
  orderType: OrderType;
  price: number;
  trigger: number;
  validity?: Validity;
  validityTtl?: number;   // minutes, when validity === 'TTL'
  variety?: Variety;
  disclosedQty?: number;
  tag?: string;
}

/** Build the body for POST /api/v1/kite/orders. */
export function buildOrderBody(a: BuildArgs): PlaceOrderBody {
  const body: PlaceOrderBody = {
    tradingsymbol: a.tradingsymbol,
    exchange: a.exchange,
    transaction_type: a.side,
    quantity: Math.round(a.quantity),
    order_type: a.orderType,
    product: a.product,
    variety: a.variety ?? 'regular',
    validity: a.validity ?? 'DAY',
  };
  if (needsPrice(a.orderType)) body.price = a.price;
  if (needsTrigger(a.orderType)) body.trigger_price = a.trigger;
  if (a.validity === 'TTL' && a.validityTtl && a.validityTtl > 0) body.validity_ttl = Math.round(a.validityTtl);
  if (a.disclosedQty && a.disclosedQty > 0) body.disclosed_quantity = Math.round(a.disclosedQty);
  if (a.tag) body.tag = a.tag.slice(0, 20);
  return body;
}

// ── Protective GTT (the "gtt" Stoploss / Target row) ─────────────────────────
export interface GttArgs {
  tradingsymbol: string;
  exchange: string;
  entrySide: Side;     // the side of the ENTRY order being protected
  quantity: number;
  product: Product;
  basePrice: number;   // entry/limit price or LTP the % are measured from
  slPct?: number;      // e.g. -5 (below entry for a long)
  tgtPct?: number;     // e.g.  5 (above entry for a long)
}

/**
 * Build a protective GTT for the position the entry order opens. A long is
 * protected by SELL legs (SL below, target above); a short by BUY legs. With
 * both legs it's a two-leg OCO; with one, a single GTT. Prices are tick-rounded.
 * Returns null when there's nothing to protect or no base price.
 */
export function buildProtectionGtt(a: GttArgs): PlaceGttBody | null {
  if (!(a.basePrice > 0)) return null;
  const hasSl = a.slPct != null && a.slPct !== 0;
  const hasTgt = a.tgtPct != null && a.tgtPct !== 0;
  if (!hasSl && !hasTgt) return null;

  const exitSide: Side = a.entrySide === 'BUY' ? 'SELL' : 'BUY';
  const dir = a.entrySide === 'BUY' ? 1 : -1;   // long: +% above, short: mirror
  const slPrice = roundTick(a.basePrice * (1 + dir * (a.slPct ?? 0) / 100));
  const tgtPrice = roundTick(a.basePrice * (1 + dir * (a.tgtPct ?? 0) / 100));
  const leg = (price: number) => ({
    tradingsymbol: a.tradingsymbol, exchange: a.exchange, transaction_type: exitSide,
    quantity: Math.round(a.quantity), order_type: 'LIMIT', product: a.product, price,
  });

  if (hasSl && hasTgt) {
    const pair = [slPrice, tgtPrice].sort((x, y) => x - y);  // Kite needs ascending triggers
    return {
      trigger_type: 'two-leg', tradingsymbol: a.tradingsymbol, exchange: a.exchange,
      last_price: a.basePrice, trigger_values: pair, orders: pair.map((p) => leg(p)),
    };
  }
  const t = hasSl ? slPrice : tgtPrice;
  return {
    trigger_type: 'single', tradingsymbol: a.tradingsymbol, exchange: a.exchange,
    last_price: a.basePrice, trigger_values: [t], orders: [leg(t)],
  };
}

/** Build a single order entry for the /margins/orders calculator. */
export function buildMarginOrder(a: BuildArgs): Record<string, unknown> {
  return {
    exchange: a.exchange,
    tradingsymbol: a.tradingsymbol,
    transaction_type: a.side,
    variety: a.variety ?? 'regular',
    product: a.product,
    order_type: a.orderType,
    quantity: Math.round(a.quantity),
    price: needsPrice(a.orderType) ? a.price : 0,
    trigger_price: needsTrigger(a.orderType) ? a.trigger : 0,
  };
}

/** Pull Required (margin) and charges out of a /margins/orders response row. */
export function parseMargin(resp: any): { total: number; charges: number } | null {
  const row = Array.isArray(resp) ? resp[0] : resp;
  if (!row) return null;
  const total = Number(row.total ?? 0);
  const charges = Number(row?.charges?.total ?? 0);
  if (!Number.isFinite(total)) return null;
  return { total, charges };
}
