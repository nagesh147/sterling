import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { api } from '../utils/api';

const KEY = ['nifty-orb-options-config'];

export interface OrbRuntimeConfig {
  enabled: boolean;
  data_source: 'kite' | 'truedata';
  entry_start: string;
  entry_end: string;
  max_trades_per_day: number;
  [field: string]: unknown;
}

/** Shared with the settings panel, so enabling from either place updates both. */
export function useOrbConfig() {
  return useQuery<{ config: OrbRuntimeConfig }>({
    queryKey: KEY,
    queryFn: () => api.get('/api/v1/config/nifty-orb-options'),
    staleTime: 30000,
  });
}

export function useSetOrbEnabled() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (enabled: boolean) => api.put('/api/v1/config/nifty-orb-options', { enabled }),
    onSuccess: (result) => {
      qc.setQueryData(KEY, result);
      // The feed is gated on `enabled`, so it must refetch, not wait out its interval.
      qc.invalidateQueries({ queryKey: ['nifty-orb-options-scan'] });
    },
  });
}
