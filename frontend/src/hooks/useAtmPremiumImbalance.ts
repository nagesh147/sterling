import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { api } from '../utils/api';

const KEY = ['atm-premium-imbalance-config'];
const SNAPSHOT_KEY = ['atm-premium-imbalance-snapshot'];

export type QuoteMode = 'COMPATIBILITY' | 'SYNCHRONIZED' | 'EXECUTABLE';
export type EntryPricePolicy =
  | 'MARKETABLE_ASK' | 'PERCENT_THROUGH' | 'MANUAL_FILE'
  | 'FIRST_TICK_PERCENT' | 'FIRST_TICK_PLUS_BUFFER';
export type ExitPolicy = 'FIXED_POINT_TARGET' | 'PREMIUM_CONVERGENCE';
export type ProtectionMode = 'NONE' | 'RESTING_TARGET_LIMIT' | 'GTT';
export type FirstTickSource = 'SESSION_TICK' | 'OFFICIAL_OPEN';
export type ExpiryPolicy = 'SAME_DAY' | 'NEAREST' | 'NEXT' | 'EXPLICIT';

export interface AtmPremiumImbalanceConfig {
  enabled: boolean;
  underlying: string;
  expiry_policy: ExpiryPolicy;
  explicit_expiry: string;
  strike_policy: string;
  session_start: string;
  session_end: string;
  quote_mode: QuoteMode;
  max_quote_age_ms: number;
  max_ce_pe_skew_ms: number;
  signal_mode: string;
  minimum_difference: number;
  minimum_difference_percent: number;
  entry_price_policy: EntryPricePolicy;
  require_session_origin_tick: boolean;
  first_tick_source: FirstTickSource;
  entry_buffer_points: number;
  entry_through_pct: number;
  manual_price_file: string;
  max_entry_attempts: number;
  entry_attempt_timeout_ms: number;
  exit_policy: ExitPolicy;
  protection_mode: ProtectionMode;
  target_points: number;
  exit_buffer_points: number;
  stop_enabled: boolean;
  stop_points: number;
  max_hold_seconds: number;
  max_trades_per_session: number;
  quantity: number;
  max_quantity: number;
  max_premium_at_risk_inr: number;
  daily_loss_limit_inr: number;
  data_source: 'kite' | 'truedata';
  execution_mode: 'paper' | 'live';
}

export interface AtmPremiumImbalanceResponse {
  strategy: {
    id: string;
    name: string;
    contract_version: string;
    tagline: string;
    how_it_works: string;
    provenance: string;
    /** False until the live-readiness gate passes. The UI must not offer live. */
    live_ready: boolean;
    enabled: boolean;
  };
  config: AtmPremiumImbalanceConfig;
  /** The engine's own defaults, published so the UI never mirrors a second copy. */
  defaults: AtmPremiumImbalanceConfig;
  /** Allowed values, published for the same reason. */
  vocabularies: Record<string, string[]>;
  /**
   * Options the engine will refuse in live mode. Greyed out rather than offered,
   * so the operator is never shown a switch that validation will reject after
   * they have already clicked it.
   */
  research_only: { entry_price_policy: string[]; exit_policy: string[] };
  /** What live mode will insist on, published so the UI can say so up front. */
  live_requires?: { protection_mode: string[]; quote_mode: string[];
    require_session_origin_tick?: boolean[] };
}

export interface AtmPremiumImbalanceSnapshot {
  strategy: AtmPremiumImbalanceResponse['strategy'];
  config: AtmPremiumImbalanceConfig;
  resolved: {
    underlying: string;
    expiry: string;
    strike: number;
    ce: { instrument_id: string; tradingsymbol: string; lot_size: number };
    pe: { instrument_id: string; tradingsymbol: string; lot_size: number };
  } | null;
  /** Every reason the strategy is not armed. Never empty when `resolved` is null. */
  blockers: string[];
}

export function useAtmPremiumImbalanceConfig() {
  return useQuery<AtmPremiumImbalanceResponse>({
    queryKey: KEY,
    queryFn: () => api.get('/api/v1/config/atm-premium-imbalance'),
    staleTime: 30000,
  });
}

export function useSetAtmPremiumImbalanceConfig() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: Partial<AtmPremiumImbalanceConfig>) =>
      api.put('/api/v1/config/atm-premium-imbalance', body),
    onSuccess: () => {
      // Refetch rather than patch the cache: the server is the only thing that
      // knows the validated result, and instrument resolution depends on it.
      qc.invalidateQueries({ queryKey: KEY });
      qc.invalidateQueries({ queryKey: SNAPSHOT_KEY });
    },
  });
}

export function useAtmPremiumImbalanceSnapshot(enabled = true) {
  return useQuery<AtmPremiumImbalanceSnapshot>({
    queryKey: SNAPSHOT_KEY,
    queryFn: () => api.get('/api/v1/config/atm-premium-imbalance/snapshot'),
    enabled,
    staleTime: 15000,
    retry: false,
  });
}
