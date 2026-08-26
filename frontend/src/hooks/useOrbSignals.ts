import { useQuery } from '@tanstack/react-query';
import { api } from '../utils/api';
import { toOrbFeedEntries, type OrbFeedEntry } from '../utils/niftyOrbSignalAdapter';

export function useOrbSignals(enabled = true) {
  const query = useQuery({
    queryKey: ['nifty-orb-options-scan'],
    queryFn: async (): Promise<OrbFeedEntry[]> => {
      const payload = await api.post('/api/v1/config/nifty-orb-options/scan', {});
      return toOrbFeedEntries(payload);
    },
    enabled,
    refetchInterval: enabled ? 5000 : false,
    refetchIntervalInBackground: false,
    staleTime: 2000,
    retry: 1,
  });

  return {
    ...query,
    signals: query.data ?? [],
    isRefreshing: query.isFetching,
  };
}
