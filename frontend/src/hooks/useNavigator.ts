import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { api } from '../utils/api';
import { notifyOrder } from '../store/useKiteNotifications';
import type {
  CalibrationReportResponse,
  NavigatorCalibrationResponse, NavigatorConfigModel, NavigatorConfigResponse,
  NavigatorSeriesResponse, NavigatorSignalsPage, NavigatorStatusResponse,
} from '../types/navigator';

const N = '/api/v1/kite/navigator';

export function useNavigatorConfig() {
  return useQuery<NavigatorConfigResponse>({
    queryKey: ['navigator-config'],
    queryFn: () => api.get<NavigatorConfigResponse>(`${N}/config`),
    staleTime: 30_000,
  });
}

export function useSetNavigatorConfig() {
  const qc = useQueryClient();
  return useMutation<NavigatorConfigResponse, Error, { config: NavigatorConfigModel; expected_revision: number }>({
    mutationFn: (body) => api.put<NavigatorConfigResponse>(`${N}/config`, body),
    onSuccess: (data) => {
      qc.setQueryData(['navigator-config'], data);
      notifyOrder({ kind: 'info', title: 'Navigator settings saved', message: `Revision ${data.record.revision}.` });
    },
  });
}

export function useValidateNavigatorConfig() {
  return useMutation<{ valid: boolean }, Error, Record<string, unknown>>({
    mutationFn: (body) => api.post<{ valid: boolean }>(`${N}/config/validate`, body),
  });
}

export function useResetNavigatorConfig() {
  const qc = useQueryClient();
  return useMutation<NavigatorConfigResponse, Error, void>({
    mutationFn: () => api.post<NavigatorConfigResponse>(`${N}/config/reset`),
    onSuccess: (data) => {
      qc.setQueryData(['navigator-config'], data);
      notifyOrder({ kind: 'info', title: 'Navigator reset', message: 'Restored to disabled defaults.' });
    },
  });
}

export function useNavigatorStatus(enabled: boolean) {
  return useQuery<NavigatorStatusResponse>({
    queryKey: ['navigator-status'],
    queryFn: () => api.get<NavigatorStatusResponse>(`${N}/status`),
    refetchInterval: enabled ? 15_000 : false,
    enabled,
  });
}

export function useNavigatorSnapshot(underlying: string | null) {
  return useQuery<Record<string, unknown>>({
    queryKey: ['navigator-snapshot', underlying],
    queryFn: () => api.get<Record<string, unknown>>(`${N}/snapshot/${encodeURIComponent(underlying as string)}`),
    enabled: !!underlying,
    retry: false,
    refetchInterval: underlying ? 15_000 : false,
  });
}

export function useNavigatorSignals(underlying?: string) {
  const qs = underlying ? `?underlying=${encodeURIComponent(underlying)}` : '';
  return useQuery<NavigatorSignalsPage>({
    queryKey: ['navigator-signals', underlying ?? null],
    queryFn: () => api.get<NavigatorSignalsPage>(`${N}/signals${qs}`),
    staleTime: 15_000,
  });
}

export function useNavigatorSeries(underlying: string | null) {
  return useQuery<NavigatorSeriesResponse>({
    queryKey: ['navigator-series', underlying],
    queryFn: () => api.get<NavigatorSeriesResponse>(`${N}/series/${encodeURIComponent(underlying as string)}`),
    enabled: !!underlying,
  });
}

export function useNavigatorCalibration() {
  return useQuery<NavigatorCalibrationResponse>({
    queryKey: ['navigator-calibration'],
    queryFn: () => api.get<NavigatorCalibrationResponse>(`${N}/calibration`),
    staleTime: 60_000,
  });
}

/** Score every decision Navigator has made against what the market did next.
 *  Read-and-measure only — generating a report never promotes anything. */
export function useGenerateCalibrationReport() {
  const qc = useQueryClient();
  return useMutation<CalibrationReportResponse, Error, void>({
    mutationFn: () => api.post<CalibrationReportResponse>(`${N}/calibration/report`),
    onSuccess: (data) => {
      qc.invalidateQueries({ queryKey: ['navigator-calibration'] });
      notifyOrder({
        kind: 'info',
        title: data.criteria.eligible ? 'Calibration report ready to review' : 'Calibration report generated',
        message: data.criteria.eligible
          ? 'Every criterion passes — you can promote when you\'ve reviewed it.'
          : `${data.criteria.criteria.filter((c) => !c.passed).length} criteria still outstanding.`,
      });
    },
  });
}

/** Explicitly mark calibration ready against a reviewed report. The server
 *  re-checks every criterion and refuses (409) if any fails. */
export function usePromoteCalibration() {
  const qc = useQueryClient();
  return useMutation<NavigatorConfigResponse, Error, { report_id: string; expected_revision: number }>({
    mutationFn: (body) => api.post<NavigatorConfigResponse>(`${N}/calibration/promote`, body),
    onSuccess: (data) => {
      qc.setQueryData(['navigator-config'], data);
      qc.invalidateQueries({ queryKey: ['navigator-calibration'] });
      notifyOrder({
        kind: 'info', title: 'Calibration promoted',
        message: 'Gate mode is now available to select. Nothing was switched on for you.',
      });
    },
  });
}

/** Revoke a promotion — back to not-ready, and off gate mode if selected. */
export function useDemoteCalibration() {
  const qc = useQueryClient();
  return useMutation<NavigatorConfigResponse, Error, { expected_revision: number }>({
    mutationFn: (body) => api.post<NavigatorConfigResponse>(`${N}/calibration/demote`, body),
    onSuccess: (data) => {
      qc.setQueryData(['navigator-config'], data);
      qc.invalidateQueries({ queryKey: ['navigator-calibration'] });
      notifyOrder({
        kind: 'info', title: 'Calibration revoked',
        message: 'Back to not-ready. Gate mode is locked again.',
      });
    },
  });
}
