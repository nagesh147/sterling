import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { api } from '../utils/api';

export interface ExchangeConfigResponse {
  id: string;
  name: string;
  display_name: string;
  api_key_hint: string;
  is_paper: boolean;
  is_active: boolean;
  supported: boolean;
  has_credentials: boolean;
  extra: Record<string, unknown>;
}

export interface ExchangeListResponse {
  exchanges: ExchangeConfigResponse[];
  active_id: string | null;
  count: number;
}

export interface SupportedExchange {
  name: string;
  display_name: string;
}

export interface DataSourceResponse {
  exchange: string;
  display_name: string;
  reachable: boolean;
  adapter_stack: string;
  timestamp_ms: number;
}

export function useExchanges() {
  return useQuery<ExchangeListResponse>({
    queryKey: ['exchanges'],
    queryFn: () => api.get<ExchangeListResponse>('/api/v1/exchanges'),
    staleTime: 30_000,
  });
}

export function useSupportedExchanges() {
  return useQuery<{ exchanges: SupportedExchange[] }>({
    queryKey: ['exchanges-supported'],
    queryFn: () => api.get<{ exchanges: SupportedExchange[] }>('/api/v1/exchanges/supported'),
    staleTime: 300_000,
  });
}

export function useDataSource() {
  return useQuery<DataSourceResponse>({
    queryKey: ['data-source'],
    queryFn: () => api.get<DataSourceResponse>('/api/v1/config/data-source'),
    staleTime: 15_000,
    refetchInterval: 30_000,
  });
}

export function useSetDataSource() {
  const qc = useQueryClient();
  return useMutation<DataSourceResponse, Error, { exchange: string; api_key?: string; api_secret?: string }>({
    mutationFn: (body) => api.post<DataSourceResponse>('/api/v1/config/data-source', body),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['data-source'] });
      qc.invalidateQueries({ queryKey: ['config-info'] });
    },
  });
}

export function useActivateDataSource() {
  const qc = useQueryClient();
  return useMutation<{ message: string; reachable: boolean }, Error, string>({
    mutationFn: (id) =>
      api.post<{ message: string; reachable: boolean }>(`/api/v1/exchanges/${id}/activate-data-source`),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['data-source'] });
      qc.invalidateQueries({ queryKey: ['config-info'] });
    },
  });
}

export function useInvalidateCache() {
  const qc = useQueryClient();
  return useMutation<{ cleared: boolean }, Error, void>({
    mutationFn: () => api.post<{ cleared: boolean }>('/api/v1/config/data-source/invalidate-cache'),
    onSuccess: () => {
      // Refetch all market data
      qc.invalidateQueries({ queryKey: ['snapshot'] });
      qc.invalidateQueries({ queryKey: ['watchlist'] });
      qc.invalidateQueries({ queryKey: ['market-snapshot'] });
    },
  });
}

export function useAddExchange() {
  const qc = useQueryClient();
  return useMutation<ExchangeConfigResponse, Error, {
    name: string; display_name: string; api_key: string; api_secret: string;
    is_paper: boolean; extra?: Record<string, unknown>;
  }>({
    mutationFn: (body) => api.post<ExchangeConfigResponse>('/api/v1/exchanges', body),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['exchanges'] }),
  });
}

export function useUpdateExchange() {
  const qc = useQueryClient();
  return useMutation<ExchangeConfigResponse, Error, {
    id: string; api_key?: string; api_secret?: string; is_paper?: boolean;
    display_name?: string; extra?: Record<string, unknown>;
  }>({
    mutationFn: ({ id, ...body }) => api.put<ExchangeConfigResponse>(`/api/v1/exchanges/${id}`, body),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['exchanges'] }),
  });
}

export function useActivateExchange() {
  const qc = useQueryClient();
  return useMutation<ExchangeConfigResponse, Error, string>({
    mutationFn: (id) => api.post<ExchangeConfigResponse>(`/api/v1/exchanges/${id}/activate`),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['exchanges'] });
      qc.invalidateQueries({ queryKey: ['account'] });
    },
  });
}

export function useDeleteExchange() {
  const qc = useQueryClient();
  return useMutation<void, Error, string>({
    mutationFn: (id) => api.delete<void>(`/api/v1/exchanges/${id}`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['exchanges'] }),
  });
}

export function useTestConnection() {
  return useMutation<{ connected: boolean; message?: string; error?: string; is_paper?: boolean }, Error, string>({
    mutationFn: (id) =>
      api.post<{ connected: boolean; message?: string; error?: string; is_paper?: boolean }>(
        `/api/v1/exchanges/${id}/test`
      ),
  });
}
