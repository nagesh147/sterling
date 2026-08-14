import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { api } from '../utils/api';
import type {
  TrueDataCredential,
  TrueDataCredentialCreate,
  TrueDataCredentialUpdate,
  TrueDataStatus,
} from '../types/truedata';

const TD = '/api/v1/truedata';

export function useTrueDataCredentials() {
  return useQuery<TrueDataCredential[]>({
    queryKey: ['truedata-credentials'],
    queryFn: () => api.get<TrueDataCredential[]>(`${TD}/credentials`),
    staleTime: 15_000,
  });
}

export function useAddTrueDataCredential() {
  const qc = useQueryClient();
  return useMutation<TrueDataCredential, Error, TrueDataCredentialCreate>({
    mutationFn: (body) => api.post<TrueDataCredential>(`${TD}/credentials`, body),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['truedata-credentials'] });
      qc.invalidateQueries({ queryKey: ['truedata-status'] });
    },
  });
}

export function useUpdateTrueDataCredential() {
  const qc = useQueryClient();
  return useMutation<
    TrueDataCredential,
    Error,
    { id: string } & TrueDataCredentialUpdate
  >({
    mutationFn: ({ id, ...body }) => api.put<TrueDataCredential>(`${TD}/credentials/${id}`, body),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['truedata-credentials'] });
      qc.invalidateQueries({ queryKey: ['truedata-status'] });
    },
  });
}

export function useDeleteTrueDataCredential() {
  const qc = useQueryClient();
  return useMutation<void, Error, string>({
    mutationFn: (id) => api.delete<void>(`${TD}/credentials/${id}`),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['truedata-credentials'] });
      qc.invalidateQueries({ queryKey: ['truedata-status'] });
    },
  });
}

export function useTrueDataStatus() {
  return useQuery<TrueDataStatus>({
    queryKey: ['truedata-status'],
    queryFn: () => api.get<TrueDataStatus>(`${TD}/status`),
    refetchInterval: 30_000,
  });
}
