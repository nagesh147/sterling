import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { api } from '../utils/api';

export interface SignalAlert {
  id: string;
  underlying: string;
  state: string;
  state_label: string;
  direction: string;
  regime: string;
  entry: number;
  stop_loss: number | null;
  take_profit: number | null;
  risk_pct: number;
  score: number;
  atr: number;
  adx: number;
  rsi: number;
  futures_symbol: string;
  rec_leverage: number;
  opt_strike: number | null;
  opt_type: string | null;
  opt_expiry: string | null;
  opt_symbol: string | null;
  timestamp_ms: number;
  fresh: boolean;
}

export interface SignalAlertsResponse {
  alerts: SignalAlert[];
  count: number;
  timestamp_ms: number;
}

export function useSignalAlerts() {
  return useQuery<SignalAlertsResponse>({
    queryKey: ['signal-alerts'],
    queryFn: () => api.get<SignalAlertsResponse>('/api/v1/directional/signal-alerts'),
    refetchInterval: 10_000,
  });
}

export interface LiveOrderRequest {
  underlying: string;
  direction: string;
  instrument_type: string;
  size: number;
  leverage: number;
  order_type: string;
  limit_price?: number;
  stop_loss?: number | null;
  take_profit?: number | null;
  option_symbol?: string | null;
  notes: string;
}

export function usePlaceOrder() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (req: LiveOrderRequest) =>
      api.post('/api/v1/trading/place-order', req),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['positions'] });
      qc.invalidateQueries({ queryKey: ['live-pnl'] });
      qc.invalidateQueries({ queryKey: ['signal-alerts'] });
    },
  });
}
