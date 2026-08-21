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

/** One leg's live quote, plus whether it may be traded on at all. */
export interface AtmLegState {
  instrument_id: string;
  tradingsymbol: string;
  option_type: 'CE' | 'PE';
  lot_size: number | null;
  ltp: number | null;
  bid: number | null;
  ask: number | null;
  last_trade_ts_ms: number | null;
  /**
   * Did the trade behind `ltp` happen in this session?
   * `false` means a carried-over price and the strategy will refuse it;
   * `null` means the feed sent no trade time, so it cannot be judged.
   */
  session_origin: boolean | null;
  age_ms: number | null;
  official_open: number | null;
}

export interface AtmTradeState {
  state: string;
  option: 'CE' | 'PE' | null;
  strike: number | null;
  quantity: number | null;
  first_tick_price: number | null;
  entry_order_price: number | null;
  entry: number | null;
  target: number | null;
  trigger: number | null;
  exit_order_price: number | null;
  exit: number | null;
  points: number | null;
  pnl: number | null;
  slippage_vs_target: number | null;
  attempts: number | null;
  quote_mode: string;
  halt_reason: string | null;
  protection: { kind: string; state: string; limit_price: number | null; order_id: string | null } | null;
}

/** The live armed session, or null when nothing is armed. */
export interface AtmSessionStatus {
  armed: boolean;
  finished: boolean;
  session_date: string;
  session_open_ms: number | null;
  phase: string;
  halt_reason: string | null;
  underlying: string;
  expiry: string | null;
  strike: number | null;
  quantity: number | null;
  execution_mode: string;
  quote_mode: string;
  protection_mode: string;
  trades_taken: number;
  legs: { CE: AtmLegState; PE: AtmLegState } | null;
  difference: number | null;
  cheaper_leg: 'CE' | 'PE' | null;
  signal: { action: string | null; reason: string | null; option_type: 'CE' | 'PE' | null } | null;
  trade: AtmTradeState | null;
}

export interface AtmArmResult {
  status: 'armed' | 'already_armed' | 'disabled' | 'no_quantity' | 'market_closed' | 'error';
  underlying?: string;
  expiry?: string;
  strike?: number;
  quantity?: number;
  protection_mode?: string;
  execution_mode?: string;
  message?: string;
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
  /** Live session state, or null when nothing is armed. */
  session: AtmSessionStatus | null;
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

export function useAtmPremiumImbalanceSnapshot(enabled = true, refetchMs = 0) {
  return useQuery<AtmPremiumImbalanceSnapshot>({
    queryKey: SNAPSHOT_KEY,
    queryFn: () => api.get('/api/v1/config/atm-premium-imbalance/snapshot'),
    enabled,
    staleTime: 2000,
    // Polled only while something is armed: an unarmed strategy has no live
    // state worth a request every few seconds.
    refetchInterval: refetchMs > 0 ? refetchMs : false,
    retry: false,
  });
}

/**
 * Arm the session: resolve the ATM pair and subscribe both legs.
 *
 * Idempotent for the day on the server, which is what makes it safe to expose
 * as a button — a double click returns `already_armed` rather than creating a
 * second session that could place a second entry.
 */
export function useArmAtmPremiumImbalance() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () => api.post<AtmArmResult>('/api/v1/config/atm-premium-imbalance/arm'),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: SNAPSHOT_KEY });
    },
  });
}
