import { useQuery } from '@tanstack/react-query';
import { api } from '../utils/api';

export interface SystemInfo {
  version: string;
  environment: string;
  exchange_adapter: string;
  active_data_source: string;
  data_source_display: string;
  paper_trading: boolean;
  real_public_data: boolean;
  default_underlying: string;
  supported_underlyings: string[];
  underlyings_with_options: string[];
  adapter_stack: string;
  db_path: string;
  supported_data_sources: Record<string, string>;
  timestamp_ms: number;
}

export function useConfigInfo() {
  return useQuery<SystemInfo>({
    queryKey: ['config-info'],
    queryFn: () => api.get<SystemInfo>('/api/v1/config/info'),
    staleTime: 15_000,
    refetchInterval: 30_000,
  });
}
