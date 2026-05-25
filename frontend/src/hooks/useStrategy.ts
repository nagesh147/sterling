import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { api } from '../utils/api';

// ── Config (mirrors backend TripleSTConfig) ──────────────────────────────────

export type StrategyMode = 'Aggressive' | 'Balanced' | 'Conservative' | 'Momentum';
export type AssetClass = 'Auto-Detect' | 'Large' | 'Mid' | 'Small';
export type HTFSource = 'SuperTrend' | 'EMA' | 'Both';

export interface TripleSTConfig {
  mode: StrategyMode;
  use_quality_score: boolean;
  quality_threshold: number;
  asset_type: AssetClass;
  use_ha: boolean;
  use_volume: boolean;
  use_rsi: boolean;
  use_macd: boolean;
  use_htf: boolean;
  htf_source: HTFSource;
  use_btc_corr: boolean;
  use_regime_filter: boolean;
  use_spike_guard: boolean;
  use_gap_protection: boolean;
  risk_percent: number;
  max_position_pct: number;
  daily_loss_limit: number;
  max_slippage: number;
  warmup_bars: number;
  use_circuit_breaker: boolean;
  consecutive_loss_limit: number;
  use_black_swan: boolean;
  black_swan_pct: number;
  use_dynamic_mode: boolean;
  account_equity: number;
}

export interface ModePreset {
  mode: StrategyMode; min_confirm: number; risk_mult: number;
  be_trigger_r: number; trail_source: string; partials: [number, number][];
}
export interface AssetPreset {
  asset_class: AssetClass; sl_mult: number; tp_mult: number;
  min_adx: number; squeeze_threshold: number; short_modifier: number;
}
export interface ConfigResponse {
  config: TripleSTConfig; mode_presets: ModePreset[]; asset_presets: AssetPreset[];
}

// ── Evaluation ───────────────────────────────────────────────────────────────

export interface STLine { period: number; multiplier: number; value: number; trend: number; }
export interface Quality {
  consensus: number; volume: number; htf: number; regime: number;
  momentum: number; bonus: number; total: number; threshold: number; passed: boolean;
}
export interface FilterView { name: string; passed: boolean; detail: string; }
export interface RegimeView {
  is_compressed: boolean; is_high_vol: boolean; is_trending: boolean;
  is_choppy: boolean; post_squeeze: boolean; adx: number; chop: number;
  bb_ratio: number; label: string;
}
export interface TradePlan {
  direction: string; entry: number; stop_loss: number; take_profit: number;
  r_distance: number; partials: [number, number][]; size_units: number;
  notional_usd: number; risk_usd: number; risk_pct: number; leverage: number; rr: number;
}
export interface StrategyEvaluation {
  underlying: string; timestamp_ms: number; close: number;
  effective_mode: StrategyMode; asset_class: AssetClass;
  direction: 'long' | 'short' | 'none'; raw_long: boolean; raw_short: boolean; arrow: boolean;
  consensus_count: number; supertrends: STLine[];
  quality: Quality; filters: FilterView[]; regime: RegimeView;
  entry_ok: boolean; can_trade: boolean; block_reason: string; reason: string;
  trade_plan: TradePlan | null;
  equity: number; drawdown_pct: number; consecutive_losses: number;
  size_multiplier: number; effective_quality_threshold: number;
  config: TripleSTConfig; warming_up: boolean;
}

// ── Backtest ─────────────────────────────────────────────────────────────────

export interface BacktestStats {
  total_trades: number; wins: number; losses: number; win_rate: number;
  avg_win_r: number; avg_loss_r: number; expectancy_r: number; profit_factor: number;
  max_drawdown_pct: number; sharpe: number; total_return_pct: number;
  long_trades: number; short_trades: number; avg_bars_held: number; final_equity: number;
}
export interface BacktestTrade {
  direction: string; entry_ts: number; exit_ts: number; entry_price: number;
  exit_price: number; bars_held: number; pnl_usd: number; pnl_r: number;
  exit_reasons: string[]; mode: string;
}
export interface BacktestResult {
  underlying: string; lookback_days: number; bars_evaluated: number;
  config: TripleSTConfig; asset_class: AssetClass; stats: BacktestStats;
  trades: BacktestTrade[]; equity_curve: { ts: number; equity: number }[]; timestamp_ms: number;
}

// ── Multi-symbol scan ────────────────────────────────────────────────────────

export interface SignalSummary {
  underlying: string; close: number; direction: 'long' | 'short' | 'none';
  entry_ok: boolean; executable: boolean; arrow: boolean; consensus_count: number;
  quality_total: number; quality_pass: boolean; regime_label: string;
  effective_mode: StrategyMode; asset_class: AssetClass;
  entry: number | null; stop_loss: number | null; take_profit: number | null;
  rr: number | null; risk_pct: number | null; leverage: number | null;
  notional_usd: number | null; size_units: number | null;
  reason: string; timestamp_ms: number; error: string | null;
}
export interface SignalScanResponse {
  signals: SignalSummary[]; count: number; armed_count: number;
  effective_mode: StrategyMode; timestamp_ms: number;
}

export interface ExecuteResponse {
  accepted: boolean; mode: string; underlying: string; direction: string;
  size_units: number; notional_usd: number; entry_price: number | null;
  stop_loss: number | null; take_profit: number | null; order_id: string | null;
  paper_position_id: string | null; status: string; reason: string; timestamp_ms: number;
}

// ── Hooks ────────────────────────────────────────────────────────────────────

export function useStrategyConfig() {
  return useQuery<ConfigResponse>({
    queryKey: ['strategy', 'config'],
    queryFn: () => api.get<ConfigResponse>('/api/v1/strategy/config'),
    staleTime: 60_000,
  });
}

export function useSetStrategyConfig() {
  const qc = useQueryClient();
  return useMutation<ConfigResponse, Error, TripleSTConfig>({
    mutationFn: (cfg) => api.post<ConfigResponse>('/api/v1/strategy/config', cfg),
    onSuccess: (data) => {
      qc.setQueryData(['strategy', 'config'], data);
      qc.invalidateQueries({ queryKey: ['strategy', 'evaluate'] });
    },
  });
}

export function useStrategySignals(armedOnly = false) {
  return useQuery<SignalScanResponse>({
    queryKey: ['strategy', 'signals', armedOnly],
    queryFn: () => api.get<SignalScanResponse>(`/api/v1/strategy/signals?armed_only=${armedOnly}`),
    refetchInterval: 30_000,
    retry: 1,
  });
}

export function useStrategyEvaluate(underlying: string, enabled = true) {
  return useQuery<StrategyEvaluation>({
    queryKey: ['strategy', 'evaluate', underlying],
    queryFn: () => api.get<StrategyEvaluation>(`/api/v1/strategy/evaluate/${underlying}`),
    enabled: enabled && !!underlying,
    refetchInterval: 15_000,
    retry: 1,
  });
}

export function useStrategyBacktest() {
  return useMutation<BacktestResult, Error, { underlying: string; lookback_days: number; config?: TripleSTConfig }>({
    mutationFn: (req) => api.post<BacktestResult>('/api/v1/strategy/backtest', req),
  });
}

export function useStrategyExecute() {
  return useMutation<ExecuteResponse, Error, { underlying: string }>({
    mutationFn: (req) => api.post<ExecuteResponse>('/api/v1/strategy/execute', { underlying: req.underlying, confirm: true }),
  });
}
