// Types for the Kite-exclusive triple-SuperTrend options engine.
// Mirrors backend app/engines/triple_supertrend/schemas.py.

export type TrailTarget = 'fast' | 'mid' | 'slow';
export type Moneyness = 'ATM' | 'ITM1' | 'ITM2' | 'ITM3' | 'ITM4' | 'ITM5' | 'ITM10' | 'ITM15' | 'ITM20' | 'OTM1' | 'OTM2' | 'OTM3' | 'OTM4' | 'OTM5';
export type ScanSource = 'spot' | 'derivatives' | 'both';
export type ScanExpiry = 'weekly' | 'monthly';
export type Vehicle = 'otm_options' | 'deep_itm_options' | 'futures';
export type DeepItmMoneyness = 'ITM5' | 'ITM10' | 'ITM15' | 'ITM20';

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
  adx?: number | null;      // ADX at signal time (trend strength, 0–100)
  atr_pct?: number | null;  // ATR percentile at signal time (volatility rank)
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
  engine_enabled: boolean;
  trail_target: TrailTarget;
  strike_moneyness: Moneyness[];
  scan_source: ScanSource;
  scan_expiries: ScanExpiry[];
  scan_expiries_indices?: ScanExpiry[] | null;
  scan_expiries_stocks?: ScanExpiry[] | null;
  scan_indices: string[];
  scan_stocks: string[];
  scan_all_stocks: boolean;
  early_lock: boolean;
  auto_execute: boolean;
  // Per-trade risk sizing (workstream F)
  risk_sizing: boolean;
  risk_pct: number;
  max_lots: number;
  // Protective stop mode (workstreams C/D)
  stop_mode: 'broker' | 'monitor' | 'both';
  // ── Directional mode (additive, opt-in) ────────────────────────────────
  directional_mode: boolean;
  vehicle: Vehicle;
  enabled_vehicles: Vehicle[];
  itm_depth: DeepItmMoneyness | null;
  target_delta: number | null;
  futures_expiry: 'near' | 'next';
  adx_min: number | null;
  atr_pct_min: number | null;
  wire_risk_infra: boolean;
}

// ─── Options backtest (workstream H) ─────────────────────────────────────────
export type BacktestDataMode = 'synthetic' | 'real' | 'both';

export interface BacktestRequest {
  symbol: string;
  data_mode: BacktestDataMode;
  trail_target: TrailTarget;
  lookback_bars: number;
  starting_capital: number;
  qty: number;
  iv: number;
  dte_days: number;
  moneyness_offset_pct: number;
  slippage_pct?: number | null;
  brokerage_per_order?: number | null;
}

export interface BacktestTrade {
  entry_ms: number;
  exit_ms: number;
  direction: string;
  entry_premium: number;
  exit_premium: number;
  qty: number;
  gross_pnl: number;
  costs: number;
  net_pnl: number;
  bars_held: number;
  exit_reason: string;
}

export interface BacktestStats {
  trades: number;
  wins: number;
  losses: number;
  win_rate: number;
  gross_pnl: number;
  total_costs: number;
  net_pnl: number;
  profit_factor: number;
  expectancy: number;
  avg_win: number;
  avg_loss: number;
  max_drawdown: number;
  sharpe: number;
  return_pct: number;
  final_capital: number;
}

export interface BacktestRun {
  mode: string;
  caveat: string;
  trades: BacktestTrade[];
  equity_curve: number[];
  stats: BacktestStats;
}

export interface BacktestResponse {
  symbol: string;
  data_mode: string;
  generated_ms: number;
  runs: BacktestRun[];
  bs_vs_real_drift_pct?: number | null;
  notes: string[];
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

// ─── Stock registry ────────────────────────────────────────────────────────
export type LiquidityLevel = 'Very High' | 'High' | 'Good' | 'Moderate' | 'Moderate-Good';

export interface StockEntry {
  name: string;
  label: string;
  liquidity: LiquidityLevel;
  volatility: string;
  indices: string;
  why: string;
}

export interface LiquidityGroup {
  liquidity: string;
  stocks: StockEntry[];
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

// ─── Engine open positions ────────────────────────────────────────────────────
export type EngineVehicle = 'otm_options' | 'deep_itm_options' | 'futures';

export interface EngineOpenPosition {
  symbol: string;
  exchange: string;
  token: number;
  qty: number;
  lot_size: number;
  entry_premium: number;
  fill_price: number;
  stop_premium: number;
  status: string;
  direction: 'long' | 'short';
  vehicle: EngineVehicle;
  underlying: string;
  opened_ms: number;
  exit_reason: string;
  order_id: string;
}

export interface OpenPositionsResponse {
  positions: EngineOpenPosition[];
}
