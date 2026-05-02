import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { api } from '../utils/api';

export type AlertCondition =
  | 'price_above' | 'price_below'
  | 'ivr_above' | 'ivr_below'
  | 'signal_green_arrow' | 'signal_red_arrow'
  | 'state_is';

export type AlertStatus = 'active' | 'triggered' | 'dismissed';

export interface Alert {
  id: string;
  underlying: string;
  condition: AlertCondition;
  threshold: number | null;
  target_state: string | null;
  cooldown_hours: number;
  notes: string;
  status: AlertStatus;
  triggered_at_ms: number | null;
  trigger_value: number | null;
  fire_count: number;
  created_at_ms: number;
}

export interface AlertListResponse {
  alerts: Alert[];
  active_count: number;
  triggered_count: number;
}

export interface AlertCheckResponse {
  checked: number;
  newly_triggered: number;
  results: Array<{
    alert_id: string;
    triggered: boolean;
    message: string;
    current_value: number | null;
  }>;
  timestamp_ms: number;
}

const CONDITION_LABELS: Record<AlertCondition, string> = {
  price_above: 'Price >', price_below: 'Price <',
  ivr_above: 'IVR >', ivr_below: 'IVR <',
  signal_green_arrow: 'Green Arrow', signal_red_arrow: 'Red Arrow',
  state_is: 'State =',
};

export { CONDITION_LABELS };

export function useAlerts(qs = '') {
  return useQuery<AlertListResponse>({
    queryKey: ['alerts', qs],
    queryFn: () => api.get<AlertListResponse>(`/api/v1/alerts${qs}`),
    refetchInterval: 15_000,
  });
}

export function useCreateAlert() {
  const qc = useQueryClient();
  return useMutation<Alert, Error, {
    underlying: string; condition: AlertCondition; threshold?: number;
    target_state?: string; notes?: string; cooldown_hours?: number;
  }>({
    mutationFn: (body) => api.post<Alert>('/api/v1/alerts', body),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['alerts'] }),
  });
}

export function useBulkClearDismissed() {
  const qc = useQueryClient();
  return useMutation<void, Error, void>({
    mutationFn: () => api.delete<void>('/api/v1/alerts'),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['alerts'] }),
  });
}

export function useCheckAlerts() {
  const qc = useQueryClient();
  return useMutation<AlertCheckResponse, Error, void>({
    mutationFn: () => api.post<AlertCheckResponse>('/api/v1/alerts/check'),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['alerts'] }),
  });
}

export function useDismissAlert() {
  const qc = useQueryClient();
  return useMutation<Alert, Error, string>({
    mutationFn: (id) => api.post<Alert>(`/api/v1/alerts/${id}/dismiss`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['alerts'] }),
  });
}

export function useDeleteAlert() {
  const qc = useQueryClient();
  return useMutation<void, Error, string>({
    mutationFn: (id) => api.delete<void>(`/api/v1/alerts/${id}`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['alerts'] }),
  });
}
