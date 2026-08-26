import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { api } from '../utils/api';

const KEY = ['nifty-orb-options-config'];

export interface OrbConfig {
  enabled: boolean;
  underlying: string;
  scan_indices: string[];
  scan_stocks: string[];
  scan_all_stocks: boolean;
  scan_stock_contracts: boolean;
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
  target_r: number;
  option_moneyness: string;
  option_steps_itm: number;
  max_risk_inr: number;
  max_trades_per_day: number;
  avoid_expiry_day: boolean;
  expiry_selection: string;
  expiry_dte_min: number;
  expiry_dte_max: number;
  execution_broker: string;
  data_source: 'kite' | 'truedata';
  max_spread_pct: number;
  min_option_volume: number;
  min_open_interest: number;
  max_quote_staleness_s: number;
  risk_free_rate: number;
  truedata_use_ticks: boolean;
  truedata_use_oi: boolean;
  truedata_use_bid_ask: boolean;
  truedata_use_quote_freshness: boolean;
}

export interface OrbConfigResponse {
  config: OrbConfig;
  /** The engine's own defaults, published so the UI never mirrors a second copy. */
  defaults: OrbConfig;
  supported_data_sources: string[];
  execution_brokers: string[];
}

export function useOrbConfig() {
  return useQuery<OrbConfigResponse>({
    queryKey: KEY,
    queryFn: () => api.get('/api/v1/config/nifty-orb-options'),
    staleTime: 30000,
  });
}

/** Patch any subset of the config. The scan is gated on it, so it must refetch. */
export function useSetOrbConfig() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: Partial<OrbConfig>) => api.put('/api/v1/config/nifty-orb-options', body),
    onSuccess: (result) => {
      qc.setQueryData(KEY, result);
      qc.invalidateQueries({ queryKey: ['nifty-orb-options-scan'] });
    },
  });
}

export function useSetOrbEnabled() {
  const set = useSetOrbConfig();
  return { ...set, mutate: (enabled: boolean) => set.mutate({ enabled }) };
}
