// Zerodha Kite — frontend types (mirrors backend app/services/exchanges/kite/models.py)

export interface KiteAccount {
  id: string;
  user_id: string;
  label: string;
  api_key_hint: string;
  has_credentials: boolean;
  is_paper: boolean;
  is_active: boolean;
  connected: boolean;
  kite_user_id?: string | null;
  last_login_at_ms?: number | null;
  created_at_ms: number;
  updated_at_ms: number;
}

export interface KiteAccountList {
  accounts: KiteAccount[];
  active_id: string | null;
  count: number;
}

export interface KiteStatus {
  connected: boolean;
  is_paper: boolean;
  account_id?: string | null;
  kite_user_id?: string | null;
  user_name?: string | null;
  message: string;
}

export interface KiteSessionResult {
  connected: boolean;
  kite_user_id?: string | null;
  user_name?: string | null;
  email?: string | null;
  login_time?: string | null;
}

export interface KiteInstrument {
  instrument_token: number;
  tradingsymbol: string;
  name?: string;
  segment?: string;
  exchange?: string;
  last_price?: number;
  expiry?: string;
  strike?: number;
  lot_size?: number;
  instrument_type?: string;
}

export interface KiteInstrumentSearch {
  exchange: string;
  query: string;
  count: number;
  instruments: KiteInstrument[];
}

export interface WatchItem {
  symbol: string;   // EXCHANGE:TRADINGSYMBOL (LTP key)
  token: number;
  name: string;
  sub?: string;     // short descriptor (e.g. "NFO · CE 25000")
}

export interface KitePosition {
  symbol: string;
  underlying: string;
  size: number;
  side: string;
  entry_price: number;
  mark_price: number;
  unrealized_pnl: number;
  realized_pnl: number;
  margin: number;
  position_type: string;
}

export interface PlaceOrderBody {
  tradingsymbol: string;
  exchange: string;
  transaction_type: 'BUY' | 'SELL';
  quantity: number;
  order_type: 'MARKET' | 'LIMIT' | 'SL' | 'SL-M';
  product: 'MIS' | 'CNC' | 'NRML';
  variety?: string;
  price?: number | null;
  trigger_price?: number | null;
  validity?: string;
  tag?: string | null;
}

export interface PlaceGttBody {
  trigger_type: 'single' | 'two-leg';
  tradingsymbol: string;
  exchange: string;
  last_price: number;
  trigger_values: number[];
  orders: Array<{
    tradingsymbol: string;
    exchange: string;
    transaction_type: 'BUY' | 'SELL';
    quantity: number;
    order_type: string;
    product: string;
    price: number;
  }>;
}

export interface KiteTickerStatus {
  active: boolean;
  connected: boolean;
  subscribed: number[];
  tick_count: number;
}
