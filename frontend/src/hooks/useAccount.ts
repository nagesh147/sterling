import { useQuery } from '@tanstack/react-query';
import { api } from '../utils/api';

export interface AssetBalance {
  asset: string;
  available: number;
  locked: number;
  total: number;
  usd_value: number | null;
}

export interface AccountPosition {
  symbol: string;
  underlying: string;
  size: number;
  side: string;
  entry_price: number;
  mark_price: number;
  unrealized_pnl: number;
  realized_pnl: number;
  margin: number;
  leverage: number | null;
  position_type: string;
  created_at_ms: number | null;
}

export interface AccountOrder {
  order_id: string;
  symbol: string;
  side: string;
  size: number;
  price: number;
  filled_size: number;
  status: string;
  order_type: string;
  created_at_ms: number;
}

export interface AccountFill {
  fill_id: string;
  order_id: string;
  symbol: string;
  side: string;
  size: number;
  price: number;
  fee: number;
  fee_asset: string;
  pnl: number;
  created_at_ms: number;
}

export interface PortfolioSnapshot {
  exchange: string;
  display_name: string;
  total_balance_usd: number;
  unrealized_pnl_usd: number;
  realized_pnl_usd: number;
  margin_used: number;
  margin_available: number;
  positions_count: number;
  open_orders_count: number;
  balances: AssetBalance[];
  timestamp_ms: number;
}

export interface AccountSummary {
  exchange_id: string;
  exchange_name: string;
  display_name: string;
  is_paper: boolean;
  is_connected: boolean;
  portfolio: PortfolioSnapshot | null;
  error: string | null;
  timestamp_ms: number;
}

export interface AccountInfo {
  active: boolean;
  exchange_id?: string;
  exchange_name?: string;
  display_name?: string;
  is_paper?: boolean;
  api_key_hint?: string;
  timestamp_ms?: number;
}

export function useAccountInfo() {
  return useQuery<AccountInfo>({
    queryKey: ['account', 'info'],
    queryFn: () => api.get<AccountInfo>('/api/v1/account/info'),
    refetchInterval: 60_000,
  });
}

export function useAccountSummary() {
  return useQuery<AccountSummary>({
    queryKey: ['account', 'summary'],
    queryFn: () => api.get<AccountSummary>('/api/v1/account/summary'),
    refetchInterval: 30_000,
    retry: false,
  });
}

export function useAccountBalances() {
  return useQuery<{ exchange: string; is_paper: boolean; balances: AssetBalance[]; count: number; timestamp_ms: number }>({
    queryKey: ['account', 'balances'],
    queryFn: () => api.get('/api/v1/account/balances'),
    refetchInterval: 30_000,
    retry: false,
  });
}

export function useAccountPositions(underlying = '') {
  return useQuery<{ exchange: string; is_paper: boolean; positions: AccountPosition[]; count: number; timestamp_ms: number }>({
    queryKey: ['account', 'positions', underlying],
    queryFn: () => api.get(`/api/v1/account/positions${underlying ? `?underlying=${underlying}` : ''}`),
    refetchInterval: 15_000,
    retry: false,
  });
}

export function useAccountOrders(underlying = '') {
  return useQuery<{ exchange: string; is_paper: boolean; orders: AccountOrder[]; count: number; timestamp_ms: number }>({
    queryKey: ['account', 'orders', underlying],
    queryFn: () => api.get(`/api/v1/account/orders${underlying ? `?underlying=${underlying}` : ''}`),
    refetchInterval: 15_000,
    retry: false,
  });
}

export function useAccountFills(limit = 50) {
  return useQuery<{ exchange: string; is_paper: boolean; fills: AccountFill[]; count: number; timestamp_ms: number }>({
    queryKey: ['account', 'fills', limit],
    queryFn: () => api.get(`/api/v1/account/fills?limit=${limit}`),
    refetchInterval: 30_000,
    retry: false,
  });
}
