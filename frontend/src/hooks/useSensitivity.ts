import { useMutation, useQuery } from '@tanstack/react-query';
import { api } from '../utils/api';

export interface SensitivityResult {
  parameter: string;
  values_tested: number[];
  sharpes: number[];
  best_value: number;
  sensitivity: number;
}

export function useSensitivity(underlying: string) {
  return useQuery<{ results: SensitivityResult[]; computed_at: string; stale_days: number; is_stale: boolean }>({
    queryKey: ['sensitivity-latest', underlying],
    queryFn: () => api.get(`/api/v1/analytics/sensitivity/${underlying}/latest`),
    retry: false,
  });
}

export function useRunSensitivity() {
  return useMutation<SensitivityResult[], Error, { underlying: string }>({
    mutationFn: (req) => api.post('/api/v1/analytics/sensitivity', req),
  });
}
