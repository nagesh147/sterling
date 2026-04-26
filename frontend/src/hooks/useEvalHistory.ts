import { useQuery } from '@tanstack/react-query';
import { api } from '../utils/api';

export interface EvalHistoryItem {
  state: string;
  direction: string;
  recommendation: string;
  no_trade_score: number;
  ivr?: number;
  timestamp_ms: number;
}

export interface EvalHistoryResponse {
  underlying: string;
  history: EvalHistoryItem[];
  count: number;
}

export function useEvalHistory(underlying: string) {
  return useQuery<EvalHistoryResponse>({
    queryKey: ['eval-history', underlying],
    queryFn: () =>
      api.get<EvalHistoryResponse>(`/api/v1/directional/history/${underlying}`),
    refetchInterval: 60_000,
    enabled: !!underlying,
  });
}
