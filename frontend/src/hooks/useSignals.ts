import { useQuery } from '@tanstack/react-query';
import { api } from '../utils/api';

export interface SignalItem {
  underlying: string;
  has_options: boolean;
  spot_price: number | null;
  ivr: number | null;
  green_arrow: boolean;
  red_arrow: boolean;
  state: string;
  direction: string;
  regime: string;
  score_long: number;
  score_short: number;
  exec_mode: string | null;
  fresh: boolean;
  timestamp_ms: number;
}

export interface SignalsResponse {
  signals: SignalItem[];
  count: number;
  timestamp_ms: number;
}

export function useSignals() {
  return useQuery<SignalsResponse>({
    queryKey: ['signals-all'],
    queryFn: () => api.get<SignalsResponse>('/api/v1/directional/signals'),
    refetchInterval: 15_000,
  });
}
