import { useQuery } from '@tanstack/react-query';
import { api } from '../utils/api';

export interface NiftyOrbSignal {
  underlying: string;
  status: 'signal' | 'signal_unresolved' | 'watching' | 'no_data' | 'error';
  spot?: number;
  interval_minutes?: number;
  data_source?: 'kite' | 'truedata';
  signal?: {
    direction: 'LONG' | 'SHORT' | 'NONE';
    regime: string;
    timestamp: string | null;
    or_high: number;
    or_low: number;
    vwap: number;
    atr: number;
    breakout_distance: number;
    volume_ratio: number;
    confidence: number;
    reason: string;
  } | null;
  trade?: {
    direction: 'LONG' | 'SHORT';
    option_type: 'CE' | 'PE';
    underlying_entry: number;
    underlying_stop: number;
    initial_risk_points: number;
    target_points: number;
    entry_premium: number;
    stop_premium: number;
    target_premium: number;
    quantity: number;
    risk_inr: number;
    contract: {
      symbol: string;
      strike: number;
      expiry: string;
      option_type: 'CE' | 'PE';
      ltp: number;
      bid: number;
      ask: number;
      lot_size: number;
      volume: number;
      open_interest: number;
    };
  } | null;
  trade_error?: string;
  error?: string;
}

export interface NiftyOrbSignalsResponse {
  enabled: boolean;
  universe: string[];
  signals: NiftyOrbSignal[];
  signal_count: number;
  data_source?: 'kite' | 'truedata';
}

export function useNiftyOrbSignals(enabled = true) {
  return useQuery<NiftyOrbSignalsResponse>({
    queryKey: ['nifty-orb-options-signals'],
    queryFn: () => api.post('/api/v1/config/nifty-orb-options/scan', {}),
    enabled,
    refetchInterval: enabled ? 5000 : false,
    refetchIntervalInBackground: true,
    staleTime: 2500,
  });
}
