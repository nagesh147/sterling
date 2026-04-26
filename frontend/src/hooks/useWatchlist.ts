import { useQuery } from '@tanstack/react-query';
import { api } from '../utils/api';

export interface WatchlistItem {
  underlying: string;
  has_options: boolean;
  state: string;
  direction: string;
  macro_regime?: string;
  signal_trend?: number;
  ivr?: number;
  ivr_band: string;
  score_long?: number;
  score_short?: number;
  spot_price?: number;
  error?: string;
  timestamp_ms: number;
}

export interface WatchlistResponse {
  items: WatchlistItem[];
  count: number;
  timestamp_ms: number;
}

export function useWatchlist() {
  return useQuery<WatchlistResponse>({
    queryKey: ['watchlist'],
    queryFn: () => api.get<WatchlistResponse>('/api/v1/directional/watchlist'),
    refetchInterval: 30_000,
  });
}
