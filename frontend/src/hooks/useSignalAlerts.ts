import { useAppStream } from './useAppStream';

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
