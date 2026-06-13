import { useEffect, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { api } from '../utils/api';
import type {
  KiteAccount, KiteAccountList, KiteInstrumentSearch, KitePosition, KiteSessionResult,
  KiteStatus, KiteTickerStatus, PlaceGttBody, PlaceOrderBody, WatchItem,
} from '../types/kite';

const K = '/api/v1/kite';

function iParams(symbols: string[]): string {
  return symbols.map((s) => `i=${encodeURIComponent(s)}`).join('&');
}

// ─── Accounts (credentials CRUD) ──────────────────────────────────────────────
export function useKiteAccounts() {
  return useQuery<KiteAccountList>({
    queryKey: ['kite-accounts'],
    queryFn: () => api.get<KiteAccountList>(`${K}/accounts`),
    staleTime: 15_000,
  });
}

export function useAddKiteAccount() {
  const qc = useQueryClient();
  return useMutation<KiteAccount, Error, { label: string; api_key: string; api_secret: string; is_paper: boolean }>({
    mutationFn: (body) => api.post<KiteAccount>(`${K}/accounts`, body),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['kite-accounts'] }),
  });
}

export function useUpdateKiteAccount() {
  const qc = useQueryClient();
  return useMutation<KiteAccount, Error, { id: string; label?: string; api_key?: string; api_secret?: string; is_paper?: boolean }>({
    mutationFn: ({ id, ...body }) => api.put<KiteAccount>(`${K}/accounts/${id}`, body),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['kite-accounts'] }),
  });
}

export function useDeleteKiteAccount() {
  const qc = useQueryClient();
  return useMutation<void, Error, string>({
    mutationFn: (id) => api.delete<void>(`${K}/accounts/${id}`),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['kite-accounts'] }); qc.invalidateQueries({ queryKey: ['kite-status'] }); },
  });
}

export function useActivateKiteAccount() {
  const qc = useQueryClient();
  return useMutation<KiteAccount, Error, string>({
    mutationFn: (id) => api.post<KiteAccount>(`${K}/accounts/${id}/activate`),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['kite-accounts'] }); qc.invalidateQueries({ queryKey: ['kite-status'] }); },
  });
}

export function useTestKiteAccount() {
  return useMutation<{ connected: boolean; message?: string; error?: string; is_paper?: boolean }, Error, string>({
    mutationFn: (id) => api.post(`${K}/accounts/${id}/test`),
  });
}

// ─── Session / login ──────────────────────────────────────────────────────────
export function useKiteStatus() {
  return useQuery<KiteStatus>({
    queryKey: ['kite-status'],
    queryFn: () => api.get<KiteStatus>(`${K}/status`),
    refetchInterval: 30_000,
  });
}

export function useKiteLoginUrl(enabled: boolean) {
  return useQuery<{ login_url: string }>({
    queryKey: ['kite-login-url'],
    queryFn: () => api.get<{ login_url: string }>(`${K}/login-url`),
    enabled,
    staleTime: 60_000,
  });
}

export function useGenerateKiteSession() {
  const qc = useQueryClient();
  return useMutation<KiteSessionResult, Error, { request_token: string; account_id?: string }>({
    mutationFn: (body) => api.post<KiteSessionResult>(`${K}/session`, body),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['kite-status'] });
      qc.invalidateQueries({ queryKey: ['kite-accounts'] });
    },
  });
}

export function useKiteLogout() {
  const qc = useQueryClient();
  return useMutation<{ ok: boolean }, Error, void>({
    mutationFn: () => api.post(`${K}/logout`),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['kite-status'] }); qc.invalidateQueries({ queryKey: ['kite-accounts'] }); },
  });
}

// ─── Funds / portfolio ────────────────────────────────────────────────────────
export function useKiteMargins(enabled = true) {
  return useQuery<Record<string, any>>({
    queryKey: ['kite-margins'],
    queryFn: () => api.get(`${K}/margins`),
    enabled,
    refetchInterval: 20_000,
  });
}

export function useKiteHoldings(enabled = true) {
  return useQuery<any[]>({
    queryKey: ['kite-holdings'],
    queryFn: () => api.get(`${K}/holdings`),
    enabled,
    refetchInterval: 15_000,
  });
}

