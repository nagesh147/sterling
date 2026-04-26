import { useQuery } from '@tanstack/react-query';
import { api } from '../utils/api';
import type { MarketSnapshotResponse } from '../types';

export function useMarketSnapshot(underlying: string) {
  return useQuery<MarketSnapshotResponse>({
    queryKey: ['market-snapshot', underlying],
    queryFn: () =>
      api.get<MarketSnapshotResponse>(
        `/api/v1/directional/debug/market-snapshot?underlying=${underlying}`
      ),
    refetchInterval: 15_000,
    enabled: !!underlying,
  });
}
