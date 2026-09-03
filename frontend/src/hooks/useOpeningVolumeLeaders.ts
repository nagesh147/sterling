import { useMutation, useQuery } from '@tanstack/react-query';
import { api } from '../utils/api';

const ROOT = '/api/v1/opening-volume-leaders';

export type OpeningLeaderDirection = 'UP' | 'DOWN' | 'NEUTRAL';
export type OpeningLeaderTier = 'weak' | 'watch' | 'spurt' | 'strong' | 'explosive';
export type OpeningLeaderQuality = 'weak' | 'moderate' | 'strong';
export type OpeningLeaderLiquidity = 'pass' | 'fail' | 'unknown';

export interface OpeningLeaderSignal {
  symbol: string;
  session_date: string;
  signal_time: string;
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
  rise_from_low_pct: number;
  fall_from_high_pct: number;
  is_leader: boolean;
  passes_quality_filters: boolean;
  entry_phase: string;
  signal_key: string;
}

export interface OpeningVolumeContract {
  strategy: {
    id: string;
    version: string;
    execution: 'advisory_only' | string;
    documented_rules: string[];
    local_transparent_rules: string[];
    unknown_and_omitted: string[];
  };
  defaults: Record<string, number>;
  live_scan_defaults: Record<string, unknown>;
  live_universe: string;
  tier_score: string;
}

export interface OpeningVolumeScanRequest {
  symbols: string[];
  scan_all_stocks: boolean;
  include_watch: boolean;
  max_candidates: number;
  concurrency: number;
  history_calendar_days: number;
  config: Record<string, number>;
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
  breadth: {
    advances: number;
    declines: number;
    unchanged: number;
    observed: number;
    advance_decline_ratio: number | null;
  };
  leaders: OpeningLeaderSignal[];
  watch: OpeningLeaderSignal[];
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
