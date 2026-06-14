import { useEffect, useRef, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { api } from '../utils/api';
import type {
  CreateAlertBody, HoldingsAuthResult, KiteAccount, KiteAccountList, KiteAlert,
  KiteAlertHistoryRow, KiteInstrumentSearch, KiteOrderUpdate, KiteSessionResult,
  KiteStatus, KiteTickerStatus, MfInstrumentSearch, ModifyMfSipBody, PlaceGttBody,
  PlaceMfSipBody, PlaceOrderBody, WatchItem,
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

export function useRefreshKiteSession() {
  const qc = useQueryClient();
  return useMutation<KiteSessionResult, Error, { refresh_token?: string; account_id?: string }>({
    mutationFn: (body) => api.post<KiteSessionResult>(`${K}/session/refresh`, body),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['kite-status'] });
      qc.invalidateQueries({ queryKey: ['kite-accounts'] });
    },
  });
}

// Background session-keeper: auto-recovers a lapsed Kite session using the stored
// refresh_token — no manual "Refresh" click. Reactive (not a token-churning timer):
// it only acts when the status poll reports the active account is NOT connected,
// and also retries when the tab/window regains focus. Best-effort + debounced;
// failures are swallowed (Zerodha may still require the daily 2FA login, which
// this cannot bypass). Mount once where the Kite UI lives.
export function useKiteAutoSession(enabled = true) {
  const { data: status } = useKiteStatus();
  const refresh = useRefreshKiteSession();
  const lastAttempt = useRef(0);
  const refreshRef = useRef(refresh);
  refreshRef.current = refresh;

  // Only auto-recover when Kite actually issued a refresh_token at login — otherwise
  // a renewal is impossible and the daily 2FA re-login is the only path (don't spam it).
  const needsRecovery = !!(status?.account_id && !status.connected && status.has_refresh_token);

  const tryRecover = (minGapMs: number) => {
    if (!enabled || !needsRecovery) return;
    const now = Date.now();
    if (now - lastAttempt.current < minGapMs) return;
    if (refreshRef.current.isPending) return;
    lastAttempt.current = now;
    // empty body → backend uses the refresh_token captured at login
    refreshRef.current.mutate({});
  };

  // Attempt as soon as a lapse is detected (status polls every ~30s).
  useEffect(() => {
    tryRecover(45_000);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [needsRecovery, enabled]);

  // Attempt when the user returns to the tab (e.g. next morning).
  useEffect(() => {
    if (!enabled) return;
    const onFocus = () => tryRecover(20_000);
    window.addEventListener('focus', onFocus);
    document.addEventListener('visibilitychange', onFocus);
    return () => {
      window.removeEventListener('focus', onFocus);
      document.removeEventListener('visibilitychange', onFocus);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [enabled, needsRecovery]);

  return { recovering: refresh.isPending, needsRecovery };
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
  return useQuery<{ net: any[]; day: any[] }>({
    queryKey: ['kite-positions'],
    queryFn: () => api.get(`${K}/positions`),
    enabled,
    refetchInterval: 5_000,
  });
}

export function useKiteAuctions(enabled = true) {
  return useQuery<any[]>({
    queryKey: ['kite-auctions'],
    queryFn: () => api.get(`${K}/auctions`),
    enabled,
    refetchInterval: 60_000,
  });
}

export function useKiteCorporateActions(enabled = true) {
  return useQuery<any[]>({
    queryKey: ['kite-corporate-actions'],
    queryFn: () => api.get(`${K}/corporate-actions`),
    enabled,
    refetchInterval: 60_000,
  });
}

export function useKiteIPOs(enabled = true) {
  return useQuery<any[]>({
    queryKey: ['kite-ipos'],
    queryFn: () => api.get(`${K}/ipos`),
    enabled,
    refetchInterval: 60_000,
  });
}

// CDSL holdings authorisation (eDIS) — returns a consent URL the caller opens so
// the user can enter their TPIN; required before holdings can be sold via API.
export function useInitiateHoldingsAuth() {
  return useMutation<HoldingsAuthResult, Error, { instruments?: Array<{ isin: string; quantity?: number }> }>({
    mutationFn: (body) => api.post<HoldingsAuthResult>(`${K}/holdings/authorise`, { instruments: body.instruments ?? [] }),
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

export function useModifyKiteOrder() {
  const qc = useQueryClient();
  return useMutation<any, Error, { id: string; variety?: string; quantity?: number; price?: number; order_type?: string; trigger_price?: number; validity?: string }>({
    mutationFn: ({ id, ...body }) => api.put(`${K}/orders/${id}`, body),
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

export function useKiteTrades(enabled = true) {
  return useQuery<any[]>({
    queryKey: ['kite-trades'],
    queryFn: () => api.get(`${K}/trades`),
    enabled,
    refetchInterval: 10_000,
  });
}

export function useKiteOrderHistory(orderId: string | null) {
  return useQuery<any[]>({
    queryKey: ['kite-order-history', orderId],
    queryFn: () => api.get(`${K}/orders/${orderId}/history`),
    enabled: !!orderId,
    staleTime: 5_000,
  });
}

export function useKiteOrderTrades(orderId: string | null) {
  return useQuery<any[]>({
    queryKey: ['kite-order-trades', orderId],
    queryFn: () => api.get(`${K}/orders/${orderId}/trades`),
    enabled: !!orderId,
    staleTime: 10_000,
  });
}

// ─── Profile / funds ────────────────────────────────────────────────────────
export function useKiteProfile(enabled = true) {
  return useQuery<any>({
    queryKey: ['kite-profile'],
    queryFn: () => api.get(`${K}/profile`),
    enabled,
    staleTime: 60_000,
  });
}

// ─── Mutual funds ─────────────────────────────────────────────────────────────
export function useKiteMfHoldings(enabled = true) {
  return useQuery<any[]>({ queryKey: ['kite-mf-holdings'], queryFn: () => api.get(`${K}/mf/holdings`), enabled, refetchInterval: 60_000 });
}
export function useKiteMfOrders(enabled = true) {
  return useQuery<any[]>({ queryKey: ['kite-mf-orders'], queryFn: () => api.get(`${K}/mf/orders`), enabled, refetchInterval: 60_000 });
}
export function useKiteMfSips(enabled = true) {
  return useQuery<any[]>({ queryKey: ['kite-mf-sips'], queryFn: () => api.get(`${K}/mf/sips`), enabled, refetchInterval: 60_000 });
}

export function usePlaceKiteMfOrder() {
  const qc = useQueryClient();
  return useMutation<any, Error, Record<string, unknown>>({
    mutationFn: (body) => api.post(`${K}/mf/orders`, body),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['kite-mf-orders'] }),
  });
}

export function useCancelKiteMfOrder() {
  const qc = useQueryClient();
  return useMutation<any, Error, string>({
    mutationFn: (orderId) => api.delete(`${K}/mf/orders/${orderId}`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['kite-mf-orders'] }),
  });
}

export function useKiteMfOrderDetail(orderId: string | null) {
  return useQuery<any>({
    queryKey: ['kite-mf-order', orderId],
    queryFn: () => api.get(`${K}/mf/orders/${orderId}`),
    enabled: !!orderId,
    staleTime: 10_000,
  });
}

// MF scheme master search (drives the SIP/fund autocomplete).
export function useKiteMfInstrumentSearch(query: string) {
  return useQuery<MfInstrumentSearch>({
    queryKey: ['kite-mf-instruments', query],
    queryFn: () => api.get<MfInstrumentSearch>(`${K}/mf/instruments?query=${encodeURIComponent(query)}&limit=25`),
    enabled: query.trim().length >= 2,
    staleTime: 5 * 60_000,
  });
}

export function usePlaceKiteMfSip() {
  const qc = useQueryClient();
  return useMutation<any, Error, PlaceMfSipBody>({
    mutationFn: (body) => api.post(`${K}/mf/sips`, body),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['kite-mf-sips'] }),
  });
}

export function useModifyKiteMfSip() {
  const qc = useQueryClient();
  return useMutation<any, Error, { id: string } & ModifyMfSipBody>({
    mutationFn: ({ id, ...body }) => api.put(`${K}/mf/sips/${id}`, body),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['kite-mf-sips'] }),
  });
}

export function useCancelKiteMfSip() {
  const qc = useQueryClient();
  return useMutation<any, Error, string>({
    mutationFn: (sipId) => api.delete(`${K}/mf/sips/${sipId}`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['kite-mf-sips'] }),
  });
}

// ─── Positions: convert ───────────────────────────────────────────────────────
export function useConvertKitePosition() {
  const qc = useQueryClient();
  return useMutation<any, Error, Record<string, unknown>>({
    mutationFn: (body) => api.put(`${K}/positions/convert`, body),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['kite-positions'] }),
  });
}

