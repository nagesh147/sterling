import { useQuery, useMutation } from '@tanstack/react-query';
import { api } from '../utils/api';

export interface DrawdownBreakerState {
  state: 'clear' | 'warning' | 'halt' | 'reset';
  current_drawdown: number;
  peak_value: number;
  current_value: number;
  thresholds: { warn: number; halt: number; reset: number };
  size_multiplier: number;
  timestamp_ms?: number;
}

export function useDrawdownBreaker() {
  return useQuery<DrawdownBreakerState>({
    queryKey: ['dd-circuit-breaker'],
    queryFn: () => api.get<DrawdownBreakerState>('/api/v1/risk/circuit-breaker'),
    refetchInterval: 10_000,
  });
}

export function useResetDrawdownBreaker() {
  return useMutation<{ state: string }, Error, void>({
    mutationFn: () => api.post('/api/v1/risk/circuit-breaker/reset', { confirm: true }),
  });
}
