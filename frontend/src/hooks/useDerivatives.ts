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
  source: string; // "engine" (scalping/triple-ST) | "edge" (backtest-validated feed)
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
  structure_summary: string | null;
  structure_max_loss_usd: number | null;
  structure_max_profit_usd: number | null;
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
  // Originating strategy slug (e.g. "scalping/price_action", "directional").
  // Stamped into the position notes so the executed row can be attributed back
  // to the engine that produced it — keeps the Grok/Sterling tables separate.
  strategy?: string;
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
  return useQuery<{ profiles: Record<string, StrategyDerivativesProfile>; defaults: Record<string, StrategyDerivativesProfile> }>({
    queryKey: ['derivatives', 'config'],
    queryFn: () => api.get('/api/v1/derivatives/config'),
  });
}

export function usePatchDerivativesProfile() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ strategy, profile }: { strategy: string; profile: StrategyDerivativesProfile }) =>
      api.post<{ profiles: Record<string, StrategyDerivativesProfile>; defaults: Record<string, StrategyDerivativesProfile> }>(
        '/api/v1/derivatives/config',
        { profile: { ...profile, strategy } }
      ),
    onSuccess: (data) => {
      qc.setQueryData(['derivatives', 'config'], data);
      qc.invalidateQueries({ queryKey: ['derivatives', 'candidates'] });
    },
  });
}

export function useResetDerivativesConfig() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () =>
      api.delete<{ profiles: Record<string, StrategyDerivativesProfile>; defaults: Record<string, StrategyDerivativesProfile> }>(
        '/api/v1/derivatives/config'
      ),
    onSuccess: (data) => {
      qc.setQueryData(['derivatives', 'config'], data);
      qc.invalidateQueries({ queryKey: ['derivatives', 'candidates'] });
    },
  });
}

export function usePatchDerivativesGlobal() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (patch: { enabled?: boolean; auto_execute_futures?: boolean; auto_execute_options?: boolean }) =>
      api.post<{ profiles: Record<string, StrategyDerivativesProfile>; defaults: Record<string, StrategyDerivativesProfile> }>(
        '/api/v1/derivatives/config/global',
        patch
      ),
    onSuccess: (data) => {
      qc.setQueryData(['derivatives', 'config'], data);
      qc.invalidateQueries({ queryKey: ['derivatives', 'candidates'] });
    },
  });
}

// ─── engine config (Phase 2a: routing_gate vs native) ────────────────────

export type EngineMode = 'routing_gate' | 'native';
export type RiskPosture = 'long_only' | 'defined_risk' | 'naked';
export type AlphaSource =
  | 'directional_futures'
  | 'directional_options'
  | 'vrp_voltiming'
  | 'skew_put'
  | 'gex_pinning';

export interface DerivativesEngineConfig {
  engine_mode: EngineMode;
  active_alpha_sources: AlphaSource[];
  /** Multi-select: postures the native engine may use; it picks the best
   *  one for the current regime. */
  risk_postures: RiskPosture[];
  /** Legacy single posture — still returned by the backend, kept in sync
   *  with the highest-priority entry of `risk_postures`. */
  risk_posture?: RiskPosture;
  validation_method: 1 | 2 | 3;
}

export function useDerivativesEngineConfig() {
  return useQuery<DerivativesEngineConfig>({
    queryKey: ['derivatives', 'engine-config'],
    queryFn: () => api.get<DerivativesEngineConfig>('/api/v1/derivatives/config/engine'),
  });
}

export function usePatchDerivativesEngineConfig() {
  const qc = useQueryClient();
  return useMutation<DerivativesEngineConfig, Error, DerivativesEngineConfig>({
    mutationFn: (cfg) =>
      api.post<DerivativesEngineConfig>('/api/v1/derivatives/config/engine', cfg),
    onSuccess: (data) => {
      qc.setQueryData(['derivatives', 'engine-config'], data);
      // New engine mode → candidate tables + scan must refresh.
      qc.invalidateQueries({ queryKey: ['derivatives', 'candidates'] });
      qc.invalidateQueries({ queryKey: ['derivatives', 'scan'] });
    },
  });
}

export interface StudyReportResponse {
  validation_method: 1 | 2 | 3;
  study: string | null;
  study_generated_at: number | null;
  gate_overfilter: string | null;
}

