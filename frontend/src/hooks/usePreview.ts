import { useQuery } from '@tanstack/react-query';
import { api } from '../utils/api';
import type { PreviewResponse } from '../types';

export function usePreview(underlying: string) {
  return useQuery<PreviewResponse>({
    queryKey: ['preview', underlying],
    queryFn: () =>
      api.get<PreviewResponse>(
        `/api/v1/directional/preview?underlying=${underlying}`
      ),
    refetchInterval: 60_000,
    enabled: !!underlying,
  });
}
