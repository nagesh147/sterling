/**
 * Hooks for the DerivativesSelector API surface (Phase 4 of the
 * derivatives build).
 *
 * - useDerivativesCandidates(strategy?, underlying?) → /candidates (refetch 30s)
 * - useDerivativesPreview(args)                     → /preview
 * - useDerivativesConfig()                          → /config (GET)
 * - usePatchDerivativesProfile()                    → /config (POST)
 * - useDerivativesExecute()                         → /execute with freeze_token
 * - useGreeksBudgetState()                          → /greeks-budget (refetch 10s)
 * - useDerivativesFunding(underlying)               → /funding/{ul}
 *
 * Types mirror app/engines/derivatives/schemas.py + the endpoint Pydantic
 * models in app/api/v1/endpoints/derivatives.py.
 */
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { api } from '../utils/api';

// ── Types ────────────────────────────────────────────────────────────────

export type InstrumentBias = 'auto' | 'futures' | 'options';

export interface StrategyDerivativesProfile {
  strategy: string;
  enabled: boolean;
  instrument_bias: InstrumentBias;
  target_delta: number;
  target_delta_tolerance: number;
  prefer_asymmetry: boolean;
  dte_min: number;
  dte_preferred: number;
  dte_max: number;
  expected_hold_minutes: number;
  expiry_close_minutes_before: number;
  front_back_iv_diff_max: number;
  leverage_cap: number;
  max_premium_pct_of_account: number;
  funding_cost_max_pct_of_R: number;
  min_oi: number;
  min_volume_24h_x_contract: number;
  max_spread_pct: number;
  ivr_pct_naked_max: number;
  // Auto-execute toggles — when algo_mode is ON the background scanner
  // fires the chosen candidate per leg. Both default false.
  auto_execute_futures: boolean;
  auto_execute_options: boolean;
}

export interface DerivativesCandidateRow {
  signal_id: string;
  strategy: string;
  underlying: string;
  direction: string;
  instrument_type: string;
  option_symbol: string | null;
  strike: number | null;
  dte: number | null;
  delta: number | null;
  gamma: number | null;
  theta: number | null;
  vega: number | null;
  premium: number | null;
  contracts: number;
  leverage: number;
  notional_usd: number;
  stop_loss: number | null;
  take_profit: number | null;
  expected_r: number;
  funding_cost_usd: number;
  theta_burn_usd: number;
  liquidity_score: number | null;
  freeze_token: string;
  freeze_token_ttl_ms: number;
  status: string;
  reason: string;
  warnings: string[];
  chain_age_ms: number | null;
}

export interface CandidatesResponse {
  candidates: DerivativesCandidateRow[];
  timestamp_ms: number;
}

export interface DerivativesCandidate {
  rank: number;
  instrument_type: string;
  underlying: string;
  option_symbol: string | null;
  option_type: string | null;
  strike: number | null;
  expiry: string | null;
  dte: number | null;
  entry_price: number;
  direction: string;
  contracts: number;
  leverage: number;
  notional_usd: number;
  premium_usd: number | null;
  stop_loss: number | null;
  take_profit: number | null;
  sl_premium: number | null;
  tp_premium: number | null;
  expected_r: number;
  projected_funding_cost_usd: number;
  projected_theta_burn_usd: number;
  delta: number;
  gamma: number;
  vega: number;
  theta: number;
  rho: number;
  spread_pct: number;
  open_interest: number;
  mark_iv: number;
  score: number;
  score_breakdown: Record<string, number>;
  warnings: string[];
}

export interface DerivativesDecision {
  status: 'ok' | 'defer' | 'fail_open' | 'profile_off';
  chosen: DerivativesCandidate | null;
  alternatives: DerivativesCandidate[];
  freeze_token: string | null;
  freeze_token_ttl_ms: number;
  reason: string;
  code: string;
  timestamp_ms: number;
  warnings: string[];
}

export interface GreeksBudgetState {
  budget: {
    max_net_delta: number;
    max_net_gamma: number;
    max_net_vega: number;
    max_net_theta: number;
  };
  portfolio_value: number;
  net_greeks: { delta: number; gamma: number; vega: number; theta: number; rho: number };
  usage_pct_of_nav: { delta: number; gamma: number; vega: number; theta: number; rho: number };
  positions: Array<{
    id: string;
    underlying: string;
    instrument_type: string;
    contracts: number;
    notional_usd: number;
    delta: number;
    gamma: number;
    vega: number;
    theta: number;
    rho: number;
  }>;
  timestamp_ms?: number;
}

export interface DerivativesExecuteRequest {
  freeze_token: string;
  candidate_idx?: number;
}

export interface DerivativesExecuteResponse {
  accepted: boolean;
  mode: string;
  underlying: string;
  instrument_type: string;
  direction: string;
  size: number;
  leverage: number;
  order_id: string | null;
  paper_position_id: string | null;
  entry_price: number | null;
  stop_loss: number | null;
  take_profit: number | null;
  status: string;
  code: string;
  reason: string;
  timestamp_ms: number;
}

// ── Hooks ────────────────────────────────────────────────────────────────

