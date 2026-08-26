import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { api } from '../utils/api';
import { notifyOrder } from '../store/useKiteNotifications';
import type { AdaptiveEdgeSettings, AdaptiveEdgeSnapshot } from '../types/adaptiveEdge';

const ROOT = '/api/v1/adaptive-edge';

export function useAdaptiveEdgeSnapshot() {
  return useQuery<AdaptiveEdgeSnapshot>({
    queryKey: ['adaptive-edge-snapshot'],
    queryFn: () => api.get<AdaptiveEdgeSnapshot>(`${ROOT}/snapshot`),
    refetchInterval: 5000,
  });
}

export function useAdaptiveEdgeSettings() {
  return useQuery<{ settings: AdaptiveEdgeSettings; live_trading: boolean }>({
    queryKey: ['adaptive-edge-settings'],
    queryFn: () => api.get(`${ROOT}/settings`),
  });
}

export function useSetAdaptiveEdgeSettings() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (settings: AdaptiveEdgeSettings) => api.put(`${ROOT}/settings`, settings),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['adaptive-edge-settings'] });
      qc.invalidateQueries({ queryKey: ['adaptive-edge-snapshot'] });
      notifyOrder({ kind: 'info', title: 'Adaptive Edge settings saved', message: 'Research policy only. Live trading stays blocked.' });
    },
  });
}
