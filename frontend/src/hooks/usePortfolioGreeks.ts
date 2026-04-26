import { useQuery } from '@tanstack/react-query';
import { api } from '../utils/api';

export interface PortfolioGreeks {
  total_delta: number;
  net_directional_exposure: 'bullish' | 'bearish' | 'neutral';
  open_positions: number;
  timestamp_ms: number;
}

export function usePortfolioGreeks() {
  return useQuery<PortfolioGreeks>({
    queryKey: ['portfolio-greeks'],
    queryFn: () => api.get<PortfolioGreeks>('/api/v1/positions/greeks'),
    refetchInterval: 15_000,
  });
}
