import { useMutation, useQuery } from '@tanstack/react-query';
import { api } from '../utils/api';

const ROOT = '/api/v1/opening-volume-leaders';

export type OpeningLeaderDirection = 'UP' | 'DOWN' | 'NEUTRAL';
export type OpeningLeaderTier = 'weak' | 'watch' | 'spurt' | 'strong' | 'explosive';
export type OpeningLeaderQuality = 'weak' | 'moderate' | 'strong';
export type OpeningLeaderLiquidity = 'pass' | 'fail' | 'unknown';
export type OpeningLeaderChaseState = 'no_aligned_break' | 'retest' | 'preferred' | 'caution' | 'chase';
export type OpeningLeaderValidationState = 'pending' | 'pass' | 'fail' | 'unavailable';

export interface OpeningLeaderOption {
  tradingsymbol: string;
  exchange: string;
  option_type: 'CE' | 'PE';
  strike: number;
  expiry: string;
  dte: number;
  ltp: number;
  bid: number;
  ask: number;
  lot_size: number;
  lot_cost: number;
  premium_stop_price: number;
  premium_target_price: number;
  premium_risk_per_lot: number;
  beginner_expiry_warning: boolean;
}

export interface OpeningLeaderPlaybook {
  known_gate_status: 'blocked' | 'caution' | 'passes_known_gates';
  known_gate_blockers: string[];
  known_gate_cautions: string[];
  breadth_alignment: 'aligned' | 'neutral' | 'against';
  recommended_risk_pct: number;
  primary_gate_complete: false;
  sterling_gate_complete: boolean;
  unverified_private_gates: string[];
  entry_reference: string;
  staged_entry_pct: [number, number, number];
  first_scale_r_multiple: [number, number];
  daily_loss_cap_r: number;
  weekly_loss_cap_r: number;
  max_open_positions: number;
}

export interface OpeningLeaderDecision {
  model: string;
  provenance: string;
  score: {
    lower_bound: number;
    upper_bound: number;
    coverage_pct: number;
    trade_threshold: number;
    special_threshold: number;
    trade: boolean;
    special: boolean;
    components: Array<{
      name: string;
      weight: number;
      earned: number;
      status: 'pass' | 'fail' | 'neutral' | 'unknown';
      rule: string;
    }>;
  };
  conviction: {
    passed: number;
    known: number;
    total: 7;
    required: number;
    factors: Record<string, boolean | null>;
    rules: Record<string, string>;
  };
  momentum: {
    box_x: boolean;
    box_y: boolean;
    state: 'ready' | 'setup' | 'blocked';
    box_x_rule: string;
    box_y_rule: string;
  };
  sterling_combo: boolean;
  combo_rule: string;
  execution_eligible: boolean;
}

export interface OpeningLeaderMarketContext {
  status: 'available' | 'insufficient_history' | 'unavailable' | 'not_requested';
  daily_session_count?: number;
  sma_50?: number | null;
  trend_50dma_aligned?: boolean | null;
  high_52w?: number | null;
  low_52w?: number | null;
  distance_from_52w_high_pct?: number | null;
  source: string;
  error_type?: string;
}

export interface OpeningLeaderSignal {
  symbol: string;
  session_date: string;
  signal_time: string;
  volume_signal_time: string;
  actionable_signal_time: string | null;
  observed_at: string;
  direction: OpeningLeaderDirection;
  tier: OpeningLeaderTier;
  rvol: number;
  opening_volume: number;
  average_opening_volume: number;
  baseline_session_count: number;
  opening_open: number;
  opening_high: number;
  opening_low: number;
  opening_close: number;
  current_price: number;
  live_price: number | null;
  price_source: 'kite_live_quote' | 'latest_completed_minute';
  previous_close: number | null;
  day_change_pct: number | null;
  gap_pct: number | null;
  body_pct: number;
  range_pct: number;
  body_fraction: number;
  close_location: number;
  candle_quality: OpeningLeaderQuality;
  average_turnover_inr: number | null;
  turnover_session_count: number;
  liquidity_state: OpeningLeaderLiquidity;
  liquidity_reasons: string[];
  orb_break_side: OpeningLeaderDirection | null;
  orb_break_time: string | null;
  orb_cumulative_volume: number | null;
  orb_aligned: boolean;
  orb_immediate: boolean;
  combo: boolean;
  session_high: number;
  session_low: number;
  orb_break_level: number | null;
  orb_age_minutes: number | null;
  orb_fresh: boolean;
  orb_distance_pct: number | null;
  chase_state: OpeningLeaderChaseState;
  protective_stop_price: number | null;
  stop_distance_pct: number | null;
  stop_too_wide: boolean | null;
  consecutive_leader_days: number | null;
  third_day_repeat: boolean | null;
  hold_5m_status: OpeningLeaderValidationState;
  hold_5m_check_time: string | null;
  hold_5m_price: number | null;
  move_1pct_within_60m: boolean | null;
  move_1pct_time: string | null;
  intraday_vwap: number | null;
  vwap_aligned: boolean | null;
  previous_day_high: number | null;
  previous_day_low: number | null;
  pdh_pdl_break_aligned: boolean | null;
  rsi_14_1m: number | null;
  rally_aligned: boolean;
  rise_from_low_pct: number;
  fall_from_high_pct: number;
  is_leader: boolean;
  passes_quality_filters: boolean;
  entry_phase: string;
  signal_key: string;
  playbook: OpeningLeaderPlaybook;
  market_context: OpeningLeaderMarketContext;
  option: OpeningLeaderOption | null;
  option_status: string;
  option_rule: string;
  decision: OpeningLeaderDecision;
}

