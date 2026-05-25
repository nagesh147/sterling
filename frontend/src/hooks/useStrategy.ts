import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { api } from '../utils/api';

// ── Config (mirrors backend TripleSTConfig) ──────────────────────────────────
// Strategy (1D): long = close>SMA & close>EMA & RSI>ADX; exit RSI<ADX. Short = mirror.

export interface TripleSTConfig {
  timeframe: string;
  sma_period: number;
  ema_period: number;
  rsi_period: number;
  adx_period: number;
  allow_long: boolean;
  allow_short: boolean;
  atr_period: number;
  sl_atr_mult: number;
  risk_percent: number;
  max_position_pct: number;
  max_slippage: number;
  warmup_bars: number;
  account_equity: number;
}

export interface ConfigResponse {
  config: TripleSTConfig;
}

// ── Evaluation ───────────────────────────────────────────────────────────────

export interface TradePlan {
  direction: string; entry: number; stop_loss: number; r_distance: number;
  size_units: number; notional_usd: number; risk_usd: number; risk_pct: number; leverage: number;
}
export interface StrategyEvaluation {
  underlying: string; timestamp_ms: number; close: number; timeframe: string;
  direction: 'long' | 'short' | 'none';
  sma: number; ema: number; rsi: number; adx: number;
  above_sma: boolean; above_ema: boolean; rsi_gt_adx: boolean;
  long_ok: boolean; short_ok: boolean;
  entry_ok: boolean; executable: boolean; can_trade: boolean; block_reason: string; reason: string;
  trade_plan: TradePlan | null;
  equity: number; config: TripleSTConfig; warming_up: boolean;
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
  exit_price: number; bars_held: number; pnl_usd: number; pnl_r: number; exit_reason: string;
}
export interface BacktestResult {
  underlying: string; lookback_days: number; bars_evaluated: number;
  config: TripleSTConfig; stats: BacktestStats;
  trades: BacktestTrade[]; equity_curve: { ts: number; equity: number }[]; timestamp_ms: number;
}

// ── Multi-symbol scan ────────────────────────────────────────────────────────

export interface SignalSummary {
  underlying: string; close: number; direction: 'long' | 'short' | 'none';
  entry_ok: boolean; executable: boolean;
  sma: number; ema: number; rsi: number; adx: number;
  above_sma: boolean; above_ema: boolean; rsi_gt_adx: boolean;
  entry: number | null; stop_loss: number | null; r_distance: number | null;
  risk_pct: number | null; leverage: number | null;
  notional_usd: number | null; size_units: number | null;
  reason: string; timestamp_ms: number; error: string | null;
}
export interface SignalScanResponse {
  signals: SignalSummary[]; count: number; armed_count: number; timestamp_ms: number;
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
      qc.invalidateQueries({ queryKey: ['strategy', 'signals'] });
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