export function useKitePositions(enabled = true) {
  return useQuery<{ positions: KitePosition[] }>({
    queryKey: ['kite-positions'],
    queryFn: () => api.get(`${K}/positions`),
    enabled,
    refetchInterval: 5_000,
  });
}

// ─── Orders ───────────────────────────────────────────────────────────────────
export function useKiteOrders(enabled = true) {
  return useQuery<any[]>({
    queryKey: ['kite-orders'],
    queryFn: () => api.get(`${K}/orders`),
    enabled,
    refetchInterval: 5_000,
  });
}

export function usePlaceKiteOrder() {
  const qc = useQueryClient();
  return useMutation<any, Error, PlaceOrderBody>({
    mutationFn: (body) => api.post(`${K}/orders`, body),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['kite-orders'] }),
  });
}

export function useCancelKiteOrder() {
  const qc = useQueryClient();
  return useMutation<any, Error, { id: string; variety?: string }>({
    mutationFn: ({ id, variety = 'regular' }) => api.delete(`${K}/orders/${id}?variety=${variety}`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['kite-orders'] }),
  });
}

// ─── GTT ──────────────────────────────────────────────────────────────────────
export function useKiteGtts(enabled = true) {
  return useQuery<any[]>({
    queryKey: ['kite-gtt'],
    queryFn: () => api.get(`${K}/gtt`),
    enabled,
    refetchInterval: 15_000,
  });
}

export function usePlaceKiteGtt() {
  const qc = useQueryClient();
  return useMutation<any, Error, PlaceGttBody>({
    mutationFn: (body) => api.post(`${K}/gtt`, body),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['kite-gtt'] }),
  });
}

export function useDeleteKiteGtt() {
  const qc = useQueryClient();
  return useMutation<any, Error, number>({
    mutationFn: (id) => api.delete(`${K}/gtt/${id}`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['kite-gtt'] }),
  });
}

// ─── Market data ──────────────────────────────────────────────────────────────
// Universal search across all segments (equities, futures, options incl. strikes,
// indices, currencies, commodities) — like the Zerodha Kite app search box.
export function useKiteInstrumentSearch(query: string) {
  return useQuery<KiteInstrumentSearch>({
    queryKey: ['kite-instruments', query],
    queryFn: () => api.get<KiteInstrumentSearch>(`${K}/instruments?query=${encodeURIComponent(query)}&limit=50`),
    enabled: query.trim().length >= 2,
    staleTime: 60_000,
  });
}

// Persisted market watchlist (localStorage → survives pane switches + refresh).
const WATCH_KEY = 'sterling.kite.watchlist.v1';

export function useKiteWatchlist() {
  const [items, setItems] = useState<WatchItem[]>(() => {
    try { return JSON.parse(localStorage.getItem(WATCH_KEY) || '[]'); } catch { return []; }
  });
  useEffect(() => {
    try { localStorage.setItem(WATCH_KEY, JSON.stringify(items)); } catch { /* quota — ignore */ }
  }, [items]);
  const add = (it: WatchItem) =>
    setItems((p) => (p.some((x) => x.symbol === it.symbol) ? p : [...p, it]));
  const remove = (symbol: string) => setItems((p) => p.filter((x) => x.symbol !== symbol));
  const clear = () => setItems([]);
  return { items, add, remove, clear };
}

export function useKiteLtp(symbols: string[], enabled = true) {
  return useQuery<Record<string, { last_price?: number; instrument_token?: number }>>({
    queryKey: ['kite-ltp', symbols.join(',')],
    queryFn: () => api.get(`${K}/ltp?${iParams(symbols)}`),
    enabled: enabled && symbols.length > 0,
    refetchInterval: 5_000,
  });
}

// ─── Ticker ───────────────────────────────────────────────────────────────────
export function useKiteTickerStatus(enabled = true) {
  return useQuery<KiteTickerStatus>({
    queryKey: ['kite-ticker-status'],
    queryFn: () => api.get(`${K}/ticker/status`),
    enabled,
    refetchInterval: 10_000,
  });
}

export function useKiteTickerSubscribe() {
  return useMutation<any, Error, { instrument_tokens: number[]; mode?: string }>({
    mutationFn: (body) => api.post(`${K}/ticker/subscribe`, { mode: 'quote', ...body }),
  });
}