export function useDerivativesCandidates(strategy?: string, underlying?: string) {
  const qs = new URLSearchParams();
  if (strategy) qs.append('strategy', strategy);
  if (underlying) qs.append('underlying', underlying);
  const qsStr = qs.toString() ? `?${qs.toString()}` : '';
  return useQuery<CandidatesResponse>({
    queryKey: ['derivatives', 'candidates', strategy ?? '', underlying ?? ''],
    queryFn: () => api.get<CandidatesResponse>(`/api/v1/derivatives/candidates${qsStr}`),
    refetchInterval: 30_000,
    retry: 1,
  });
}

export interface PreviewArgs {
  strategy: string;
  underlying: string;
  direction: string;
  entry: number;
  stop_loss: number;
  take_profit?: number;
  atr?: number;
  signal_score?: number;
  expected_hold_minutes?: number;
}

export function useDerivativesPreview(args: PreviewArgs | null) {
  const qs = args
    ? new URLSearchParams(
        Object.entries({
          strategy: args.strategy,
          underlying: args.underlying,
          direction: args.direction,
          entry: String(args.entry),
          stop_loss: String(args.stop_loss),
          take_profit: args.take_profit != null ? String(args.take_profit) : '',
          atr: String(args.atr ?? 0),
          signal_score: String(args.signal_score ?? 0),
          expected_hold_minutes: args.expected_hold_minutes != null ? String(args.expected_hold_minutes) : '',
        }).filter(([, v]) => v !== '')
      ).toString()
    : '';
  return useQuery<DerivativesDecision>({
    queryKey: ['derivatives', 'preview', qs],
    queryFn: () => api.get<DerivativesDecision>(`/api/v1/derivatives/preview?${qs}`),
    enabled: !!args,
    retry: 0,
  });
}

export function useDerivativesConfig() {
  return useQuery<{ profiles: Record<string, StrategyDerivativesProfile> }>({
    queryKey: ['derivatives', 'config'],
    queryFn: () => api.get('/api/v1/derivatives/config'),
  });
}

export function usePatchDerivativesProfile() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (profile: StrategyDerivativesProfile) =>
      api.post<{ profiles: Record<string, StrategyDerivativesProfile> }>(
        '/api/v1/derivatives/config',
        { profile }
      ),
    onSuccess: (data) => {
      qc.setQueryData(['derivatives', 'config'], data);
      qc.invalidateQueries({ queryKey: ['derivatives', 'candidates'] });
    },
  });
}

export function useDerivativesExecute() {
  const qc = useQueryClient();
  return useMutation<DerivativesExecuteResponse, Error, DerivativesExecuteRequest>({
    mutationFn: (req) =>
      api.post<DerivativesExecuteResponse>('/api/v1/derivatives/execute', req),
    onSettled: () => {
      qc.invalidateQueries({ queryKey: ['derivatives', 'candidates'] });
      qc.invalidateQueries({ queryKey: ['positions'] });
    },
  });
}

export function useGreeksBudgetState() {
  return useQuery<GreeksBudgetState>({
    queryKey: ['derivatives', 'greeks-budget'],
    queryFn: () => api.get<GreeksBudgetState>('/api/v1/derivatives/greeks-budget'),
    refetchInterval: 10_000,
    retry: 1,
  });
}

// ── Split candidate hooks (parallel futures + options tables) ──────────

export function useDerivativesFuturesCandidates(strategy?: string, underlying?: string) {
  const qs = new URLSearchParams();
  if (strategy) qs.append('strategy', strategy);
  if (underlying) qs.append('underlying', underlying);
  const qsStr = qs.toString() ? `?${qs.toString()}` : '';
  return useQuery<CandidatesResponse>({
    queryKey: ['derivatives', 'candidates', 'futures', strategy ?? '', underlying ?? ''],
    queryFn: () => api.get<CandidatesResponse>(`/api/v1/derivatives/candidates/futures${qsStr}`),
    refetchInterval: 30_000,
    retry: 1,
  });
}

export function useDerivativesOptionsCandidates(strategy?: string, underlying?: string) {
  const qs = new URLSearchParams();
  if (strategy) qs.append('strategy', strategy);
  if (underlying) qs.append('underlying', underlying);
  const qsStr = qs.toString() ? `?${qs.toString()}` : '';
  return useQuery<CandidatesResponse>({
    queryKey: ['derivatives', 'candidates', 'options', strategy ?? '', underlying ?? ''],
    queryFn: () => api.get<CandidatesResponse>(`/api/v1/derivatives/candidates/options${qsStr}`),
    refetchInterval: 30_000,
    retry: 1,
  });
}

export interface DerivativesScanResponse {
  futures: DerivativesCandidateRow[];
  options: DerivativesCandidateRow[];
  algo_mode: boolean;
  last_scan_ms: number;
  next_scan_ms: number;
  auto_exec_attempts: number;
  auto_exec_accepted: number;
}

export function useDerivativesScan() {
  return useQuery<DerivativesScanResponse>({
    queryKey: ['derivatives', 'scan'],
    queryFn: () => api.get<DerivativesScanResponse>('/api/v1/derivatives/scan'),
    refetchInterval: 30_000,
    retry: 1,
  });
}

export function useDerivativesFunding(underlying: string | null) {
  return useQuery<{
    funding_rate_8h_pct: number;
    source: string;
    fetched_ts_ms: number;
    next_funding_ts_ms: number | null;
  }>({
    queryKey: ['derivatives', 'funding', underlying],
    queryFn: () => api.get(`/api/v1/derivatives/funding/${underlying}`),
    enabled: !!underlying,
    refetchInterval: 60_000,
    retry: 1,
  });
}
