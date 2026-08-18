import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { api } from '../utils/api';

export type OrbConfig = {
  enabled: boolean;
  universe: string;
  instruments: string[];
  instrument_types: string[];
  expiry_dte_min: number;
  expiry_dte_max: number;
  expiry_preference: 'NEAREST' | 'WEEKLY' | 'MONTHLY' | 'DTE_RANGE';
  interval_minutes: number;
  opening_range_minutes: number;
  entry_start: string;
  entry_end: string;
  breakout_atr: number;
  atr_period: number;
  volume_multiplier: number;
  option_moneyness: 'ATM' | 'ITM';
  option_steps_itm: number;
  max_risk_inr: number;
  max_trades_per_day: number;
  max_signals_per_day: number;
  avoid_expiry_day: boolean;
  paper_only: boolean;
  data_source: 'kite' | 'truedata';
  execution_broker: 'kite';
  option_entry_side: 'BUY';
};

const key = ['orb-momentum-options-config'];

export function useOrbMomentumOptionsConfig() {
  return useQuery<{ config: OrbConfig; strategy: string; option_entry: string }>({
    queryKey: key,
    queryFn: () => api.get('/orb-momentum-options/config'),
    staleTime: 30_000,
  });
}

export function useSetOrbMomentumOptionsConfig() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (config: Partial<OrbConfig>) => api.put('/orb-momentum-options/config', config),
    onSuccess: () => qc.invalidateQueries({ queryKey: key }),
  });
}

export function useOrbMomentumOptionsSignals() {
  return useQuery({
    queryKey: ['orb-momentum-options-signals'],
    queryFn: () => api.get('/orb-momentum-options/signals'),
    refetchInterval: 5_000,
  });
}
