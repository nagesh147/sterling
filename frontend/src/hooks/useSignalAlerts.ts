import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useAppStream } from './useAppStream';
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
  const { data, status } = useAppStream<SignalAlertsResponse>('alerts');
  return {
    data: data ?? undefined,
    isLoading: status === 'connecting' && data == null,
    isError: false,
  };
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

// Mirrors backend LiveOrderResponse (trading.py). Note: backend reports success
// via `status`/`message` — there is no `accepted` or `reason` field.
export interface LiveOrderResponse {
  mode: string;
  order_id?: string | null;
  paper_position_id?: string | null;
  symbol: string;
  side: string;
  size: number;
  entry_price?: number | null;
  stop_loss?: number | null;
  take_profit?: number | null;
  leverage?: number | null;
  status: string;
  message: string;
  timestamp_ms: number;
}

export function usePlaceOrder() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (req: LiveOrderRequest) =>
      api.post<LiveOrderResponse>('/api/v1/trading/place-order', req),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['positions'] });
      qc.invalidateQueries({ queryKey: ['live-pnl'] });
      qc.invalidateQueries({ queryKey: ['signal-alerts'] });
    },
  });
}

export interface AlgoModeResponse {
  enabled: boolean;
}

export function useAlgoMode() {
  return useQuery<AlgoModeResponse>({
    queryKey: ['algo-mode'],
    queryFn: () => api.get<AlgoModeResponse>('/api/v1/trading/algo-mode'),
    staleTime: 0,
  });
}

export function useSetAlgoMode() {
  const qc = useQueryClient();
  return useMutation<AlgoModeResponse, Error, boolean>({
    mutationFn: (enabled) =>
      api.post<AlgoModeResponse>('/api/v1/trading/algo-mode', { enabled }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['algo-mode'] }),
  });
}