export interface StudyReportResponse {
  validation_method: 1 | 2 | 3;
  study: string | null;
  study_generated_at: number | null;
  gate_overfilter: string | null;
  has_csv: boolean;
}

export function useStudyReport(enabled = true) {
  return useQuery<StudyReportResponse>({
    queryKey: ['derivatives', 'study-report'],
    queryFn: () => api.get<StudyReportResponse>('/api/v1/derivatives/study/report'),
    enabled,
    staleTime: 60_000,
  });
}

// ─── study run / status ──────────────────────────────────────────────────

export interface StudyRunResponse {
  run_id: string;
  status: string;
  n_configs: number;
}

export interface StudyStatusResponse {
  run_id: string;
  status: string;           // starting | running | complete | failed
  progress_pct: number;     // 0-100
  current_stage: string;
  elapsed_seconds: number;
  error: string | null;
  n_configs: number;
  n_survivors: number;
}

export function useStudyRun() {
  return useMutation<StudyRunResponse, Error, {
    symbols?: string[];
    timeframes?: string[];
    validation_method?: number;
  }>({
    mutationFn: (body) =>
      api.post<StudyRunResponse>('/api/v1/derivatives/study/run', body),
  });
}

export function useStudyStatus(runId: string | null, enabled = true) {
  return useQuery<StudyStatusResponse>({
    queryKey: ['derivatives', 'study-status', runId],
    queryFn: () => api.get<StudyStatusResponse>(`/api/v1/derivatives/study/status/${runId}`),
    enabled: enabled && !!runId,
    refetchInterval: (query) => {
      const data = query.state.data;
      if (data && (data.status === 'complete' || data.status === 'failed')) {
        return false;
      }
      return 3000;
    },
  });
}

// ─── edge gate ──────────────────────────────────────────────────────────

export interface EdgeGate {
  min_net_return: number;
  min_sharpe: number;
  min_trades: number;
  min_oos_sharpe: number;
  max_p_loss: number;
}

export interface EdgeComboSummary {
  symbol: string;
  tf: string;
  strategy: string;
  profile: string;
  trades: number;
  sharpe: number;
  pf: number;
  net_return: number;
  signal_score: number;
}

export interface EdgeGateResponse {
  gate: EdgeGate;
  admitted_count: number;
  admitted: EdgeComboSummary[];
}

export function useEdgeGate() {
  return useQuery<EdgeGateResponse>({
    queryKey: ['derivatives', 'edge-gate'],
    queryFn: () => api.get<EdgeGateResponse>('/api/v1/derivatives/edge-gate'),
  });
}

export function usePatchEdgeGate() {
  const qc = useQueryClient();
  return useMutation<EdgeGateResponse, Error, EdgeGate>({
    mutationFn: (gate) =>
      api.post<EdgeGateResponse>('/api/v1/derivatives/edge-gate', gate),
    onSuccess: (data) => {
      qc.setQueryData(['derivatives', 'edge-gate'], data);
      // New allow-list → candidate tables and scan must refresh.
      qc.invalidateQueries({ queryKey: ['derivatives', 'candidates'] });
      qc.invalidateQueries({ queryKey: ['derivatives', 'scan'] });
    },
  });
}

// ─── strategy catalog ───────────────────────────────────────────────────

export interface StrategyCatalogCombo {
  symbol: string;
  tf: string;
  profile: string;
  bracket: string;
  trades: number;
  win_rate_pct: number;
  net_return_pct: number;
  sharpe: number;
  oos_sharpe: number | null;
  p_loss_pct: number;
  max_dd_pct: number;
  signal_score: number;
}

export interface StrategyCatalogEntry {
  id: string;
  name: string;
  tagline: string;
  how_it_works: string;
  direction: string;
  engine: string;
  instrument: string;
  note: string;
  live: boolean;
  live_combo_count: number;
  combos: StrategyCatalogCombo[];
}

export interface StrategyCatalogResponse {
  strategies: StrategyCatalogEntry[];
  engines: { edge_feed: string; scalping_scanner: string };
  routing: string;
  gate: EdgeGate;
}

export function useStrategyCatalog() {
  return useQuery<StrategyCatalogResponse>({
    queryKey: ['derivatives', 'strategy-catalog'],
    queryFn: () => api.get<StrategyCatalogResponse>('/api/v1/derivatives/strategy-catalog'),
    staleTime: 60_000,
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
