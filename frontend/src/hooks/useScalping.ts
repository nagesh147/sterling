import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { api } from '../utils/api';

// ── Config ──────────────────────────────────────────────────────────────────

export interface ScalpingConfig {
  enable_price_action: boolean;
  enable_smc: boolean;
  enable_ma_crossover: boolean;
  macro_timeframe: string;
  execution_timeframe: string;
  level_touches: number;
  level_tolerance_pct: number;
  pa_lookback_bars: number;
  pa_confirm_bars: number;
  smc_imbalance_ratio: number;
  ma_fast_sma: number;
  ma_slow_ema: number;
  allow_long: boolean;
  allow_short: boolean;
  macro_trend_filter: boolean;
  pa_min_rr: number;
  use_optimized: boolean;
  risk_percent: number;
  max_position_pct: number;
  account_equity: number;
  symbols: string[];
  warmup_bars_4h: number;
  warmup_bars_15m: number;
}

export interface ScalpingConfigResponse { config: ScalpingConfig; }
export interface ScalpingUniverseResponse { symbols: string[]; }

// ── Signal ──────────────────────────────────────────────────────────────────

export interface SupportResistanceLevel {
  underlying: string;
  price: number;
  touches: number;
  first_touch_ts: number;
  last_touch_ts: number;
  level_type: string;
}

export interface ScalpingSignal {
  underlying: string;
  close: number;
  strategy: string;
  direction: string;
  near_level: number | null;
  level_type: string;
  pattern: string;
  reason: string;
  entry: number | null;
  stop_loss: number | null;
  take_profit: number | null;
  tp_source?: string;
  risk_pct: number | null;
  leverage: number | null;
  size_units: number | null;
  notional_usd: number | null;
  entry_ok: boolean;
  executable: boolean;
  timestamp_ms: number;
  error: string | null;
}

export interface ScalpingScanResponse {
  signals: ScalpingSignal[];
  levels: SupportResistanceLevel[];
  count: number;
  armed_count: number;
  timestamp_ms: number;
}

// ── Backtest ────────────────────────────────────────────────────────────────

export interface ScalpingBacktestTrade {
  direction: string;
  strategy: string;
  entry_ts: number;
  exit_ts: number;
  entry_price: number;
  exit_price: number;
  bars_held: number;
  pnl_r: number;
  exit_reason: string;
}

export interface ScalpingBacktestResult {
  underlying: string;
  lookback_days: number;
  bars_evaluated: number;
  config: ScalpingConfig;
  trades: ScalpingBacktestTrade[];
  total_trades: number;
  win_rate: number;
  total_return_pct: number;
  max_drawdown_pct: number;
  timestamp_ms: number;
}

// ── Execute ─────────────────────────────────────────────────────────────────

export interface ScalpingExecuteResponse {
  accepted: boolean;
  mode: string;
  underlying: string;
  strategy: string;
  direction: string;
  size_units: number;
  notional_usd: number;
  entry_price: number | null;
  stop_loss: number | null;
  take_profit: number | null;
  tp_source?: string;
  order_id: string | null;
  paper_position_id: string | null;
  status: string;
  reason: string;
  timestamp_ms: number;
  telegram_alert_sent: boolean;
}

// ── Optimize ──────────────────────────────────────────────────────────────────

export interface OptimizeComboResult {
  params: Record<string, number | boolean>;
  is_pf: number; is_exp: number; n_is: number;
  oos_pf: number; oos_exp: number; n_oos: number;
  total_trades: number; score: number;
}

export interface OptimizeResult {
  combos: OptimizeComboResult[];
  best_params: Record<string, number | boolean>;
  baseline: OptimizeComboResult;
  is_oos_corr: number;
  recommend_change: boolean;
  n_combos: number;
  universe: string[];
  note: string;
}

export interface OptimizeStatus {
  running: boolean;
  progress: string;
  started_ms: number;
  done_ms: number;
  error: string | null;
}

export interface OptimizeResponse {
  status: OptimizeStatus;
  result: OptimizeResult | null;
  optimized_params: Record<string, number | boolean> | null;
}

// ── Hooks ───────────────────────────────────────────────────────────────────

export function useScalpingConfig() {
  return useQuery<ScalpingConfigResponse>({
    queryKey: ['scalping', 'config'],
    queryFn: () => api.get<ScalpingConfigResponse>('/api/v1/scalping/config'),
    staleTime: 60_000,
  });
}

export function useSetScalpingConfig() {
  const qc = useQueryClient();
  return useMutation<ScalpingConfigResponse, Error, ScalpingConfig>({
    mutationFn: (cfg) => api.post<ScalpingConfigResponse>('/api/v1/scalping/config', cfg),
    onSuccess: (data) => {
      qc.setQueryData(['scalping', 'config'], data);
      qc.invalidateQueries({ queryKey: ['scalping', 'signals'] });
    },
  });
}

export function useScalpingUniverse() {
  return useQuery<ScalpingUniverseResponse>({
    queryKey: ['scalping', 'universe'],
    queryFn: () => api.get<ScalpingUniverseResponse>('/api/v1/scalping/universe'),
    staleTime: 300_000,
  });
}

export function useScalpingSignals(armedOnly = false) {
  return useQuery<ScalpingScanResponse>({
    queryKey: ['scalping', 'signals', armedOnly],
    queryFn: () => api.get<ScalpingScanResponse>(`/api/v1/scalping/signals?armed_only=${armedOnly}`),
    refetchInterval: 30_000,
    retry: 1,
  });
}

export function useScalpingBacktest() {
  return useMutation<ScalpingBacktestResult, Error, { underlying: string; lookback_days: number; strategies?: string[]; config?: ScalpingConfig }>({
    mutationFn: (req) => api.post<ScalpingBacktestResult>('/api/v1/scalping/backtest', req),
  });
}

export function useScalpingExecute() {
  return useMutation<ScalpingExecuteResponse, Error, { underlying: string; strategy: string; auto?: boolean }>({
    mutationFn: (req) => api.post<ScalpingExecuteResponse>('/api/v1/scalping/execute', { underlying: req.underlying, strategy: req.strategy, confirm: true, auto: req.auto ?? false }),
  });
}

// Optimizer: poll while a sweep is running so the UI shows live progress + results.
export function useScalpingOptimize() {
  return useQuery<OptimizeResponse>({
    queryKey: ['scalping', 'optimize'],
    queryFn: () => api.get<OptimizeResponse>('/api/v1/scalping/optimize'),
    refetchInterval: (q) => (q.state.data?.status.running ? 3_000 : false),
  });
}

export function useRunScalpingOptimize() {
  const qc = useQueryClient();
  return useMutation<{ status: string }, Error, { days?: number; max_symbols?: number }>({
    mutationFn: (req) => api.post<{ status: string }>(
      `/api/v1/scalping/optimize?days=${req.days ?? 90}&max_symbols=${req.max_symbols ?? 5}`, {}),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['scalping', 'optimize'] }); },
  });
}