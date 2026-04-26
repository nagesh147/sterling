import { useMutation, useQueryClient } from '@tanstack/react-query';
import { api } from '../utils/api';

export interface ExitSignal {
  should_exit: boolean;
  reason: string;
  exit_type?: string;
  partial: boolean;
  partial_ratio: number;
}

export interface MonitorResult {
  position_id: string;
  underlying: string;
  exit_signal: ExitSignal;
  current_spot: number;
  estimated_pnl_usd: number;
  current_dte: number;
  current_signal_trend: number;
  timestamp_ms: number;
}

export function useMonitorPosition() {
  const qc = useQueryClient();
  return useMutation<MonitorResult, Error, string>({
    mutationFn: (posId) =>
      api.post<MonitorResult>(`/api/v1/positions/${posId}/monitor`),
    onSuccess: (data) => {
      // Auto-refresh positions list if exit was triggered or partial applied
      if (data.exit_signal.should_exit || data.exit_signal.partial) {
        qc.invalidateQueries({ queryKey: ['positions'] });
        qc.invalidateQueries({ queryKey: ['portfolio-summary'] });
      }
    },
  });
}

export function useMonitorAll() {
  const qc = useQueryClient();
  return useMutation<unknown, Error, void>({
    mutationFn: () => api.post('/api/v1/positions/monitor-all'),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['positions'] });
      qc.invalidateQueries({ queryKey: ['portfolio-summary'] });
    },
  });
}
