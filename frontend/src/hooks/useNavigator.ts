import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { api } from '../utils/api';
import { notifyOrder } from '../store/useKiteNotifications';
import type {
  CalibrationReportResponse,
  NavigatorCalibrationResponse, NavigatorConfigModel, NavigatorConfigResponse,
  NavigatorActivityResponse, NavigatorChartResponse, NavigatorScanResponse, NavigatorSeriesResponse,
  NavigatorSignalsPage, NavigatorStatusResponse,
} from '../types/navigator';
import type { EngineSignalRow, SignalsResponse } from '../types/kiteEngine';

const N = '/api/v1/kite/navigator';

function signalRowKey(row: EngineSignalRow): string {
  const leg = row.legs?.[0]?.option_symbol ?? '';
  return `${row.source ?? 'spot'}:${row.underlying}:${row.token}:${row.direction}:${row.option_type}:${row.timestamp_ms}:${leg}`;
}

function mergeSignalRows(base: EngineSignalRow[], navigator: EngineSignalRow[]): EngineSignalRow[] {
  const merged = new Map<string, EngineSignalRow>();
  [...base, ...navigator].forEach((row) => {
    const key = signalRowKey(row);
    const existing = merged.get(key);
    if (!existing) {
      merged.set(key, row);
      return;
    }
    const rank = Number(row.is_fresh) * 2 + Number(row.is_active);
    const existingRank = Number(existing.is_fresh) * 2 + Number(existing.is_active);
    if (rank >= existingRank) merged.set(key, row);
  });
  return Array.from(merged.values()).sort((a, b) =>
    Number(Boolean(b.is_fresh || b.is_active)) - Number(Boolean(a.is_fresh || a.is_active))
    || b.timestamp_ms - a.timestamp_ms,
  );
}

function mergeNavigatorScanIntoBoard(prev: SignalsResponse | undefined, data: NavigatorScanResponse): SignalsResponse | undefined {
  if (!prev) return prev;
  return {
    ...prev,
    generated_ms: Math.max(prev.generated_ms ?? 0, data.generated_ms ?? 0),
    scanning: data.scanning || prev.scanning,
    scanning_label: data.scanning_label || prev.scanning_label,
    next_scan_ms: data.next_scan_ms || prev.next_scan_ms,
    auto_scan: data.auto_scan || prev.auto_scan,
    rows: mergeSignalRows(prev.rows ?? [], data.rows ?? []),
  };
}

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

export function useNavigatorActivity(enabled = true) {
  return useQuery<NavigatorActivityResponse>({
    queryKey: ['navigator-activity'],
    queryFn: () => api.get<NavigatorActivityResponse>(`${N}/activity`),
    refetchInterval: enabled ? 5000 : false,
    enabled,
  });
}

export function useRunNavigatorScan() {
  const qc = useQueryClient();
  return useMutation<NavigatorScanResponse, Error, void>({
    mutationFn: () => api.post<NavigatorScanResponse>(`${N}/scan`),
    onSuccess: (data) => {
      qc.setQueryData<SignalsResponse>(['kite-engine-signals'], (prev) => mergeNavigatorScanIntoBoard(prev, data));
      qc.invalidateQueries({ queryKey: ['kite-engine-signals'] });
      qc.invalidateQueries({ queryKey: ['navigator-status'] });
      qc.invalidateQueries({ queryKey: ['navigator-activity'] });
      qc.invalidateQueries({ queryKey: ['navigator-signals'] });
      notifyOrder({ kind: 'info', title: 'Navigator scan complete', message: 'Independent Navigator scan finished.' });
    },
  });
}

export function useCancelNavigatorScan() {
  const qc = useQueryClient();
  return useMutation<NavigatorScanResponse, Error, void>({
    mutationFn: () => api.post<NavigatorScanResponse>(`${N}/scan/cancel`),
    onSuccess: (data) => {
      qc.setQueryData<SignalsResponse>(['kite-engine-signals'], (prev) => mergeNavigatorScanIntoBoard(prev, data));
      qc.invalidateQueries({ queryKey: ['kite-engine-signals'] });
      qc.invalidateQueries({ queryKey: ['navigator-status'] });
      qc.invalidateQueries({ queryKey: ['navigator-activity'] });
      notifyOrder({ kind: 'info', title: 'Navigator scan cancelled', message: 'Navigator cancellation requested.' });
    },
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

/** Per-bar Navigator evidence for the chart overlay.
 *
 * Only fetched while a Navigator indicator is switched on — the request costs
 * a Kite historical call, so an untoggled overlay must cost nothing. */
export function useNavigatorChart(underlying: string | null, enabled: boolean) {
  return useQuery<NavigatorChartResponse>({
    queryKey: ['navigator-chart', underlying],
    queryFn: () => api.get<NavigatorChartResponse>(`${N}/chart/${encodeURIComponent(underlying as string)}`),
    enabled: enabled && !!underlying,
    retry: false,
    staleTime: 60_000,
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
