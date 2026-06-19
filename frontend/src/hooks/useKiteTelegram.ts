// Kite-specific Telegram targets — TanStack Query hooks.
// Uses the same api client / base-url pattern as useKite.ts (api.get/post/put/delete
// against `/api/v1/kite/...`). Every mutation invalidates the targets list so the
// UI reflects the server state without a manual refetch.
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { api } from '../utils/api';
import type {
  KiteTelegramTarget, KiteTelegramTargetIn, KiteTelegramTargetList, KiteTelegramTargetPatch,
} from '../types/kiteTelegram';

const K = '/api/v1/kite/telegram';
const KEY = ['kite-telegram-targets'];

export function useKiteTelegramTargets() {
  return useQuery<KiteTelegramTargetList>({
    queryKey: KEY,
    queryFn: () => api.get<KiteTelegramTargetList>(K),
    staleTime: 30_000,
  });
}

export function useAddKiteTelegram() {
  const qc = useQueryClient();
  return useMutation<KiteTelegramTarget, Error, KiteTelegramTargetIn>({
    mutationFn: (body) => api.post<KiteTelegramTarget>(K, body),
    onSuccess: () => qc.invalidateQueries({ queryKey: KEY }),
  });
}

export function useUpdateKiteTelegram() {
  const qc = useQueryClient();
  return useMutation<KiteTelegramTarget, Error, { id: string } & KiteTelegramTargetPatch>({
    mutationFn: ({ id, ...body }) => api.put<KiteTelegramTarget>(`${K}/${id}`, body),
    onSuccess: () => qc.invalidateQueries({ queryKey: KEY }),
  });
}

export function useDeleteKiteTelegram() {
  const qc = useQueryClient();
  return useMutation<{ ok: boolean }, Error, string>({
    mutationFn: (id) => api.delete<{ ok: boolean }>(`${K}/${id}`),
    onSuccess: () => qc.invalidateQueries({ queryKey: KEY }),
  });
}

export function useTestKiteTelegram() {
  const qc = useQueryClient();
  return useMutation<KiteTelegramTarget, Error, string>({
    mutationFn: (id) => api.post<KiteTelegramTarget>(`${K}/${id}/test`),
    onSuccess: () => qc.invalidateQueries({ queryKey: KEY }),
  });
}
