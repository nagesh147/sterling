import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { api } from '../utils/api';
import { useSetTradingModeStore } from '../store/useStore';

export interface TradingModeConfig {
  name: string;
  display: string;
  macro_tf: string;
  signal_tf: string;
  execution_tf: string;
  st_threshold: number;
  macro_filter: string;
  dte_min: number;
  dte_preferred: [number, number];
  dte_max: number;
  ivr_pct_naked_max: number;
  stop_atr_mult: number;
  trail_mode: string;
  trail_atr_mult: number;
  trail_pct: number;
  rr_target: number;
  position_pct: number;
  max_concurrent: number;
  poll_interval_s: number;
}

export interface TradingModeResponse {
  name: string;
  config: TradingModeConfig;
}

export function useTradingMode() {
  return useQuery<TradingModeResponse>({
    queryKey: ['trading-mode'],
    queryFn: () => api.get<TradingModeResponse>('/api/v1/config/trading-mode'),
    refetchOnWindowFocus: true,
    staleTime: 30_000,
  });
}

export function useSetTradingMode() {
  const qc = useQueryClient();
  const setStore = useSetTradingModeStore();
  return useMutation<TradingModeResponse, Error, { name: string }>({
    mutationFn: ({ name }) =>
      api.put<TradingModeResponse>('/api/v1/config/trading-mode', { name }),
    onSuccess: (data) => {
      setStore(data.name);
      qc.invalidateQueries({ queryKey: ['trading-mode'] });
    },
  });
}

export function useAllTradingModes() {
  return useQuery<Record<string, TradingModeConfig>>({
    queryKey: ['trading-mode-all'],
    queryFn: () => api.get<Record<string, TradingModeConfig>>('/api/v1/config/trading-mode/all'),
    staleTime: 60_000,
  });
}
