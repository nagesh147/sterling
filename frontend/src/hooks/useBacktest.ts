import { useMutation } from '@tanstack/react-query';
import { api } from '../utils/api';

export interface BacktestBarResult {
  timestamp_ms: number;
  close_1h: number;
  macro_regime: string;
  signal_trend: number;
  all_green: boolean;
  all_red: boolean;
  green_arrow: boolean;
  red_arrow: boolean;
  state: string;
  direction: string;
}

export interface BacktestStats {
  total_bars_evaluated: number;
  bullish_regime_bars: number;
  bearish_regime_bars: number;
  neutral_regime_bars: number;
  green_arrows: number;
  red_arrows: number;
  confirmed_long_setups: number;
  confirmed_short_setups: number;
  early_long_setups: number;
  early_short_setups: number;
  filtered_bars: number;
  idle_bars: number;
}

export interface BacktestResult {
  underlying: string;
  lookback_days: number;
  total_1h_candles: number;
  total_4h_candles: number;
  bars: BacktestBarResult[];
  stats: BacktestStats;
  timestamp_ms: number;
}

export interface BacktestRequest {
  underlying: string;
  lookback_days: number;
  sample_every_n_bars: number;
}

export function useBacktest() {
  return useMutation<BacktestResult, Error, BacktestRequest>({
    mutationFn: (req) => api.post<BacktestResult>('/api/v1/backtest/run', req),
  });
}
