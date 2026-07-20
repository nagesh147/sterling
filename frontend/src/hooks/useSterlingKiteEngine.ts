import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { api } from '../utils/api';
import { notifyOrder } from '../store/useKiteNotifications';
import type {
  ActivityResponse, BacktestRequest, BacktestResponse, EngineConfigModel,
  EngineDetailResponse, EngineOrderRequest, EngineOrderResponse, LiquidityGroup,
  OpenPositionsResponse, ScanReportResponse, SetupChart, SignalsResponse,
} from '../types/kiteEngine';

const E = '/api/v1/kite/engine';

// ─── Options backtest (workstream H) ─────────────────────────────────────────
export function useEngineBacktest() {
  return useMutation<BacktestResponse, Error, BacktestRequest>({
    mutationFn: (req) => api.post<BacktestResponse>(`${E}/backtest`, req),
  });
}

// ─── Signals (polled) ────────────────────────────────────────────────────────
export function useEngineSignals() {
  return useQuery<SignalsResponse>({
    queryKey: ['kite-engine-signals'],
    queryFn: () => api.get<SignalsResponse>(`${E}/signals`),
    refetchInterval: 15_000,
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

// ─── Per-contract scan report ───────────────────────────────────────────────
export function useScanReport() {
  return useQuery<ScanReportResponse>({
    queryKey: ['kite-engine-scan-report'],
    queryFn: () => api.get<ScanReportResponse>(`${E}/scan-report`),
    staleTime: 120_000,
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
export function useEngineDetail(token: number | null, timestamp_ms: number | null, enabled: boolean) {
  return useQuery<EngineDetailResponse>({
    queryKey: ['kite-engine-detail', token, timestamp_ms],
    queryFn: () => api.get<EngineDetailResponse>(`${E}/detail/${token}?timestamp_ms=${timestamp_ms || 0}`),
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