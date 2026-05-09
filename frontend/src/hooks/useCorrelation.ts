import { useQuery } from '@tanstack/react-query';
import { api } from '../utils/api';

export interface CorrelationState {
  matrix: Record<string, number>;
  assets: string[];
  updated_at: number;
}

export function useCorrelation() {
  return useQuery<CorrelationState>({
    queryKey: ['correlation'],
    queryFn: () => api.get<CorrelationState>('/api/v1/risk/correlation'),
    refetchInterval: 60_000,
  });
}
