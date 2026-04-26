import { useQuery } from '@tanstack/react-query';
import { api } from '../utils/api';

export interface ArrowEvent {
  underlying: string;
  arrow_type: 'green' | 'red';
  spot_price: number;
  direction: string;
  state: string;
  source: string;
  timestamp_ms: number;
}

export interface ArrowResponse {
  underlying: string;
  arrows: ArrowEvent[];
  count: number;
}

export function useArrows(underlying: string) {
  return useQuery<ArrowResponse>({
    queryKey: ['arrows', underlying],
    queryFn: () =>
      api.get<ArrowResponse>(`/api/v1/directional/arrows/${underlying}`),
    refetchInterval: 30_000,
    enabled: !!underlying,
  });
}

export function useAllArrows() {
  return useQuery<ArrowResponse>({
    queryKey: ['arrows-all'],
    queryFn: () => api.get<ArrowResponse>('/api/v1/directional/arrows'),
    refetchInterval: 30_000,
  });
}
