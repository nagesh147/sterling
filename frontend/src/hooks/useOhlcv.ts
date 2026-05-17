import { useQuery } from '@tanstack/react-query';
import { api } from '../utils/api';

export interface OhlcvCandle {
  time: number;   // unix seconds
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
}

export interface OhlcvResponse {
  symbol: string;
  resolution: string;
  count: number;
  earliest: number | null;
  latest: number | null;
  is_fetching: boolean;
  candles: OhlcvCandle[];
}

export interface OhlcvStatus {
  is_fetching: boolean;
  last_summary: Record<string, number>;
  coverage: Array<{
    symbol: string;
    resolution: string;
    count: number;
    earliest: number;
    latest: number;
  }>;
  supported_symbols: string[];
  supported_resolutions: string[];
  timestamp_ms: number;
}

export const OHLCV_RESOLUTIONS = ['5m', '15m', '30m', '1h', '2h', '4h'] as const;
export type OhlcvResolution = typeof OHLCV_RESOLUTIONS[number];

export function useOhlcv(
  symbol: string,
  resolution: OhlcvResolution,
  limit = 500,
  enabled = true,
) {
  return useQuery<OhlcvResponse>({
    queryKey: ['ohlcv', symbol, resolution, limit],
    queryFn: () =>
      api.get<OhlcvResponse>(
        `/api/v1/ohlcv?symbol=${symbol}&resolution=${resolution}&limit=${limit}`,
      ),
    staleTime: 60_000,      // 1 minute — data is only as fresh as the last fetch
    refetchInterval: 120_000, // re-check every 2 min for new candles
    enabled: enabled && !!symbol,
  });
}

export function useOhlcvStatus() {
  return useQuery<OhlcvStatus>({
    queryKey: ['ohlcv-status'],
    queryFn: () => api.get<OhlcvStatus>('/api/v1/ohlcv/status'),
    staleTime: 30_000,
    refetchInterval: 60_000,
  });
}

export function useTriggerOhlcvFetch() {
  return async (symbol?: string) => {
    const url = symbol
      ? `/api/v1/ohlcv/fetch?symbol=${symbol}`
      : '/api/v1/ohlcv/fetch';
    return api.post<{ status: string }>(url, {});
  };
}