export interface OpeningVolumeContract {
  strategy: {
    id: string;
    version: string;
    execution: 'guarded_account_mode' | string;
    documented_rules: string[];
    local_transparent_rules: string[];
    unknown_and_omitted: string[];
  };
  defaults: Record<string, number>;
  decision_defaults: Record<string, number>;
  decision_weights: Record<string, number>;
  live_scan_defaults: Record<string, unknown>;
  live_universe: string;
  tier_score: string;
  parity: {
    evidence_backed: string[];
    transparent_local: string[];
    insufficient_evidence: string[];
  };
}

export interface OpeningVolumeScanRequest {
  symbols: string[];
  scan_all_stocks: boolean;
  include_watch: boolean;
  include_weak: boolean;
  max_candidates: number;
  concurrency: number;
  history_calendar_days: number;
  as_of?: string;
  config: Record<string, number>;
  sector_by_symbol?: Record<string, string>;
}

export interface OpeningExecutionConfig {
  enabled: boolean;
  min_score: number;
  min_conviction: number;
  max_trades_per_day: number;
  risk_pct: number;
  max_lots: number;
  max_quote_staleness_s: number;
  max_spread_pct: number;
  max_underlying_drift_pct: number;
  min_dte: number;
}

export interface OpeningExecutionResponse {
  scan: OpeningVolumeScanResponse;
  execution: {
    status: string;
    reason?: string;
    count?: number;
    executed: Array<Record<string, unknown>>;
  };
}

export interface OpeningVolumeScanResponse {
  strategy: OpeningVolumeContract['strategy'];
  as_of: string;
  universe: {
    source: string;
    available_fno_equity_count: number;
    requested_count: number;
    selected_count: number;
    truncated: boolean;
    symbols: string[];
  };
  universe_count: number;
  evaluated_count: number;
  leader_count: number;
  watch_count: number;
  weak_count: number;
  enrichment: {
    daily_context_limit: number;
    daily_context_count: number;
    option_quote_count: number;
    historical_quotes_omitted: boolean;
  };
  breadth: {
    advances: number;
    declines: number;
    unchanged: number;
    observed: number;
    advance_decline_ratio: number | null;
    green_pct: number | null;
    mood: 'bullish' | 'bearish' | 'neutral';
    participation: 'strong_green' | 'balanced' | 'selective' | 'unknown';
    mood_rule: string;
    coverage_pct: number;
    reliable: boolean;
    source: string;
  };
  leaders: OpeningLeaderSignal[];
  watch: OpeningLeaderSignal[];
  weak: OpeningLeaderSignal[];
  failures: Array<{ symbol: string; error: string }>;
}

export function useOpeningVolumeContract() {
  return useQuery<OpeningVolumeContract>({
    queryKey: ['opening-volume-leaders-contract'],
    queryFn: () => api.get<OpeningVolumeContract>(`${ROOT}/contract`),
    staleTime: Number.POSITIVE_INFINITY,
  });
}

export function useOpeningVolumeScan() {
  return useMutation<OpeningVolumeScanResponse, Error, OpeningVolumeScanRequest>({
    mutationFn: (request) => api.post<OpeningVolumeScanResponse>(`${ROOT}/scan`, request),
  });
}

export function useOpeningExecutionConfig() {
  return useQuery<{ config: OpeningExecutionConfig }>({
    queryKey: ['opening-volume-leaders-execution-config'],
    queryFn: () => api.get<{ config: OpeningExecutionConfig }>(`${ROOT}/execution-config`),
  });
}

export function useUpdateOpeningExecutionConfig() {
  return useMutation<
    { config: OpeningExecutionConfig },
    Error,
    Partial<OpeningExecutionConfig>
  >({
    mutationFn: (request) => api.put<{ config: OpeningExecutionConfig }>(`${ROOT}/execution-config`, request),
  });
}

export function useExecuteOpeningVolumeScan() {
  return useMutation<OpeningExecutionResponse, Error, OpeningVolumeScanRequest>({
    mutationFn: (request) => api.post<OpeningExecutionResponse>(`${ROOT}/execute`, request),
  });
}
