/**
 * Data-lake status + folder picking.
 *
 * The lake normally lives on a removable drive, so "not available" is a routine state,
 * not a failure. The backend encodes that by answering 200 with `available: false` plus
 * human guidance, and this hook keeps polling — which means plugging the drive back in
 * heals the UI on its own, with no reload and no error toast.
 */
import { useCallback, useEffect, useRef, useState } from 'react';
import { api } from '../utils/api';

export interface LakeVolume {
  path: string;
  fstype: string;
  device: string;
  total_bytes: number;
  free_bytes: number;
  free_gib: number;
  total_gib: number;
  writable: boolean;
  removable: boolean;
  volume_uuid: string;
  label: string;
  lake_at: string;
  lake_id: string;
  lake_label: string;
}

export interface KnownRoot {
  lake_id: string;
  label?: string;
  last_path?: string;
  volume_uuid?: string;
  last_seen?: string;
}

export interface LakeStatus {
  available: boolean;
  root: string;
  lake_id: string;
  label: string;
  reason: string;
  guidance: string[];
  last_path: string;
  volume_uuid: string;
  volume_present_unmounted: boolean;
  free_gib: number;
  total_gib: number;
  candidates: LakeVolume[];
  known: KnownRoot[];
  has_credentials?: boolean;
  instrument_master_age_hours?: number | null;
}

export interface BrowseEntry {
  name: string;
  path: string;
  writable: boolean;
  has_lake: boolean;
  lake_label: string;
}

export interface BrowseResult {
  path: string;
  parent: string;
  entries: BrowseEntry[];
  writable: boolean;
  error: string;
  free_gib: number;
  has_lake: boolean;
  lake_label: string;
}

export interface LakeStats {
  interval: string;
  chunks_total: number;
  chunks_settled: number;
  chunks_remaining: number;
  chunks_by_status: Record<string, number>;
  pct_complete: number;
  candles: number;
  symbols: number;
  gib: number;
  instruments_known: number;
}

export interface LakeSummary extends LakeStatus {
  stats: Partial<LakeStats>;
  runs: Array<Record<string, unknown>>;
}

/** One of the three nested universes this lake downloads. */
export interface TierRow {
  tier: number;
  universe: string;
  instruments: number;
  /** Instruments no earlier tier already covered — what this tier actually pays for. */
  new_instruments: number;
  requests_standalone: number;
  requests_incremental: number;
  eta_incremental: string;
  est_gib_incremental: number;
  cumulative_requests: number;
  cumulative_eta: string;
  cumulative_gib: number;
  description: string;
}

export interface TierPlan {
  interval: string;
  frm: string;
  to: string;
  rate: number;
  tiers: TierRow[];
  total_instruments: number;
  total_requests: number;
  total_eta: string;
  total_gib: number;
  /** What summing the tiers naively would suggest — always larger than total_requests. */
  naive_requests: number;
  requests_saved_by_dedup: number;
}

/** One instrument stored in the lake. */
export interface LakeSymbol {
  instrument_token: number;
  tradingsymbol: string;
  exchange: string;
  segment: string;
  interval: string;
  rows: number;
  bytes: number;
  first_ts: string;
  last_ts: string;
}

export interface LakeSymbolPage {
  available: boolean;
  interval: string;
  total: number;
  symbols: LakeSymbol[];
  reason?: string;
  guidance?: string[];
}

export interface LakeBar {
  t: string;
  o: number;
  h: number;
  l: number;
  c: number;
  v: number;
}

export interface LakeBars {
  symbol: string;
  instrument_token: number;
  exchange: string;
  interval: string;
  rows_total: number;
  rows_returned: number;
  /** >1 when the range was thinned for display; the full span is still covered. */
  downsampled_every: number;
  bars: LakeBar[];
}

/** The api helper prepends only the host, so paths carry the full prefix. */
const D = '/api/v1/datalake';

const POLL_MS = 8000;

export function useDataLake(interval = 'minute') {
  const [summary, setSummary] = useState<LakeSummary | null>(null);
  const [loading, setLoading] = useState(true);
  /** Only set for genuine transport faults — never for an absent drive. */
  const [error, setError] = useState('');
  const alive = useRef(true);

  const refresh = useCallback(async () => {
    try {
      const data = await api.get<LakeSummary>(`${D}/summary?interval=${interval}`);
      if (!alive.current) return;
      setSummary(data);
      setError('');
    } catch (e) {
      if (!alive.current) return;
      // The backend being unreachable is a different problem from the drive being out,
      // and must not be dressed up as one.
      setError(e instanceof Error ? e.message : 'could not reach the backend');
    } finally {
      if (alive.current) setLoading(false);
    }
  }, [interval]);

  useEffect(() => {
    alive.current = true;
    void refresh();
    const timer = window.setInterval(() => void refresh(), POLL_MS);
    return () => {
      alive.current = false;
      window.clearInterval(timer);
    };
  }, [refresh]);

  const listVolumes = useCallback(
    () => api.get<{ volumes: LakeVolume[]; error: string }>(`${D}/volumes`),
    [],
  );

  const listSymbols = useCallback(
    (opts: { search?: string; limit?: number; offset?: number; sort?: string } = {}) => {
      const params = new URLSearchParams({ interval });
      if (opts.search) params.set('search', opts.search);
      params.set('limit', String(opts.limit ?? 200));
      params.set('offset', String(opts.offset ?? 0));
      params.set('sort', opts.sort ?? 'rows');
      return api.get<LakeSymbolPage>(`${D}/symbols?${params}`);
    },
    [interval],
  );

  const fetchBars = useCallback(
    (symbol: string, opts: { frm?: string; to?: string; limit?: number } = {}) => {
      const params = new URLSearchParams({ symbol, interval });
      if (opts.frm) params.set('frm', opts.frm);
      if (opts.to) params.set('to', opts.to);
      params.set('limit', String(opts.limit ?? 1500));
      return api.get<LakeBars>(`${D}/bars?${params}`);
    },
    [interval],
  );

  const tierPlan = useCallback(
    (frm: string, to: string, planInterval = interval, rate = 2.5) =>
      api.get<TierPlan>(
        `${D}/tiers?interval=${planInterval}&frm=${frm}&to=${to}&rate=${rate}`,
      ),
    [interval],
  );

  const browse = useCallback(
    (path?: string, showHidden = false) => {
      const params = new URLSearchParams();
      if (path) params.set('path', path);
      if (showHidden) params.set('show_hidden', 'true');
      const qs = params.toString();
      return api.get<BrowseResult>(`${D}/browse${qs ? `?${qs}` : ''}`);
    },
    [],
  );

  const setRoot = useCallback(
    async (path: string, label = '') => {
      const next = await api.post<LakeStatus>(`${D}/root`, { path, label, create: true });
      await refresh();
      return next;
    },
    [refresh],
  );

  const activateRoot = useCallback(
    async (lakeId: string) => {
      const next = await api.post<LakeStatus>(`${D}/root/activate`, { lake_id: lakeId });
      await refresh();
      return next;
    },
    [refresh],
  );

  const forgetRoot = useCallback(
    async (lakeId: string) => {
      const next = await api.delete<LakeStatus>(`${D}/root/${lakeId}`);
      await refresh();
      return next;
    },
    [refresh],
  );

  return {
    summary,
    loading,
    error,
    refresh,
    listVolumes,
    browse,
    setRoot,
    activateRoot,
    forgetRoot,
    tierPlan,
    listSymbols,
    fetchBars,
  };
}
