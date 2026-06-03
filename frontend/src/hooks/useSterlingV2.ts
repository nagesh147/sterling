import { useQuery } from '@tanstack/react-query';
import { api } from '../utils/api';

export interface V2Config {
  enabled: boolean;
  paper_only: boolean;
  auto_execute: boolean;
}

export function useV2Config() {
  return useQuery<V2Config>({
    queryKey: ['sterling-v2', 'config'],
    queryFn: () => api.get<V2Config>('/api/v1/sterling-v2/config'),
  });
}

export interface V2Signal {
  symbol: string;
  tf: string;
  strategy: string;
  side: number; // +1 long, -1 short, 0 none
  entry: number;
  stop: number | null;
  target: number | null;
  regime_ok: boolean;
  conviction: number;
  bar_time: string;
}

export interface V2SignalsResponse {
  signals: V2Signal[];
  paper_only: boolean;
  auto_execute: boolean;
}

export function useV2Signals(enabled: boolean) {
  return useQuery<V2SignalsResponse>({
    queryKey: ['sterling-v2', 'signals'],
    queryFn: () => api.get<V2SignalsResponse>('/api/v1/sterling-v2/signals'),
    enabled,
    refetchInterval: 60_000,
  });
}

export interface V2SymbolMetrics {
  trades: number;
  win: number;
  pf: number;
  sharpe: number;
  net: number;
  max_dd: number;
  expectancy: number;
  trades_per_year: number;
}

export interface V2BacktestResponse {
  tf: string;
  strategy: string;
  adx_min: number;
  per_symbol: Record<string, V2SymbolMetrics>;
  portfolio: {
    net: number;
    max_dd: number;
    sharpe: number;
    weights: Record<string, number>;
  };
  paper_only: boolean;
}

export function useV2Backtest(enabled: boolean) {
  return useQuery<V2BacktestResponse>({
    queryKey: ['sterling-v2', 'backtest'],
    queryFn: () => api.get<V2BacktestResponse>('/api/v1/sterling-v2/backtest'),
    enabled,
    staleTime: 5 * 60_000,
  });
}
