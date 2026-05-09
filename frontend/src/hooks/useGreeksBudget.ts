import { useQuery } from '@tanstack/react-query';
import { api } from '../utils/api';

export interface GreeksBudgetState {
  net_delta: number;
  net_vega: number;
  net_theta: number;
  budget: { max_net_delta: number; max_net_vega: number; max_net_theta: number };
  within_limits: boolean;
  open_positions: number;
  timestamp_ms: number;
}

export function useGreeksBudget() {
  return useQuery<GreeksBudgetState>({
    queryKey: ['greeks-budget'],
    queryFn: () => api.get<GreeksBudgetState>('/api/v1/risk/greeks'),
    refetchInterval: 30_000,
  });
}
