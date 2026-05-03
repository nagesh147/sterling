import { useQuery } from '@tanstack/react-query';
import { api } from '../utils/api';

export interface OHLCVBar {
  time: number;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
}

const TF_SECONDS: Record<string, number> = {
  '1m': 60, '5m': 300, '15m': 900,
  '1H': 3600, '4H': 14400, 'D': 86400,
};

export function useCandles(underlying: string, tf: string, limit = 300) {
  const refetchMs = Math.max(30_000, ((TF_SECONDS[tf] ?? 900) / 2) * 1000);
  return useQuery<OHLCVBar[]>({
    queryKey: ['candles', underlying, tf, limit],
    queryFn: () =>
      api.get<OHLCVBar[]>(`/api/v1/candles/${underlying}?tf=${tf}&limit=${limit}`),
    refetchInterval: refetchMs,
    staleTime: refetchMs,
    enabled: !!underlying,
  });
}
