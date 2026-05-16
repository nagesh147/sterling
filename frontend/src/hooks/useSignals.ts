import { useQuery } from '@tanstack/react-query';
import { api } from '../utils/api';

export interface SignalItem {
  underlying: string;
  has_options: boolean;
  spot_price: number | null;
  ivr: number | null;
  green_arrow: boolean;
  red_arrow: boolean;
  state: string;
  direction: string;
  regime: string;
  score_long: number;
  score_short: number;
  exec_mode: string | null;
  exec_confidence?: number;
  stop_price?: number | null;
  target_price?: number | null;
  st_values?: number[];
  atr_percentile?: number;
  adx?: number;
  rsi?: number;
  squeezed?: boolean;
  atr?: number;
  stop_atr_mult?: number;
  // Actionable trade parameters
  rec_leverage?: number;
  futures_symbol?: string;
  opt_strike?: number | null;
  opt_type?: string | null;
  opt_expiry?: string | null;
  opt_dte?: number | null;
  opt_symbol?: string | null;
  fresh: boolean;
  timestamp_ms: number;
  signal_id?: string | null;
}

export interface SignalsResponse {
  signals: SignalItem[];
  count: number;
  timestamp_ms: number;
}

export function useSignals() {
  return useQuery<SignalsResponse>({
    queryKey: ['signals-all'],
    queryFn: () => api.get<SignalsResponse>('/api/v1/directional/signals'),
    refetchInterval: 15_000,
  });
}
