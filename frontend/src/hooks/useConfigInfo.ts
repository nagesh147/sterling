import { useQuery } from '@tanstack/react-query';
import { api } from '../utils/api';

export interface SystemInfo {
  version: string;
  environment: string;
  exchange_adapter: string;
  paper_trading: boolean;
  real_public_data: boolean;
  default_underlying: string;
  supported_underlyings: string[];
  underlyings_with_options: string[];
  adapter_stack: string;
  db_path: string;
  timestamp_ms: number;
}

export function useConfigInfo() {
  return useQuery<SystemInfo>({
    queryKey: ['config-info'],
    queryFn: () => api.get<SystemInfo>('/api/v1/config/info'),
    staleTime: 300_000,  // 5min — doesn't change at runtime
  });
}
