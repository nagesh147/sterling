import { useEffect } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { api } from '../utils/api';
import { useReplayActive as useSimActive } from './useReplayStore';

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
  profile?: string;
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

export type GrokSignalStatus = 'open' | 'ready' | 'pending' | 'watching';

/**
 * Single source of truth for Grok/directional signal status, shared by the
 * GrokTab status-filter counts and the GrokSignalPane rows so the two can
 * never drift apart.
 *
 * Directional signals carry a `state` (TradeState) — not the `entry_ok` flag
 * the Sterling engine emits — so the ready/pending split keys off that:
 *   ENTRY_ARMED_*   -> ready    (armed, actionable now; auto-exec eligible)
 *   *_SETUP_ACTIVE  -> pending  (setup forming, not yet armed)
 *   anything else   -> watching (IDLE / FILTERED / NONE)
 * A live position on the same underlying+direction takes precedence -> open.
 */
export function getSignalStatus(s: SignalItem, activePositions: any[] = []): GrokSignalStatus {
  if (activePositions.some((p: any) => p.underlying === s.underlying && p.direction === s.direction)) return 'open';
  const st = String(s.state || '').toUpperCase();
  if (st.startsWith('ENTRY_ARMED')) return 'ready';
  if (st.endsWith('SETUP_ACTIVE')) return 'pending';
  return 'watching';
}

// Index underlyings parked out of the Grok tab for now (crypto-only view).
const GROK_HIDDEN_UNDERLYINGS = new Set(['NIFTY', 'BANKNIFTY']);

/** Grok-tab visible signal set — applied identically to counts and rows. */
export function visibleGrokSignals(signals: SignalItem[] = []): SignalItem[] {
  return signals.filter((s) => !GROK_HIDDEN_UNDERLYINGS.has((s.underlying || '').toUpperCase()));
}

export function useSignals() {
  const queryClient = useQueryClient();
  const isSimActive = useSimActive();

  useEffect(() => {
    const handleSimStart = () => {
      queryClient.refetchQueries({ queryKey: ['signals-all'] });
    };
    window.addEventListener('sterling-simulation-start', handleSimStart);
    return () => window.removeEventListener('sterling-simulation-start', handleSimStart);
  }, [queryClient]);

  return useQuery<SignalsResponse>({
    queryKey: ['signals-all'],
    queryFn: () => api.get<SignalsResponse>('/api/v1/directional/signals'),
    refetchInterval: isSimActive ? 300 : 3_000,
  });
}
