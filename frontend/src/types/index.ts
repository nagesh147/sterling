export interface InstrumentMeta {
  underlying: string;
  quote_currency: string;
  contract_multiplier: number;
  tick_size: number;
  strike_step: number;
  min_dte: number;
  preferred_dte_min: number;
  preferred_dte_max: number;
  force_exit_dte: number;
  has_options: boolean;
  exchange: string;
  perp_symbol: string;
  index_name: string;
  dvol_symbol: string | null;
  description: string;
}

export interface InstrumentListResponse {
  instruments: InstrumentMeta[];
  count: number;
}

export interface RegimeResult {
  macro_regime: 'bullish' | 'bearish' | 'neutral';
  ema50: number;
  close_4h: number;
  score: number;
}

export interface SignalResult {
  trend: 1 | -1 | 0;
  all_green: boolean;
  all_red: boolean;
  green_arrow: boolean;
  red_arrow: boolean;
  st_trends: number[];
  st_values: number[];
  close_1h: number;
  score_long: number;
  score_short: number;
}

export type TradeState =
  | 'IDLE'
  | 'EARLY_SETUP_ACTIVE'
  | 'CONFIRMED_SETUP_ACTIVE'
  | 'FILTERED'
  | 'ENTRY_ARMED_PULLBACK'
  | 'ENTRY_ARMED_CONTINUATION'
  | 'ENTERED'
  | 'PARTIALLY_REDUCED'
  | 'EXIT_PENDING'
  | 'EXITED'
  | 'CANCELLED';

export type Direction = 'long' | 'short' | 'neutral';
export type ExecMode = 'pullback' | 'continuation' | 'wait';
export type IVRBand = 'low' | 'normal' | 'elevated' | 'high';
export type PositionStatus = 'open' | 'partially_closed' | 'closed';

export interface DirectionalStatusResponse {
  underlying: string;
  loaded: boolean;
  paper_mode: boolean;
  real_public_data: boolean;
  exchange_status: string;
  has_options: boolean;
  regime?: RegimeResult;
  signal?: SignalResult;
  state: TradeState;
  timestamp_ms: number;
}

export interface MarketSnapshotResponse {
  underlying: string;
  spot_price: number;
  index_price: number;
  perp_price: number;
  candles_4h_count: number;
  candles_1h_count: number;
  candles_15m_count: number;
  dvol?: number;
  ivr?: number;
  data_source: string;
  timestamp_ms: number;
}

export interface CandidateContract {
  instrument_name: string;
  underlying: string;
  strike: number;
  expiry_date: string;
  dte: number;
  option_type: string;
  bid: number;
  ask: number;
  mark_price: number;
  mid_price: number;
  mark_iv: number;
  delta: number;
  open_interest: number;
  volume_24h: number;
  spread_pct: number;
  health_score: number;
  healthy: boolean;
  health_veto_reason?: string;
}

export interface TradeStructure {
  structure_type: string;
  direction: Direction;
  legs: CandidateContract[];
  max_loss?: number;
  max_gain?: number;
  net_premium: number;
  risk_reward?: number;
  score: number;
  score_breakdown: Record<string, number>;
}

export interface SizedTrade {
  structure: TradeStructure;
  contracts: number;
  position_value: number;
  max_risk_usd: number;
  capital_at_risk_pct: number;
}

export interface PaperPosition {
  id: string;
  underlying: string;
  sized_trade: SizedTrade;
  status: PositionStatus;
  entry_timestamp_ms: number;
  entry_spot_price: number;
  exit_timestamp_ms?: number;
  exit_spot_price?: number;
  realized_pnl_usd?: number;
  notes: string;
  run_once_state: TradeState;
}

export interface PositionListResponse {
  positions: PaperPosition[];
  open_count: number;
  closed_count: number;
}

export interface PreviewResponse {
  underlying: string;
  state: TradeState;
  direction: Direction;
  candidates: CandidateContract[];
  ranked_structures: TradeStructure[];
  ivr?: number;
  ivr_band: IVRBand;
  reason: string;
  timestamp_ms: number;
}

export interface RunOnceResponse {
  underlying: string;
  paper_mode: boolean;
  state: TradeState;
  direction: Direction;
  regime?: Record<string, unknown>;
  signal?: Record<string, unknown>;
  exec_mode: ExecMode;
  ivr?: number;
  ivr_band: IVRBand;
  ranked_structures: SizedTrade[];
  no_trade_score: number;
  recommendation: string;
  reason: string;
  timestamp_ms: number;
}
