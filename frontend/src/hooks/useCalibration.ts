import { useQuery } from '@tanstack/react-query';
import { api } from '../utils/api';

export interface CalibrationState {
  underlying: string;
  win_rate: number;
  ivr_buy_threshold: number;
  ivr_sell_threshold: number;
  trade_count: number;
  ivr_readings: number;
  note?: string;
}

export function useCalibration(underlying: string) {
  return useQuery<CalibrationState>({
    queryKey: ['calibration', underlying],
    queryFn: () => api.get<CalibrationState>(`/api/v1/risk/calibration/${underlying}`),
    refetchInterval: 30_000,
    enabled: !!underlying,
  });
}
