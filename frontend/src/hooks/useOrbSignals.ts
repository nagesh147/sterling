import { useQuery } from '@tanstack/react-query';
import { api } from '../utils/api';
import { toOrbFeedEntries, type OrbFeedEntry } from '../utils/niftyOrbSignalAdapter';

import { useSimActive } from './useSimulation';

export function useOrbSignals(enabled = true) {
  const isSimActive = useSimActive();
  const query = useQuery({
    queryKey: ['nifty-orb-options-scan'],
    queryFn: async (): Promise<OrbFeedEntry[]> => {
      const payload = await api.post('/api/v1/config/nifty-orb-options/scan', {});
      return toOrbFeedEntries(payload);
    },
    enabled,
    refetchInterval: enabled ? (isSimActive ? 300 : 2000) : false,
    refetchIntervalInBackground: false,
    staleTime: isSimActive ? 0 : 2000,
    retry: 1,
  });

  return {
    ...query,
    signals: query.data ?? [],
    isRefreshing: query.isFetching,
  };
}
