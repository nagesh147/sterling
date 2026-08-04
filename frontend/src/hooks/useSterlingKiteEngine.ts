import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { api } from '../utils/api';
import { notifyOrder } from '../store/useKiteNotifications';
import type {
  ActivityResponse, BacktestRequest, BacktestResponse, EngineConfigModel,
  EngineDetailResponse, EngineOrderRequest, EngineOrderResponse, ExpiryCalendarResponse, LiquidityGroup,
  OpenPositionsResponse, SetupChart, SignalsResponse,
} from '../types/kiteEngine';

const E = '/api/v1/kite/engine';

// ─── Options backtest (workstream H) ─────────────────────────────────────────
export function useEngineBacktest() {
  return useMutation<BacktestResponse, Error, BacktestRequest>({
    mutationFn: (req) => api.post<BacktestResponse>(`${E}/backtest`, req),
  });
}

// ─── Signals (polled) ────────────────────────────────────────────────────────
// The backend now flushes rows symbol-by-symbol while a scan is running (see
// scanner.py), so poll fast during a scan to show setups landing on the go;
// fall back to a slow idle poll once scanning finishes.
export function useEngineSignals() {
  return useQuery<SignalsResponse>({
    queryKey: ['kite-engine-signals'],
    queryFn: () => api.get<SignalsResponse>(`${E}/signals`),
    refetchInterval: (query) => (query.state.data?.scanning ? 2_000 : 15_000),
  });
}

// ─── Stock registry (cached) ───────────────────────────────────────────────
export function useStockRegistry() {
  return useQuery<LiquidityGroup[]>({
    queryKey: ['kite-engine-stock-registry'],
    queryFn: () => api.get<LiquidityGroup[]>(`${E}/stock-registry`),
    staleTime: 300_000,
  });
}

// ─── Config ────────────────────────────────────────────────────────────────
export function useEngineConfig() {
  return useQuery<EngineConfigModel>({
    queryKey: ['kite-engine-config'],
    queryFn: () => api.get<EngineConfigModel>(`${E}/config`),
    staleTime: 30_000,
  });
}

// Exact contract dates from Kite's NFO/BFO instrument dump. The backend cache is
// hourly; a shorter query window lets an expiry-day rollover refresh automatically.
export function useExpiryCalendar() {
  return useQuery<ExpiryCalendarResponse>({
    queryKey: ['kite-engine-expiry-calendar'],
    queryFn: () => api.get<ExpiryCalendarResponse>(`${E}/expiry-calendar`),
    staleTime: 15 * 60_000,
    refetchInterval: 30 * 60_000,
    retry: 1,
  });
}

export function useSetEngineConfig() {
  const qc = useQueryClient();
  return useMutation<EngineConfigModel, Error, EngineConfigModel>({
    mutationFn: (body) => api.post<EngineConfigModel>(`${E}/config`, body),
    onSuccess: (data) => qc.setQueryData(['kite-engine-config'], data),
  });
}

export function useResetEngineConfig() {
  const qc = useQueryClient();
  return useMutation<EngineConfigModel, Error, void>({
    mutationFn: () => api.post<EngineConfigModel>(`${E}/config/reset`),
    onSuccess: (data) => {
      qc.setQueryData(['kite-engine-config'], data);
      notifyOrder({
        kind: 'info',
        title: 'Settings reset',
        message: 'Sterling Kite Engine configuration restored to defaults.',
      });
    },
  });
}

// ─── Scan trigger ────────────────────────────────────────────────────────────
export function useRunScan() {
  const qc = useQueryClient();
  return useMutation<SignalsResponse, Error, void>({
    mutationFn: () => api.post<SignalsResponse>(`${E}/scan`),
    // /scan blocks server-side until the whole scan finishes, so the mutation's
    // own promise can't show progress — that comes from the polling /signals
    // query instead. Flip it into "scanning" the instant the button is clicked
    // (rather than waiting for the query's own idle-interval timer to catch up,
    // which can leave the board on a stale/empty view for the entire scan) and
    // force an immediate refetch so real rows show up as soon as the backend
    // starts flushing them.
    onMutate: () => {
      qc.setQueryData<SignalsResponse>(['kite-engine-signals'], (prev) =>
        prev ? { ...prev, scanning: true } : prev);
      qc.invalidateQueries({ queryKey: ['kite-engine-signals'] });
    },
    onSuccess: (data) => qc.setQueryData(['kite-engine-signals'], data),
  });
}

