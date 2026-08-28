import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { api } from '../utils/api';

const KEY = ['oi-wall-flow-config'];
const SNAPSHOT_KEY = ['oi-wall-flow-snapshot'];
const BASE = '/api/v1/config/oi-wall-flow';

export type StopMode = 'broker' | 'monitor' | 'both';
export type ExpirySelection = 'nearest' | 'weekly' | 'monthly' | 'any';
export type ExpirySeries = 'weekly' | 'monthly';
export type SignalState = 'watching' | 'armed' | 'running' | 'ended' | 'error';
export type Bias = 'bullish' | 'bearish' | 'neutral';

export interface OIWallFlowConfig {
  enabled: boolean;
  scan_stocks: string[];
  scan_all_stocks: boolean;
  stock_contracts: boolean;
  scan_indices: string[];
  oi_chg_deadband_pct: number;
  ltp_chg_deadband_pct: number;
  atm_window_strikes: number;
  min_bias_score: number;
  prefer_wall_strike: boolean;
  skip_atm: boolean;
  expiry_selection: ExpirySelection;
  expiry_dte_min: number;
  expiry_dte_max: number;
  avoid_expiry_day: boolean;
  min_option_oi: number;
  min_option_premium: number;
  scan_expiries_indices: ExpirySeries[];
  scan_expiries_stocks: ExpirySeries[];
  scan_weekly_series_indices: number[];
  scan_monthly_series_indices: number[];
  scan_monthly_series_stocks: number[];
  stop_premium_pct: number;
  target_premium_pct: number;
  target_2_premium_pct: number;
  wall_invalidation: boolean;
  stop_mode: StopMode;
  session_start: string;
  session_end: string;
  scan_interval_seconds: number;
  lot_size: number;
  lots: number;
  max_premium_at_risk_inr: number;
  max_concurrent_positions: number;
  max_new_trades_per_day: number;
  daily_loss_limit_inr: number;
  descale_after_losses: number;
  rescale_after_wins: number;
  data_source: 'kite';
}

export interface OIWallFlowModeState {
  is_paper: boolean;
  auto_execute: boolean;
  note: string;
}

export interface OIWallFlowStrategyInfo {
  id: string;
  name: string;
  contract_version: string;
  tagline: string;
  how_it_works: string;
  provenance: string;
  validated: boolean;
  enabled: boolean;
  calibration: Record<string, string>;
  calibrated_fields: string[];
  judgement_fields: string[];
  headline_finding: string;
  what_to_do?: string;
  evidence?: string;
}

export interface OIWallFlowResponse {
  strategy: OIWallFlowStrategyInfo;
  config: OIWallFlowConfig;
  defaults: OIWallFlowConfig;
  vocabularies: Record<string, string[]>;
  research_only: Record<string, string[]>;
  warnings: string[];
}

export interface OIWallFlowInstrument {
  instrument_id: string;
  tradingsymbol: string;
  option_type: 'CE' | 'PE';
  strike: number;
  expiry: string;
  lot_size: number;
  tick_size: number;
  exchange: string;
}

export interface OIWallFlowSignalRow {
  id: string;
  state: SignalState;
  at_ms: number;
  underlying: string;
  spot: number;
  expiry: string;
  days_to_expiry: number | null;
  reason: string | null;
  bias: {
    bias: Bias;
    score: number;
    reasons: string[];
    pcr_oi: number;
    max_pain: number;
    put_wall: number;
    call_wall: number;
    atm_strike: number;
  };
  plan: {
    option_type: 'CE' | 'PE';
    strike: number;
    entry: number;
    stop: number;
    target: number;
    target_2: number | null;
    underlying_invalidation: number;
    lot_size: number;
    quantity: number;
    lots: number;
    reason: string;
    tradingsymbol: string | null;
    instrument: OIWallFlowInstrument | null;
  } | null;
  instrument: OIWallFlowInstrument | null;
  levels: {
    ltp: number | null; entry: number | null; stop: number | null;
    trail: number | null; target: number | null; exit: number | null;
  };
  sizing: {
    lots: number | null; quantity: number | null;
    at_risk_inr: number | null; deployed_inr: number | null;
  };
}

export interface OIWallFlowPositionRow {
  symbol: string; signal_id: string; entry: number; stop: number;
  target: number | null; target_2: number | null; quantity: number; lots: number;
  entered_ms: number; entry_day: string; exiting: boolean; high_water: number;
  underlying_invalidation: number; option_type: 'CE' | 'PE'; strike: number;
  status: 'pending' | 'open' | 'closed' | 'rejected';
  order_id: string;
  fill_price: number;
  effective_entry: number;
  gtt_id: number;
  stop_mode: StopMode;
}

export interface OIWallFlowScanState {
  last_run_ms?: number;
  underlyings?: number;
  chains?: number;
  quoted?: number;
  scanned?: number;
  armed?: number;
  total_seconds?: number;
  error?: string;
}

export interface OIWallFlowTradeRecord {
  trades: number; wins: number; losses: number;
  win_rate: number | null;
  consecutive_losses: number; consecutive_wins: number;
  realised_inr: number; day_realised_inr: number; day: string;
  verdict: string;
}

export interface OIWallFlowSessionStatus {
  day: string;
  phase: string;
  halt_reason: string;
  trades_today: number;
  candidates: OIWallFlowSignalRow[];
  positions: OIWallFlowPositionRow[];
  record: OIWallFlowTradeRecord;
  subscribed: number[];
  notes: { kind: string; message: string; at_ms: number }[];
}

export interface OIWallFlowSnapshot {
  strategy: OIWallFlowStrategyInfo;
  config: OIWallFlowConfig;
  scan: OIWallFlowScanState;
  session: OIWallFlowSessionStatus | null;
  candidates: OIWallFlowSignalRow[];
  positions: OIWallFlowPositionRow[];
  record: OIWallFlowTradeRecord;
  orphan_positions: { symbol: string; quantity: number; entry_price: number }[];
  universe?: { underlyings: number; sample: string[] };
  mode?: OIWallFlowModeState;
  warnings?: string[];
  blockers: string[];
}

export function useOiWallFlowConfig() {
  return useQuery<OIWallFlowResponse>({
    queryKey: KEY,
    queryFn: () => api.get(BASE),
    staleTime: 30000,
  });
}

export function useOiWallFlowSnapshot(enabled = true, refetchInterval = 0) {
  return useQuery<OIWallFlowSnapshot>({
    queryKey: SNAPSHOT_KEY,
    queryFn: () => api.get(`${BASE}/snapshot`),
    enabled,
    staleTime: 2000,
    refetchInterval: refetchInterval || false,
  });
}

export function useUpdateOiWallFlow() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: Partial<OIWallFlowConfig>) => api.put(BASE, body),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: KEY });
      qc.invalidateQueries({ queryKey: SNAPSHOT_KEY });
    },
  });
}

export function useOiWallFlowScan() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () => api.post<{ scanned: number; armed: number }>(`${BASE}/scan`),
    onSuccess: () => qc.invalidateQueries({ queryKey: SNAPSHOT_KEY }),
  });
}

export function useArmOiWallFlow() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (signalId: string) =>
      api.post<{ ok: boolean; message?: string; symbol?: string; entry?: number; stop?: number }>(
        `${BASE}/arm`, { signal_id: signalId }),
    onSuccess: () => qc.invalidateQueries({ queryKey: SNAPSHOT_KEY }),
  });
}
