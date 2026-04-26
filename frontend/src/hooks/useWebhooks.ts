import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { api } from '../utils/api';

export type WebhookType = 'discord' | 'telegram' | 'generic';

export interface WebhookConfig {
  id: string;
  name: string;
  webhook_type: WebhookType;
  url: string;
  extra: Record<string, unknown>;
  active: boolean;
  created_at_ms: number;
  last_triggered_ms: number | null;
  trigger_count: number;
}

export interface WebhookListResponse {
  webhooks: WebhookConfig[];
  count: number;
}

export function useWebhooks() {
  return useQuery<WebhookListResponse>({
    queryKey: ['webhooks'],
    queryFn: () => api.get<WebhookListResponse>('/api/v1/webhooks'),
    staleTime: 30_000,
  });
}

export function useAddWebhook() {
  const qc = useQueryClient();
  return useMutation<WebhookConfig, Error, {
    name: string; webhook_type: WebhookType; url: string; extra?: Record<string, unknown>; active?: boolean;
  }>({
    mutationFn: (body) => api.post<WebhookConfig>('/api/v1/webhooks', body),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['webhooks'] }),
  });
}

export function useDeleteWebhook() {
  const qc = useQueryClient();
  return useMutation<void, Error, string>({
    mutationFn: (id) => api.delete<void>(`/api/v1/webhooks/${id}`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['webhooks'] }),
  });
}

export function useToggleWebhook() {
  const qc = useQueryClient();
  return useMutation<WebhookConfig, Error, string>({
    mutationFn: (id) => api.post<WebhookConfig>(`/api/v1/webhooks/${id}/toggle`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['webhooks'] }),
  });
}

export function useTestWebhook() {
  return useMutation<{ delivered: boolean; error?: string }, Error, string>({
    mutationFn: (id) =>
      api.post<{ delivered: boolean; error?: string }>(`/api/v1/webhooks/${id}/test`),
  });
}
