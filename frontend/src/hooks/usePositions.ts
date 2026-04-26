import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { api } from '../utils/api';
import type { PositionListResponse, PaperPosition } from '../types';

export function usePositions() {
  return useQuery<PositionListResponse>({
    queryKey: ['positions'],
    queryFn: () => api.get<PositionListResponse>('/api/v1/positions'),
    refetchInterval: 15_000,
  });
}

export function useEnterPosition() {
  const qc = useQueryClient();
  return useMutation<PaperPosition, Error, { underlying: string; notes?: string }>({
    mutationFn: ({ underlying, notes = '' }) =>
      api.post<PaperPosition>('/api/v1/positions/enter', { underlying, notes }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['positions'] }),
  });
}

export function useClosePosition() {
  const qc = useQueryClient();
  return useMutation<PaperPosition, Error, { id: string; exit_spot_price: number }>({
    mutationFn: ({ id, exit_spot_price }) =>
      api.post<PaperPosition>(`/api/v1/positions/${id}/close`, { exit_spot_price }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['positions'] }),
  });
}

export function useDeletePosition() {
  const qc = useQueryClient();
  return useMutation<void, Error, string>({
    mutationFn: (id) => api.delete<void>(`/api/v1/positions/${id}`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['positions'] }),
  });
}

export function useCloseAll() {
  const qc = useQueryClient();
  return useMutation<{ closed_count: number; total_realized_pnl_usd: number }, Error, void>({
    mutationFn: () => api.post('/api/v1/positions/close-all'),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['positions'] });
      qc.invalidateQueries({ queryKey: ['portfolio-summary'] });
      qc.invalidateQueries({ queryKey: ['live-pnl'] });
    },
  });
}
