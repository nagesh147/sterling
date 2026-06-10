import { useQuery } from '@tanstack/react-query';
import { api } from '../utils/api';

export interface PaperPosition {
  symbol: string;
  sleeve?: string;
  direction: string;
  entry_time?: string;
  entry_price?: number;
  sl?: number;
  tp?: number;
  mtm_price?: number;
  unrealized_pnl?: number;
  stop_dist_pct?: number;
  weight?: number;
}

export interface PaperState {
  available: boolean;
  reason?: string;
  total_equity?: number;
  return_pct?: number;
  realized?: { end?: number; ret?: number; sharpe?: number; max_dd?: number; n?: number };
  equity_curve?: number[];
  open_positions?: PaperPosition[];
  breaker?: { peak?: number; drawdown?: number; tripped?: boolean; threshold?: number; recover?: number };
  buffer_to_trip?: number;
  tripped?: boolean;
  asof?: string;
  inception?: string;
  n_closed?: number;
  capital?: number;
}

export interface PaperTrade {
  entry_time: string;
  exit_time: string;
  symbol: string;
  sleeve: string;
  direction: string;
  status: string;
  pnl_pct: number;
  stop_dist_pct: number;
}

export interface PaperTrades {
  available: boolean;
  trades: PaperTrade[];
  n: number;
}

export interface PaperSummary {
  available: boolean;
  dsr: number;
  oos_sharpe: number;
  oos_return_pct: number;
  is_oos_corr: number;
  provable: boolean;
  verdict: string;
  provenance: string;
}

export function usePaperState() {
  return useQuery<PaperState>({
    queryKey: ['paper', 'state'],
    queryFn: () => api.get<PaperState>('/api/v1/paper/state'),
  });
}

export function usePaperTrades() {
  return useQuery<PaperTrades>({
    queryKey: ['paper', 'trades'],
    queryFn: () => api.get<PaperTrades>('/api/v1/paper/trades'),
  });
}

export function usePaperSummary() {
  return useQuery<PaperSummary>({
    queryKey: ['paper', 'summary'],
    queryFn: () => api.get<PaperSummary>('/api/v1/paper/summary'),
  });
}
