import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { api } from '../utils/api';

export interface ScoringWeights {
  regime: number;
  signal: number;
  execution: number;
  dte: number;
  health: number;
  risk_reward: number;
}

const KEY = ['scoring-weights'];

export function useScoringWeights() {
  return useQuery<ScoringWeights>({
    queryKey: KEY,
    queryFn: () => api.get<ScoringWeights>('/api/v1/config/scoring-weights'),
    staleTime: 60_000,
  });
}

export function useUpdateScoringWeights() {
  const qc = useQueryClient();
  return useMutation<ScoringWeights, Error, ScoringWeights>({
    mutationFn: (body) => api.put<ScoringWeights>('/api/v1/config/scoring-weights', body),
    onSuccess: (data) => qc.setQueryData(KEY, data),
  });
}

export function useResetScoringWeights() {
  const qc = useQueryClient();
  return useMutation<ScoringWeights, Error, void>({
    mutationFn: () => api.post<ScoringWeights>('/api/v1/config/scoring-weights/reset'),
    onSuccess: (data) => qc.setQueryData(KEY, data),
  });
}
