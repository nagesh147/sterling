import { useQuery } from '@tanstack/react-query';
import { api } from '../utils/api';

export interface PnLSnapshot {
  timestamp_ms: number;
  spot_price: number;
  estimated_pnl: number;
  current_dte: number;
}

export interface PnLHistoryResponse {
  position_id: string;
  snapshots: PnLSnapshot[];
  count: number;
}

export function usePnlHistory(positionId: string) {
  return useQuery<PnLHistoryResponse>({
    queryKey: ['pnl-history', positionId],
    queryFn: () => api.get<PnLHistoryResponse>(`/api/v1/positions/${positionId}/pnl-history`),
    refetchInterval: 30_000,
    enabled: !!positionId,
  });
}
