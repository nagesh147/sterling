import { useQuery } from '@tanstack/react-query';
import { api } from '../utils/api';

export interface MtfBreakdown {
  macro_4h: number;
  signal_1h: number;
  execution_15m: number;
  macro_ok: boolean;
  signal_ok: boolean;
  exec_ok: boolean;
  alignment: 'all_aligned' | 'exec_pending' | 'signal_weak' | 'macro_unaligned' | 'no_alignment';
  alignment_label: string;
  exec_mode: string;
}

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
  signal_score?: number;
  signal_strength?: 'STRONG' | 'SIGNAL' | 'NONE';
  track?: string;
  strategy?: 'latest' | 'legacy';
  exec_mode: string | null;
  exec_confidence?: number;
  exec_score?: number;
  regime_score?: number;
  mtf_breakdown?: MtfBreakdown;
  veto_reason?: string | null;
  stop_price?: number | null;
  target_price?: number | null;
  tp_source?: string | null;
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
    refetchInterval: 5_000,
  });
}
