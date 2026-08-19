export type OrbSignalState = 'WATCHING' | 'SIGNAL' | 'SIGNAL_UNRESOLVED' | 'REJECTED' | 'ERROR';

export interface OrbSignalCandidate {
  symbol: string;
  kind?: string;
  status?: string;
  signal: {
    direction: 'LONG' | 'SHORT' | 'NONE';
    timestamp?: string;
    spot?: number;
    orb_high?: number;
    orb_low?: number;
    vwap?: number;
    atr?: number;
    volume_ratio?: number;
    confidence?: number;
    reason?: string;
  };
  option?: {
    symbol: string;
    strike: number;
    expiry: string;
    option_type: 'CE' | 'PE';
    ltp: number;
    bid: number;
    ask: number;
    lot_size: number;
    volume: number;
    open_interest: number;
  } | null;
  trade_plan?: {
    entry_premium: number;
    stop_premium: number;
    target_premium: number;
    quantity: number;
    risk_inr: number;
  } | null;
  data_source?: 'kite' | 'truedata';
  quote_age_s?: number | null;
}

export interface OrbFeedEntry {
  id: string;
  strategy: 'ORB';
  underlying: string;
  direction: 'long' | 'short';
  state: OrbSignalState;
  spot: number | null;
  orbHigh: number | null;
  orbLow: number | null;
  vwap: number | null;
  atr: number | null;
  volumeRatio: number | null;
  optionSymbol: string | null;
  optionStrike: number | null;
  optionType: 'CE' | 'PE' | null;
  optionExpiry: string | null;
  optionPremium: number | null;
  stopPremium: number | null;
  targetPremium: number | null;
  quantity: number | null;
  riskInr: number | null;
  dataSource: 'kite' | 'truedata' | null;
  quoteAgeS: number | null;
  reason: string | null;
  timestamp: string | null;
}

function stateOf(c: OrbSignalCandidate): OrbSignalState {
  const s = (c.status || '').toUpperCase();
  if (s === 'ERROR') return 'ERROR';
  if (s === 'REJECTED' || s === 'LIQUIDITY_REJECTED') return 'REJECTED';
  if (c.signal.direction === 'NONE') return 'WATCHING';
  if (!c.option || !c.trade_plan) return 'SIGNAL_UNRESOLVED';
  return 'SIGNAL';
}

export function toOrbFeedEntry(c: OrbSignalCandidate, index = 0): OrbFeedEntry {
  const signal = c.signal;
  const plan = c.trade_plan;
  const option = c.option;
  const state = stateOf(c);
  const direction = signal.direction === 'SHORT' ? 'short' : 'long';
  const key = `${c.symbol}:${signal.timestamp || 'live'}:${signal.direction}:${option?.symbol || 'none'}`;
  return {
    id: `ORB-${key}-${index}`,
    strategy: 'ORB',
    underlying: c.symbol,
    direction,
    state,
    spot: signal.spot ?? null,
    orbHigh: signal.orb_high ?? null,
    orbLow: signal.orb_low ?? null,
    vwap: signal.vwap ?? null,
    atr: signal.atr ?? null,
    volumeRatio: signal.volume_ratio ?? null,
    optionSymbol: option?.symbol ?? null,
    optionStrike: option?.strike ?? null,
    optionType: option?.option_type ?? null,
    optionExpiry: option?.expiry ?? null,
    optionPremium: option?.ltp ?? plan?.entry_premium ?? null,
    stopPremium: plan?.stop_premium ?? null,
    targetPremium: plan?.target_premium ?? null,
    quantity: plan?.quantity ?? null,
    riskInr: plan?.risk_inr ?? null,
    dataSource: c.data_source ?? null,
    quoteAgeS: c.quote_age_s ?? null,
    reason: signal.reason ?? null,
    timestamp: signal.timestamp ?? null,
  };
}

export function toOrbFeedEntries(payload: unknown): OrbFeedEntry[] {
  if (!payload || typeof payload !== 'object') return [];
  const p = payload as Record<string, unknown>;
  const rows = Array.isArray(p.candidates) ? p.candidates : Array.isArray(p.signals) ? p.signals : [];
  return rows.filter((x): x is OrbSignalCandidate => !!x && typeof x === 'object' && typeof (x as any).symbol === 'string' && !!(x as any).signal).map((x, i) => toOrbFeedEntry(x, i));
}
