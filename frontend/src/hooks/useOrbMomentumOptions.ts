import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { api } from '../utils/api';

export type OrbConfig = {
  enabled: boolean;
  underlying: string;
  interval_minutes: number;
  opening_range_minutes: number;
  entry_start: string;
  entry_end: string;
  min_breakout_atr: number;
  volume_multiplier: number;
  vwap_slope_lookback: number;
  trend_lookback: number;
  atr_period: number;
  stop_buffer_atr: number;
  trail_atr: number;
  target_r: number;
  option_moneyness: string;
  option_steps_itm: number;
  max_risk_inr: number;
  max_trades_per_day: number;
  avoid_expiry_day: boolean;
  expiry_selection: string;
  execution_broker: string;
  data_source: 'kite' | 'truedata';
  paper_only: boolean;
};

const key = ['nifty-orb-options-config'];

export function useOrbMomentumOptionsConfig() {
  return useQuery<{ config: OrbConfig; supported_data_sources: string[]; execution_brokers: string[] }>({
    queryKey: key,
    queryFn: () => api.get('/config/nifty-orb-options'),
    staleTime: 30_000,
  });
}

export function useSetOrbMomentumOptionsConfig() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (config: Partial<OrbConfig>) => api.put('/config/nifty-orb-options', config),
    onSuccess: () => qc.invalidateQueries({ queryKey: key }),
  });
}

export function useOrbMomentumOptionsSnapshot() {
  return useQuery({
    queryKey: ['nifty-orb-options-snapshot'],
    queryFn: () => api.post('/config/nifty-orb-options/snapshot', {}),
    refetchInterval: 5_000,
  });
}
