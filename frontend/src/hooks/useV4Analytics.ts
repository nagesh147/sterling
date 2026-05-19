import { useQuery } from '@tanstack/react-query';
import { api } from '../utils/api';

export interface V4AnalyticsData {
  ofi: number;
  unrealized_pnl: number;
  drift_bps: number;
}

export function useV4Analytics(symbol: string) {
  return useQuery<V4AnalyticsData>({
    queryKey: ['v4-analytics', symbol],
    // The backend might not have this specific REST endpoint yet,
    // but the websocket stream will populate these values immediately.
    // We provide a fallback object so the UI doesn't crash if the 404 occurs.
    queryFn: async () => {
      try {
        return await api.get<V4AnalyticsData>(`/api/v1/stream/analytics/${symbol}`);
      } catch (error) {
        return {
          ofi: 0,
          unrealized_pnl: 0,
          drift_bps: 0
        };
      }
    },
    refetchInterval: 60_000,
  });
}
