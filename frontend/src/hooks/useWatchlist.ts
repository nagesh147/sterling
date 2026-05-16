import { useAppStream } from './useAppStream';

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
  daily_change_pct?: number | null;
  error?: string;
  timestamp_ms: number;
}

export interface WatchlistResponse {
  items: WatchlistItem[];
  count: number;
  timestamp_ms: number;
}

export function useWatchlist() {
  const { data, status } = useAppStream<WatchlistResponse>('watchlist');
  return {
    data: data ?? undefined,
    isLoading: status === 'connecting' && data == null,
    isError: false,
    status,
    // React Query compat: surface the backend timestamp as dataUpdatedAt
    dataUpdatedAt: data?.timestamp_ms ?? 0,
  };
}
