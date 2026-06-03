import { useQuery } from '@tanstack/react-query';
import { api } from '../utils/api';

export interface V2Config {
  enabled: boolean;
  paper_only: boolean;
  auto_execute: boolean;
}

export function useV2Config() {
  return useQuery<V2Config>({
    queryKey: ['sterling-v2', 'config'],
    queryFn: () => api.get<V2Config>('/api/v1/sterling-v2/config'),
  });
}
