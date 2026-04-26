import { useQuery } from '@tanstack/react-query';
import { api } from '../utils/api';

export interface LivePnlEntry {
  position_id: string;
  underlying: string;
  status: string;
  current_spot: number | null;
  entry_spot: number;
  estimated_pnl_usd: number | null;
  current_dte: number;
  max_risk_usd: number;
  capital_at_risk_pct: number;
}

export interface LivePnlResponse {
  positions: LivePnlEntry[];
  total_estimated_pnl_usd: number;
  timestamp_ms: number;
}

export function useLivePnl(enabled = true) {
  return useQuery<LivePnlResponse>({
    queryKey: ['live-pnl'],
    queryFn: () => api.get<LivePnlResponse>('/api/v1/positions/pnl-live'),
    refetchInterval: 30_000,
    enabled,
  });
}
