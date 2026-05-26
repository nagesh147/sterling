import { useAppStream } from './useAppStream';

export interface LivePnlEntry {
  position_id: string;
  underlying: string;
  status: string;
  current_spot: number | null;
  entry_spot: number;
  estimated_pnl_usd: number | null;
  realized_pnl_usd: number | null;
  current_dte: number;
  max_risk_usd: number;
  capital_at_risk_pct: number;
  direction: string;
  contracts: number;
  leverage: number;
  entry_timestamp_ms: number;
  entry_price_real: number | null;
  initial_sl: number | null;
  initial_tp: number | null;
  current_sl: number | null;
  current_tp: number | null;
  trail_mode: string | null;
  trail_state: TrailState | null;
  order_id: string | null;
  order_status: string | null;
  mode: string | null;
  structure_type: string;
}

export interface TrailState {
  mode: string;
  current_stop: number;
  highest_seen: number;
  lowest_seen: number;
  partial_25_done: boolean;
  partial_50_done: boolean;
  breakeven_set: boolean;
}

export interface LivePnlResponse {
  positions: LivePnlEntry[];
  total_estimated_pnl_usd: number;
  total_realized_pnl_usd: number;
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
