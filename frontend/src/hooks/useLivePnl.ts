import { useAppStream } from './useAppStream';

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

export function useLivePnl(_enabled = true) {
  const { data, status } = useAppStream<LivePnlResponse>('pnl');
  return {
    data: data ?? undefined,
    isLoading: status === 'connecting' && data == null,
    isError: false,
  };
}
