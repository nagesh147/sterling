import { useQuery } from '@tanstack/react-query';
import { api } from '../utils/api';
import type { CandidateContract } from '../types';

export interface IVStats {
  atm_iv: number | null;
  min_iv: number;
  max_iv: number;
  avg_iv: number;
  iv_skew: number;
  sample_count: number;
}

export interface OptionChainResponse {
  underlying: string;
  spot_price: number;
  exchange: string;
  total_contracts: number;
  healthy_contracts: number;
  expiry_count: number;
  filter: { type: string; min_dte: number; max_dte: number };
  iv_stats: IVStats;
  by_expiry: Record<string, CandidateContract[]>;
  timestamp_ms: number;
}

export function useOptionChain(
  underlying: string,
  type: 'call' | 'put' | 'all' = 'all',
  minDte = 5,
  maxDte = 45,
) {
  return useQuery<OptionChainResponse>({
    queryKey: ['option-chain', underlying, type, minDte, maxDte],
    queryFn: () =>
      api.get<OptionChainResponse>(
        `/api/v1/options/chain?underlying=${underlying}&type=${type}&min_dte=${minDte}&max_dte=${maxDte}`
      ),
    refetchInterval: 60_000,
    enabled: !!underlying,
  });
}
