import { useQuery } from '@tanstack/react-query';
import { api } from '../utils/api';

export interface TrailStopState {
  stop: number | null;
  mode: string | null;
  highest_seen: number | null;
  partial_25_done: boolean;
  partial_50_done: boolean;
  stop_moved_last_check: boolean;
}

export function useTrailStop(positionId: string | null) {
  return useQuery<TrailStopState>({
    queryKey: ['trail-stop', positionId],
    queryFn: () => api.get<TrailStopState>(`/api/v1/positions/${positionId}/trail-stop`),
    enabled: !!positionId,
    refetchInterval: 30_000,
  });
}
