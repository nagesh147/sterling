import { useQuery } from '@tanstack/react-query';
import { api } from '../utils/api';

export interface RegimeTrendBar {
  timestamp_ms: number;
  close: number;
  ema50: number;
  is_bullish: boolean;
  regime: 'bullish' | 'bearish' | 'neutral';
}

export interface RegimeTrendResponse {
  underlying: string;
  bars: RegimeTrendBar[];
  count: number;
}

export function useRegimeTrend(underlying: string, nBars = 30) {
  return useQuery<RegimeTrendResponse>({
    queryKey: ['regime-trend', underlying, nBars],
    queryFn: () =>
      api.get<RegimeTrendResponse>(
        `/api/v1/directional/regime-trend/${underlying}?n_bars=${nBars}`
      ),
    refetchInterval: 60_000,
    enabled: !!underlying,
  });
}
