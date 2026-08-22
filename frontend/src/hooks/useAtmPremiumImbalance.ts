import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { api } from '../utils/api';

const KEY = ['atm-premium-imbalance-config'];
const SNAPSHOT_KEY = ['atm-premium-imbalance-snapshot'];

export type QuoteMode = 'COMPATIBILITY' | 'SYNCHRONIZED' | 'EXECUTABLE';
export type EntryPricePolicy =
  | 'MARKETABLE_ASK' | 'PERCENT_THROUGH' | 'MANUAL_FILE'
  | 'FIRST_TICK_PERCENT' | 'FIRST_TICK_PLUS_BUFFER';
export type ExitPolicy = 'FIXED_POINT_TARGET' | 'PREMIUM_CONVERGENCE' | 'TRAILING_STOP';
export type ProtectionMode = 'NONE' | 'RESTING_TARGET_LIMIT' | 'GTT';
export type FirstTickSource = 'SESSION_TICK' | 'OFFICIAL_OPEN';
export type ExpiryPolicy = 'SAME_DAY' | 'NEAREST' | 'NEXT' | 'EXPLICIT';
export type SizingMode = 'LOTS' | 'QUANTITY';
export type StopBasis = 'POINTS' | 'PERCENT';

export interface AtmPremiumImbalanceConfig {
  enabled: boolean;
  underlying: string;
  expiry_policy: ExpiryPolicy;
  explicit_expiry: string;
  strike_policy: string;
  session_start: string;
  session_end: string;
  quote_mode: QuoteMode;
  sizing_mode: SizingMode;
  lots: number;
  stop_basis: StopBasis;
  stop_percent: number;
  trail_points: number;
  trail_percent: number;
  trail_start_points: number;
  trail_start_percent: number;
  breakeven_points: number;
  breakeven_percent: number;
  entry_window_seconds: number;
  close_at_session_end: boolean;
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
  status: 'armed' | 'already_armed' | 'disabled' | 'no_quantity' | 'invalid_size'
        | 'market_closed' | 'error';
  underlying?: string;
  expiry?: string;
  strike?: number;
  quantity?: number;
  lots?: number;
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
  /** What will actually be ordered, once the lot size is known. */
  sizing?: {
    mode: SizingMode; lot_size: number; quantity: number;
    max_premium_at_risk_inr?: number;
    /** The dearest option this size can buy under the risk ceiling. */
    max_affordable_premium?: number | null;
  };
  /** Present only while a replay is running or has just finished. */
  simulation?: AtmSimulationState | null;
  /** Every reason the strategy is not armed. Never empty when `resolved` is null. */
  blockers: string[];
  /** Live session state, or null when nothing is armed. */
  session: AtmSessionStatus | null;
  /** The realised record. Simulated trades are excluded. */
  record?: AtmTradeRecord;
}

/**
 * What actually happened, across every closed trade.
 *
 * `breakEvenWinRate` is the number to read first. A win rate on its own says
 * nothing — 85% is excellent against a small average loss and ruinous against a
 * large one — so the threshold travels with the measurement. `verdict` refuses to
 * answer below `minSample`, because a win rate computed from four trades is not a
 * win rate.
 */
export interface AtmTradeRecord {
  trades: number;
  wins: number;
  losses: number;
  /** Percent of premium, not points: +15 is 15% of a 100 premium and 4.4% of a 338 one. */
  win_rate_pct: number;
  avg_win_pct: number;
  avg_loss_pct: number;
  /** `avg_loss / (avg_win + avg_loss)`. Null until there is at least one loss. */
  break_even_win_rate_pct: number | null;
  expectancy_pct: number;
  worst_pct: number;
  best_pct: number;
  total_pnl: number;
  exit_reasons: Record<string, number>;
  min_sample: number;
  verdict: string;
}

/**
 * A replay of a past session on a fake clock.
 *
 * `illustrative_only` is repeated in every payload the backend sends so a client
 * cannot render replayed numbers as live ones by forgetting a flag somewhere.
 */
export interface AtmSimulationState {
  running: boolean;
  session_date: string | null;
  speed: number;
  clock_ms: number;
  clock_ist: string | null;
  bars_total: number;
  bars_done: number;
  progress: number;
  note: string;
  error: string | null;
  outcome: string | null;
  halt_reason: string | null;
  /** Keeps trading after the first close, relaxing the trade limit and window. */
  continuous: boolean;
  trades: number;
  illustrative_only: true;
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


/**
 * Start a replay of the last traded session.
 *
 * Invalidates nothing on its own: the board's snapshot poll is what shows the
 * replay progressing, and it starts polling because a session appears.
 */
export function useSimulateAtmPremiumImbalance() {
  const qc = useQueryClient();
  return useMutation<{ status: string; session_date?: string; speed?: number;
                       quantity?: number; message?: string; relaxed?: string[] },
                     Error, { speed?: number; continuous?: boolean } | void>({
    // Real time by default, because the clock is the point: at 1x the replay
    // reads like a live session rather than a fast-forward.
    mutationFn: (opts) => api.post(
      `/api/v1/config/atm-premium-imbalance/simulate?speed=${opts?.speed ?? 1}`
      + `&continuous=${opts?.continuous ?? true}`, {}),
    onSuccess: () => { void qc.invalidateQueries({ queryKey: SNAPSHOT_KEY }); },
  });
}

export function useStopAtmPremiumImbalanceSimulation() {
  const qc = useQueryClient();
  return useMutation<{ ok: boolean }, Error, void>({
    mutationFn: () => api.post('/api/v1/config/atm-premium-imbalance/simulate/stop', {}),
    onSuccess: () => { void qc.invalidateQueries({ queryKey: SNAPSHOT_KEY }); },
  });
}