// ─── Margin / charges calculators ─────────────────────────────────────────────
export function useKiteOrderMargins() {
  return useMutation<any, Error, any[]>({
    mutationFn: (orders) => api.post(`${K}/margins/orders`, orders),
  });
}

export function useKiteBasketMargins() {
  return useMutation<any, Error, { orders: any[]; consider_positions?: boolean }>({
    mutationFn: (body) => api.post(`${K}/margins/basket${body.consider_positions ? '?consider_positions=true' : ''}`, body.orders),
  });
}

export function useKiteOrderCharges() {
  return useMutation<any, Error, any[]>({
    mutationFn: (orders) => api.post(`${K}/charges/orders`, orders),
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

export function useKiteGttDetail(triggerId: number | null) {
  return useQuery<any>({
    queryKey: ['kite-gtt-detail', triggerId],
    queryFn: () => api.get(`${K}/gtt/${triggerId}`),
    enabled: triggerId != null,
    staleTime: 10_000,
  });
}

export function useModifyKiteGtt() {
  const qc = useQueryClient();
  return useMutation<any, Error, { id: number } & Partial<PlaceGttBody>>({
    mutationFn: ({ id, ...body }) => api.put(`${K}/gtt/${id}`, body),
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

// Bulk EXCHANGE:TRADINGSYMBOL → lot_size (found instruments only). Lets the
// market watch size F&O orders without a per-order lookup in the ticket.
export function useKiteInstrumentLots(symbols: string[]) {
  const key = [...symbols].sort().join(',');
  return useQuery<Record<string, number>>({
    queryKey: ['kite-instrument-lots', key],
    queryFn: () => api.get<Record<string, number>>(`${K}/instruments/lots?symbols=${encodeURIComponent(key)}`),
    enabled: symbols.length > 0,
    staleTime: 3_600_000,
  });
}

export function useKiteQuote(symbols: string[], enabled = true) {
  return useQuery<Record<string, any>>({
    queryKey: ['kite-quote', symbols.join(',')],
    queryFn: () => api.get(`${K}/quote?${iParams(symbols)}`),
    enabled: enabled && symbols.length > 0,
    refetchInterval: 15_000,
  });
}

export function useKiteOhlc(symbols: string[], enabled = true) {
  return useQuery<Record<string, any>>({
    queryKey: ['kite-ohlc', symbols.join(',')],
    queryFn: () => api.get(`${K}/ohlc?${iParams(symbols)}`),
    enabled: enabled && symbols.length > 0,
    refetchInterval: 30_000,
  });
}

export function useKiteHistorical(params: { token: number; interval: string; from: string; to: string; continuous?: boolean; oi?: boolean }, enabled = true) {
  return useQuery<any>({
    queryKey: ['kite-historical', params],
    queryFn: () => api.get(`${K}/historical?token=${params.token}&interval=${params.interval}&from=${encodeURIComponent(params.from)}&to=${encodeURIComponent(params.to)}${params.continuous ? '&continuous=true' : ''}${params.oi ? '&oi=true' : ''}`),
    enabled,
    staleTime: 120_000,
  });
}

// Sync watchlist from the Kite account (holdings + positions + GTT instruments).
// Kite Connect has no saved-marketwatch endpoint, so this is the account-derived set.
export interface KiteWatchlistSync {
  items: WatchItem[];
  count: number;
  sources: Record<string, number>;
  note: string;
}

export function useSyncKiteWatchlist() {
  return useMutation<KiteWatchlistSync, Error, void>({
    mutationFn: () => api.get<KiteWatchlistSync>(`${K}/watchlist/sync`),
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
    setItems((p) => {
      if (p.some((x) => x.symbol === it.symbol)) return p;
      if (p.length >= 50) return p; // Enforce 50 item limit
      return [...p, it];
    });
  const remove = (symbol: string) => setItems((p) => p.filter((x) => x.symbol !== symbol));
  // Backfill lot sizes onto items that don't have one yet (persists to storage).
  const mergeLots = (map: Record<string, number>) =>
    setItems((p) => {
      let changed = false;
      const next = p.map((x) => {
        if (x.lot_size == null && map[x.symbol] != null) { changed = true; return { ...x, lot_size: map[x.symbol] }; }
        return x;
      });
      return changed ? next : p;
    });
  const reorder = (startIndex: number, endIndex: number) => {
    setItems((p) => {
      const result = Array.from(p);
      const [removed] = result.splice(startIndex, 1);
      result.splice(endIndex, 0, removed);
      return result;
    });
  };
  const clear = () => setItems([]);
  return { items, add, remove, reorder, clear, mergeLots };
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

export function useKiteTickerUnsubscribe() {
  return useMutation<any, Error, { instrument_tokens: number[] }>({
    mutationFn: (body) => api.post(`${K}/ticker/unsubscribe`, body),
  });
}

// ─── Native alerts ──────────────────────────────────────────────────────────
export function useKiteAlerts(enabled = true) {
  return useQuery<KiteAlert[]>({
    queryKey: ['kite-alerts'],
    queryFn: () => api.get(`${K}/alerts`),
    enabled,
    refetchInterval: 30_000,
  });
}

export function useCreateKiteAlert() {
  const qc = useQueryClient();
  return useMutation<KiteAlert, Error, CreateAlertBody>({
    mutationFn: (body) => api.post(`${K}/alerts`, body),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['kite-alerts'] }),
  });
}

export function useModifyKiteAlert() {
  const qc = useQueryClient();
  return useMutation<KiteAlert, Error, { uuid: string } & Partial<CreateAlertBody> & { status?: string }>({
    mutationFn: ({ uuid, ...body }) => api.put(`${K}/alerts/${uuid}`, body),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['kite-alerts'] }),
  });
}

export function useDeleteKiteAlerts() {
  const qc = useQueryClient();
  return useMutation<any, Error, string[]>({
    mutationFn: (uuids) => api.delete(`${K}/alerts`, { uuids }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['kite-alerts'] }),
  });
}

export function useKiteAlertHistory(uuid: string | null) {
  return useQuery<KiteAlertHistoryRow[]>({
    queryKey: ['kite-alert-history', uuid],
    queryFn: () => api.get(`${K}/alerts/${uuid}/history`),
    enabled: !!uuid,
    staleTime: 10_000,
  });
}

// ─── Live order updates (Kite postbacks over the stream WS) ───────────────────
// Subscribes to the per-user `kite_orders` channel on /api/v1/stream/ws. On every
// order-state change it refreshes the orders/positions/trades caches and surfaces
// the latest update (for a toast). Mirrors the binary tick fan-out path.
const STREAM_WS_URL =
  ((import.meta.env.VITE_API_BASE_URL as string | undefined) ?? 'http://localhost:8000')
    .replace(/^http/, 'ws') + '/api/v1/stream/ws';

export function useKiteOrderUpdates(enabled = true, userId = 'default') {
  const qc = useQueryClient();
  const [last, setLast] = useState<KiteOrderUpdate | null>(null);
  const wsRef = useRef<WebSocket | null>(null);

  useEffect(() => {
    if (!enabled) return;
    let alive = true;
    let retry: number | null = null;

    const connect = () => {
      if (!alive) return;
      const ws = new WebSocket(STREAM_WS_URL);
      wsRef.current = ws;
      ws.onopen = () => ws.send(JSON.stringify({ action: 'subscribe', channel: `kite_orders:${userId}` }));
      ws.onmessage = (ev) => {
        try {
          const msg = JSON.parse(ev.data);
          if (msg.type === 'kite_order_update' && msg.order) {
            setLast(msg.order as KiteOrderUpdate);
            qc.invalidateQueries({ queryKey: ['kite-orders'] });
            qc.invalidateQueries({ queryKey: ['kite-positions'] });
            qc.invalidateQueries({ queryKey: ['kite-trades'] });
          }
        } catch { /* ignore non-JSON frames */ }
      };
      ws.onclose = () => {
        wsRef.current = null;
        if (alive) retry = window.setTimeout(connect, 3000);
      };
      ws.onerror = () => ws.close();
    };
    connect();

    return () => {
      alive = false;
      if (retry) window.clearTimeout(retry);
      wsRef.current?.close();
      wsRef.current = null;
    };
  }, [enabled, userId, qc]);

  return last;
}
