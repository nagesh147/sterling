import { useMutation } from '@tanstack/react-query';
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
  return useMutation<MonitorResult, Error, string>({
    mutationFn: (posId) =>
      api.post<MonitorResult>(`/api/v1/positions/${posId}/monitor`),
  });
}
