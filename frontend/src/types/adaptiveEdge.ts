export interface AdaptiveEdgeSettings {
  enabled: boolean;
  symbol: string;
  w_short: number;
  w_long: number;
  stop_points: number;
  trail_points: number;
  profit_lock_activation_points: number;
  profit_lock_offset_points: number;
  persistence_bars: number;
  scalp_favorable_points: number;
  extended_favorable_points: number;
  intraday_favorable_points: number;
  tick_size: number;
  ib_minutes: number;
}

export interface AdaptiveEdgeReadiness {
  name: string;
  ready: boolean;
  detail: string;
}

export interface AdaptiveEdgeSession {
  entries: number | null;
  exits: number | null;
  reentries: number | null;
  blocked_pyramid: number | null;
  last_mode: string | null;
  last_thesis: string | null;
  last_protection_stage: string | null;
  last_overlays: string[];
  last_operating_mode: string | null;
  last_horizon: string | null;
  last_poc: number | null;
  last_cvd: number | null;
  last_location: string | null;
  last_bar_delta: number | null;
  last_vwap: number | null;
  last_or_location: string | null;
  last_poc_migration: string | null;
  peak_pnl: number | null;
  current_pnl: number | null;
  profit_giveback: number | null;
  lifecycle_action: string | null;
  last_position_quantity: number | null;
  exit_fill_price: number | null;
  audit_stages: string[];
}

export interface AdaptiveEdgeLeg {
  session_date?: string | null;
  entry_time?: string | null;
  exit_time?: string | null;
  entry_mode?: string | null;
  exit_mode?: string | null;
  peak_mode?: string | null;
  horizon?: string | null;
  operating_mode?: string | null;
  thesis?: string | null;
  protection_stage?: string | null;
  overlays?: string[];
  quantity?: number | null;
  flattened?: boolean | null;
}

export interface AdaptiveEdgeModeTransition {
  timestamp?: string | null;
  previous_mode?: string | null;
  new_mode?: string | null;
  trigger_reason?: string | null;
  favorable_points?: number | null;
  giveback_ratio?: number | null;
}

export interface AdaptiveEdgeFormulaRow {
  status: string;
  reason: string;
}

export interface AdaptiveEdgeSnapshot {
  label: string;
  software_complete: boolean;
  production_gate_authorized: boolean;
  meets_a197: boolean;
  registry_locked: boolean;
  live_trading: boolean;
  settings: AdaptiveEdgeSettings;
  readiness: AdaptiveEdgeReadiness[];
  session: AdaptiveEdgeSession;
  legs: AdaptiveEdgeLeg[];
  daily: Array<Record<string, unknown>>;
  quality: Record<string, unknown> | null;
  holdout: Record<string, unknown> | null;
  coverage: Record<string, unknown> | null;
  walk_forward: Record<string, unknown> | null;
  mode_counts: Record<string, number>;
  mode_transitions: AdaptiveEdgeModeTransition[];
  formula_table: Record<string, AdaptiveEdgeFormulaRow>;
  incomplete_reasons: string[];
}
