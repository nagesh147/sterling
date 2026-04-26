import { useQuery } from '@tanstack/react-query';
import { api } from '../utils/api';
import type { InstrumentListResponse } from '../types';

export function useInstruments() {
  return useQuery<InstrumentListResponse>({
    queryKey: ['instruments'],
    queryFn: () => api.get<InstrumentListResponse>('/api/v1/instruments'),
    staleTime: 5 * 60 * 1000,
  });
}
