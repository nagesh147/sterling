import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { api } from '../utils/api';
import { notifyOrder } from '../store/useKiteNotifications';
import type {
  ActivityResponse, EngineConfigModel, EngineDetailResponse, EngineOrderRequest,
  EngineOrderResponse, SetupChart, SignalsResponse,
} from '../types/kiteEngine';

const E = '/api/v1/kite/engine';

// ─── Signals (polled) ────────────────────────────────────────────────────────
export function useEngineSignals() {
  return useQuery<SignalsResponse>({
    queryKey: ['kite-engine-signals'],
    queryFn: () => api.get<SignalsResponse>(`${E}/signals`),
    refetchInterval: 15_000,
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

// ─── Scan trigger ────────────────────────────────────────────────────────────
export function useRunScan() {
  const qc = useQueryClient();
  return useMutation<SignalsResponse, Error, void>({
    mutationFn: () => api.post<SignalsResponse>(`${E}/scan`),
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
export function useEngineDetail(token: number | null, enabled: boolean) {
  return useQuery<EngineDetailResponse>({
    queryKey: ['kite-engine-detail', token],
    queryFn: () => api.get<EngineDetailResponse>(`${E}/detail/${token}`),
    enabled: enabled && token != null,
    refetchInterval: 15_000,
  });
}
