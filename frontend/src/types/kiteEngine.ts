// Types for the Kite-exclusive triple-SuperTrend options engine.
// Mirrors backend app/engines/triple_supertrend/schemas.py.

export type TrailTarget = 'fast' | 'mid' | 'slow';
export type Moneyness = 'ATM' | 'ITM1' | 'ITM2' | 'ITM3' | 'ITM4' | 'ITM5' | 'OTM1' | 'OTM2' | 'OTM3' | 'OTM4' | 'OTM5';
export type ScanSource = 'spot' | 'derivatives' | 'both';
export type ScanExpiry = 'weekly' | 'monthly';

export interface AlignmentChip {
  fast: number; // +1 / -1 / 0
  mid: number;
  slow: number;
}

export interface OptionLeg {
  moneyness: string; // ATM / ITM1 / ITM2 / OTM1 / OTM2
  option_type: string; // CE / PE
  option_symbol: string;
  strike: number;
  expiry: string;
  lot_size: number | null;
  premium_spot?: number;
  premium_sl?: number;
  token?: number;
  is_active?: boolean; // this contract's SuperTrend still aligned on the latest bar
}

export interface EngineSignalRow {
  underlying: string;
  token: number;
  exchange: string; // option exchange (NFO / BFO)
  regime: 'BULL' | 'BEAR';
  alignment: AlignmentChip;
  direction: 'long' | 'short';
  option_type: 'CE' | 'PE';
  legs: OptionLeg[];
  spot: number;
  stop_loss: number;
  score: number;
  timestamp_ms: number;
  source?: 'spot' | 'derivatives';
  is_active?: boolean; // SuperTrend still aligned on the latest bar (trade running)
  is_fresh?: boolean;  // entered on the latest closed bar (the live "ready now" trigger)
}

export interface SignalsResponse {
  generated_ms: number;
  scanning: boolean;
  scanning_label: string;
  rows: EngineSignalRow[];
  next_scan_ms: number;
  auto_scan: boolean;
  market_open: boolean;
}

export interface ActivityEvent {
  ts_ms: number;
  kind: string; // scan_start | scan_done | order_placed | order_blocked | order_failed | error | info
  message: string;
}

export interface ActivityResponse {
  events: ActivityEvent[];
  scanning: boolean;
  auto_scan: boolean;
  last_scan_ms: number;
  next_scan_ms: number;
  signal_count: number;
  scanning_label: string;
}

export interface SetupPoint {
  time: number; // epoch seconds
  open: number;
  high: number;
  low: number;
  close: number;
}

export interface SetupLine {
  time: number;
  value: number;
}

export interface SetupChart {
  underlying: string;
  candles: SetupPoint[];
  st_fast: SetupLine[];
  st_mid: SetupLine[];
  st_slow: SetupLine[];
  entry_index: number | null;
  trail_target: string;
}

export interface DepthLevel {
  price: number;
  quantity: number;
  orders: number;
}

export interface OptionDetail {
  moneyness: string;
  option_type: string;
  option_symbol: string;
  strike: number;
  expiry: string;
  lot_size: number | null;
  dte: number;
  last_price: number;
  bid: number;
  ask: number;
  iv: number; // decimal
  delta: number;
  gamma: number;
  theta: number;
  vega: number;
  depth_buy: DepthLevel[];
  depth_sell: DepthLevel[];
}

export interface EngineDetailResponse {
  underlying: string;
  token: number;
  exchange: string;
  direction: 'long' | 'short';
  regime: 'BULL' | 'BEAR';
  alignment: AlignmentChip;
  option_type: 'CE' | 'PE';
  triggered_ms: number;
  spot_at_trigger: number;
  spot_now: number;
  stop_loss: number;
  options: OptionDetail[];
}

export interface EngineConfigModel {
  trail_target: TrailTarget;
  strike_moneyness: Moneyness[];
  scan_source: ScanSource;
  scan_expiries: ScanExpiry[];
  scan_indices: string[];
  scan_stocks: string[];
  scan_all_stocks: boolean;
  early_lock: boolean;
  auto_execute: boolean;
}

export interface EngineOrderRequest {
  option_symbol: string;
  exchange: string;
  side: 'BUY' | 'SELL';
  quantity: number;
  order_type?: string;
  product?: string;
}

export interface EngineOrderResponse {
  order_id: string;
  status: string;
  message: string;
}

// ─── Per-contract scan report ──────────────────────────────────────────────
export interface ContractScanEntry {
  underlying: string;
  symbol: string;
  strike: number;
  option_type: 'CE' | 'PE';
  expiry: string;
  moneyness: string;
  bars: number;
  premium_close: number;
  fired: boolean;
  fired_at_ms: number;
  reason: string;
}

export interface ScanReportSummary {
  generated_ms: number;
  scan_source: string;
  indices: string[];
  total_contracts: number;
  charted: number;
  fired: number;
  no_data: number;
  min_bars: number;
  max_bars: number;
  total_ce: number;
  total_pe: number;
  fired_ce: number;
  fired_pe: number;
}

export interface ScanReportResponse {
  summary: ScanReportSummary;
  entries: ContractScanEntry[];
}
