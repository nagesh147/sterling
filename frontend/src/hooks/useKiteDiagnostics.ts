import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { api } from '../utils/api';
import type {
  KiteDiagnosticSuiteResult,
  KiteDiagnosticsSummary,
} from '../types/kiteDiagnostics';

const KITE_DIAG = '/api/v1/kite/diagnostics';

export function useKiteDiagnosticsSummary() {
  return useQuery<KiteDiagnosticsSummary>({
    queryKey: ['kite-diagnostics-summary'],
    queryFn: () => api.get<KiteDiagnosticsSummary>(`${KITE_DIAG}/summary`),
    refetchInterval: 15_000,
  });
}

export function useRunKiteDiagnostics() {
  const qc = useQueryClient();
  return useMutation<
    KiteDiagnosticSuiteResult,
    Error,
    { category_id?: string } | void
  >({
    mutationFn: (params) => {
      const url = params?.category_id
        ? `${KITE_DIAG}/run?category_id=${encodeURIComponent(params.category_id)}`
        : `${KITE_DIAG}/run`;
      return api.post<KiteDiagnosticSuiteResult>(url, {});
    },
    onSuccess: (data) => {
      qc.setQueryData(['kite-diagnostics-latest'], data);
      qc.invalidateQueries({ queryKey: ['kite-diagnostics-summary'] });
      qc.invalidateQueries({ queryKey: ['kite-status'] });
    },
  });
}
