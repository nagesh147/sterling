import { useMutation, useQuery } from '@tanstack/react-query';
import { api } from '../utils/api';

export interface WalkForwardWindowReport {
  sharpe: number;
  max_drawdown: number;
  win_rate: number;
  total_trades: number;
  regime_breakdown: Record<string, { trade_count: number; win_rate: number; sharpe_proxy: number; avg_pnl: number }>;
}

export interface WalkForwardWindow {
  window_idx: number;
  train_start: number;
  test_start: number;
  test_end: number;
  report: WalkForwardWindowReport;
  best_threshold: number;
  equity_curve: number[];
}

export interface WalkForwardResult {
  underlying: string;
  windows: WalkForwardWindow[];
  aggregate_report: WalkForwardWindowReport;
  recommended_threshold: number;
  regime_sharpes: Record<string, number>;
  oos_equity_curve: number[];
  run_at?: string;
  oos_sharpe?: number;
  timestamp_ms?: number;
}

export interface WalkForwardRequest {
  underlying: string;
  train_bars?: number;
  test_bars?: number;
  step_bars?: number;
}

export function useWalkForward(underlying: string) {
  return useQuery<WalkForwardResult>({
    queryKey: ['walk-forward-latest', underlying],
    queryFn: () => api.get<WalkForwardResult>(`/api/v1/analytics/walk-forward/${underlying}/latest`),
    retry: false,
  });
}

export function useRunWalkForward() {
  return useMutation<WalkForwardResult, Error, WalkForwardRequest>({
    mutationFn: (req) => api.post<WalkForwardResult>('/api/v1/analytics/walk-forward', req),
  });
}
