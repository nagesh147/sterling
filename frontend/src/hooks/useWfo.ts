import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { api } from '../utils/api';

export function useWfoState() {
  return useQuery({
    queryKey: ['wfo-state'],
    queryFn: async () => {
      const data = await api.get<any>('/api/v1/wfo/state');
      return data;
    },
    refetchInterval: 10000, // Poll every 10s to see if impact report is done
  });
}

export function useWfoLogs(lines: number = 100) {
  return useQuery({
    queryKey: ['wfo-logs', lines],
    queryFn: async () => {
      const data = await api.get<any>(`/api/v1/wfo/logs?lines=${lines}`);
      return data;
    },
    refetchInterval: 3000, // Fast polling while running
  });
}

export function useRunWfo() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async () => {
      const data = await api.post<any>('/api/v1/wfo/run');
      return data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['wfo-state'] });
      queryClient.invalidateQueries({ queryKey: ['wfo-logs'] });
    }
  });
}
