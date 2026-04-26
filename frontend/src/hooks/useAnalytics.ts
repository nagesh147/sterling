import { useQuery } from '@tanstack/react-query';
import { api } from '../utils/api';

export interface TradeAnalytics {
  total_closed: number;
  winners: number;
  losers: number;
  win_rate_pct: number;
  avg_pnl_usd: number;
  avg_winner_usd: number;
  avg_loser_usd: number;
  best_trade_usd: number;
  worst_trade_usd: number;
  total_realized_pnl_usd: number;
  profit_factor: number;
  timestamp_ms: number;
}

export function useAnalytics() {
  return useQuery<TradeAnalytics>({
    queryKey: ['trade-analytics'],
    queryFn: () => api.get<TradeAnalytics>('/api/v1/positions/analytics'),
    refetchInterval: 15_000,
  });
}
