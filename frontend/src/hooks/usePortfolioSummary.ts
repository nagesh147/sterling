import { useQuery } from '@tanstack/react-query';
import { api } from '../utils/api';

export interface PortfolioSummary {
  open_count: number;
  partially_closed_count: number;
  closed_count: number;
  total_positions: number;
  total_open_risk_usd: number;
  total_realized_pnl_usd: number;
  largest_open_risk_usd: number;
  underlyings_open: string[];
  avg_capital_at_risk_pct: number;
  timestamp_ms: number;
}

export function usePortfolioSummary() {
  return useQuery<PortfolioSummary>({
    queryKey: ['portfolio-summary'],
    queryFn: () => api.get<PortfolioSummary>('/api/v1/positions/summary'),
    refetchInterval: 10_000,
    refetchOnWindowFocus: true,
  });
}
