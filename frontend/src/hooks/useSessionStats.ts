import { useQuery } from '@tanstack/react-query';
import { api } from '../utils/api';

export interface SessionStats {
  green_arrows: number;
  red_arrows: number;
  total_arrows: number;
  alerts_active: number;
  alerts_triggered: number;
  alerts_dismissed: number;
  run_once_total: number;
  confirmed_long_setups: number;
  confirmed_short_setups: number;
  paper_positions_open: number;
  paper_positions_partially_closed: number;
  paper_positions_closed: number;
  underlyings_with_arrows: string[];
  timestamp_ms: number;
}

export function useSessionStats() {
  return useQuery<SessionStats>({
    queryKey: ['session-stats'],
    queryFn: () => api.get<SessionStats>('/api/v1/stats/session'),
    refetchInterval: 15_000,
  });
}