// ─── Cancel scan (force-stop) ─────────────────────────────────────────────────
export function useCancelScan() {
  const qc = useQueryClient();
  return useMutation<SignalsResponse, Error, void>({
    mutationFn: () => api.post<SignalsResponse>(`${E}/scan/cancel`),
    onSuccess: (data) => qc.setQueryData(['kite-engine-signals'], data),
  });
}

// ─── Activity feed (terminal) ─────────────────────────────────────────────────
export function useEngineActivity() {
  return useQuery<ActivityResponse>({
    queryKey: ['kite-engine-activity'],
    queryFn: () => api.get<ActivityResponse>(`${E}/activity`),
    refetchInterval: 10_000,
  });
}

// ─── Server logs (real backend logs, interleaved into the terminal) ──────────
export interface ServerLogLine {
  ts_ms: number;
  level: string;
  name: string;
  message: string;
}
export function useEngineServerLogs(enabled: boolean) {
  return useQuery<{ logs: ServerLogLine[] }>({
    queryKey: ['kite-engine-server-logs'],
    queryFn: () => api.get<{ logs: ServerLogLine[] }>(`${E}/server-logs?limit=400`),
    refetchInterval: enabled ? 10_000 : false,
    enabled,
  });
}

// ─── Setup chart (click-to-visualize) ─────────────────────────────────────────
export function useEngineSetup(token: number | null, underlying: string, enabled: boolean) {
  return useQuery<SetupChart>({
    queryKey: ['kite-engine-setup', token, underlying],
    queryFn: () => api.get<SetupChart>(
      `${E}/setup/${token}?underlying=${encodeURIComponent(underlying)}`),
    enabled: enabled && token != null,
    staleTime: 60_000,
  });
}

// ─── Place a BUY/SELL through the engine path (logged to the terminal) ────────
export function useEnginePlaceOrder() {
  const qc = useQueryClient();
  return useMutation<EngineOrderResponse, Error, EngineOrderRequest>({
    mutationFn: (body) => api.post<EngineOrderResponse>(`${E}/order`, body),
    onSuccess: (data, body) => {
      qc.invalidateQueries({ queryKey: ['kite-engine-activity'] });
      notifyOrder({
        kind: data?.status === 'duplicate' ? 'info' : 'placed',
        title: data?.status === 'duplicate' ? 'Already submitted' : 'Order placed',
        message: `${body.side} ${body.quantity} ${body.option_symbol}.`,
        orderId: data?.order_id,
      });
    },
    onError: (err, body) => {
      notifyOrder({ kind: 'rejected', title: 'Order rejected', message: `${body.side} ${body.option_symbol} — ${err.message}` });
    },
  });
}

// ─── Signal detail (trigger info + live price + greeks + depth) ───────────────
// `source` disambiguates the row: a Navigator origination and a SuperTrend row
// for the same instrument share a token, so without it the server can answer a
// Navigator click with the SuperTrend row's entry, stop and legs.
export function useEngineDetail(
  token: number | null, timestamp_ms: number | null, enabled: boolean, source?: string,
) {
  return useQuery<EngineDetailResponse>({
    queryKey: ['kite-engine-detail', token, timestamp_ms, source ?? ''],
    queryFn: () => api.get<EngineDetailResponse>(
      `${E}/detail/${token}?timestamp_ms=${timestamp_ms || 0}`
      + (source ? `&source=${encodeURIComponent(source)}` : ''),
    ),
    enabled: enabled && token != null,
    refetchInterval: 15_000,
  });
}

// ─── Engine open positions (vehicle + direction labels) ───────────────────────
export function useEngineOpenPositions() {
  return useQuery<OpenPositionsResponse>({
    queryKey: ['kite-engine-open-positions'],
    queryFn: () => api.get<OpenPositionsResponse>(`${E}/open-positions`),
    refetchInterval: 10_000,
  });
}

export function useCloseEnginePosition() {
  const qc = useQueryClient();
  return useMutation<OpenPositionsResponse, Error, string>({
    mutationFn: (symbol) => api.delete<OpenPositionsResponse>(`${E}/open-positions/${encodeURIComponent(symbol)}`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['kite-engine-open-positions'] }),
  });
}
