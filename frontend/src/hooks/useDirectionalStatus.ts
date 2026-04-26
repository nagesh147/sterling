import { useQuery } from '@tanstack/react-query';
import { api } from '../utils/api';
import type { DirectionalStatusResponse } from '../types';

export function useDirectionalStatus(underlying: string) {
  return useQuery<DirectionalStatusResponse>({
    queryKey: ['directional-status', underlying],
    queryFn: () =>
      api.get<DirectionalStatusResponse>(
        `/api/v1/directional/status?underlying=${underlying}`
      ),
    refetchInterval: 30_000,
    enabled: !!underlying,
  });
}
