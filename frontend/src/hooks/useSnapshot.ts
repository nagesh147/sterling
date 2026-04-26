import { useQuery } from '@tanstack/react-query';
import { api } from '../utils/api';

export interface DirectionalSnapshot {
  underlying: string;
  spot_price: number;
  perp_price: number;
  macro_regime: string;
  ema50: number;
  regime_score: number;
  signal_trend: number;
  all_green: boolean;
  all_red: boolean;
  green_arrow: boolean;
  red_arrow: boolean;
  st_trends: number[];
  st_values: number[];
  score_long: number;
  score_short: number;
  close_1h: number;
  ivr?: number;
  ivr_band: string;
  state: string;
  direction: string;
  setup_reason: string;
  exec_mode: string;
  exec_confidence: number;
  exec_reason: string;
  timestamp_ms: number;
}

export function useSnapshot(underlying: string) {
  return useQuery<DirectionalSnapshot>({
    queryKey: ['snapshot', underlying],
    queryFn: () =>
      api.get<DirectionalSnapshot>(
        `/api/v1/directional/snapshot?underlying=${underlying}`
      ),
    refetchInterval: 20_000,
    enabled: !!underlying,
  });
}
