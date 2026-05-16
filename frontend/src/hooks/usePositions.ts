import { useMutation, useQueryClient } from '@tanstack/react-query';
import { useMemo } from 'react';
import { api } from '../utils/api';
import { useAppStream } from './useAppStream';
import type { PositionListResponse, PaperPosition } from '../types';

/**
 * usePositions — SSE-driven position list.
 *
 * Replaces 10s REST polling with the 'positions' SSE event (5s backend push).
 * Mutations (enter/close/delete) still use REST; on success, the next SSE
 * tick (≤5s) delivers the updated list automatically.
 *
 * The `mode` filter is applied client-side since the SSE stream delivers all positions.
 */
export function usePositions(mode?: 'paper' | 'live') {
  const { data: streamData, status } = useAppStream<PositionListResponse>('positions');

  const data = useMemo<PositionListResponse | undefined>(() => {
    if (!streamData) return undefined;
    if (!mode) return streamData;
    const filtered = streamData.positions.filter(p =>
      mode === 'paper' ? p.is_paper : !p.is_paper
    );
    return {
      ...streamData,
      positions: filtered,
      open_count: filtered.filter(p => p.status === 'open' || p.status === 'partially_closed').length,
      partially_closed_count: filtered.filter(p => p.status === 'partially_closed').length,
      closed_count: filtered.filter(p => p.status === 'closed').length,
    };
  }, [streamData, mode]);

  return {
    data,
    isLoading: status === 'connecting' && data == null,
    isError: false,
    status,
  };
}

export function useEnterPosition() {
  const qc = useQueryClient();
  return useMutation<PaperPosition, Error, { underlying: string; notes?: string; structure_rank?: number }>({
    mutationFn: ({ underlying, notes = '', structure_rank = 0 }) =>
      api.post<PaperPosition>('/api/v1/positions/enter', { underlying, notes, structure_rank }),
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
