import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { api } from '../utils/api';

export interface RiskParams {
  capital: number;
  max_position_pct: number;
  max_contracts: number;
  partial_profit_r1: number;
  partial_profit_r2: number;
  time_stop_dte: number;
  financial_stop_pct: number;
  win_rate: number;
}

export function useRiskConfig() {
  return useQuery<RiskParams>({
    queryKey: ['risk-config'],
    queryFn: () => api.get<RiskParams>('/api/v1/config/risk'),
    staleTime: 60_000,
  });
}

export function useUpdateRiskConfig() {
  const qc = useQueryClient();
  return useMutation<RiskParams, Error, RiskParams>({
    mutationFn: (params) => api.put<RiskParams>('/api/v1/config/risk', params),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['risk-config'] }),
  });
}

export function useResetRiskConfig() {
  const qc = useQueryClient();
  return useMutation<RiskParams, Error, void>({
    mutationFn: () => api.post<RiskParams>('/api/v1/config/risk/reset'),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['risk-config'] }),
  });
}

export interface DailyLossConfig {
  enabled: boolean;
  pnl_usd: number;
  level: string;
  soft_warn_usd: number;
  hard_halt_usd: number;
  timestamp_ms: number;
}

export function useDailyLossConfig() {
  return useQuery<DailyLossConfig>({
    queryKey: ['daily-loss-config'],
    queryFn: () => api.get<DailyLossConfig>('/api/v1/risk/daily-loss'),
    staleTime: 5000,
  });
}

export function useUpdateDailyLossConfig() {
  const qc = useQueryClient();
  return useMutation<DailyLossConfig, Error, { enabled: boolean; soft_warn_usd: number; hard_halt_usd: number }>({
    mutationFn: (params) => api.post<DailyLossConfig>('/api/v1/risk/daily-loss', params),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['daily-loss-config'] }),
  });
}
