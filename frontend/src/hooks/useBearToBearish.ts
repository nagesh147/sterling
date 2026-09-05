import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { api } from '../utils/api';

const SNAPSHOT_KEY = ['bear-to-bearish-snapshot'];
const CONFIG_KEY = ['bear-to-bearish-config'];
const BASE = '/api/v1/bear-to-bearish';

export interface BearToBearishSignalRow {
  id: string;
  underlying: string;
  symbol: string;
  exchange: string;
  direction: 'short' | 'long';
  status: 'armed' | 'running' | 'weakening' | 'ended' | 'watching' | 'error';
  timestamp_ms: number;
  pcr_open: float;
  pcr_current: float;
  pcr_change_5m: float;
  lower_high_price: number;
  spot_price?: number;
  spot_sl?: number;
  spot_target?: number;
  option_premium?: number;
  entry_price: number;
  stop_loss: number;
  target_price: number;
  score: number;
  reason?: string | null;
  option_type?: 'PE' | 'CE';
  strike?: number | null;
  expiry?: string | null;
  lot_size?: number;
  quote_key?: string | null;
}

type float = number;

export interface BearToBearishSnapshotResponse {
  generated_ms: number;
  scanning: boolean;
  scanning_label: string;
  rows: BearToBearishSignalRow[];
  pcr_history: Record<string, { hhmm: string; pcr: number }[]>;
  config: Record<string, any>;
  next_scan_ms?: number;
  auto_scan?: boolean;
  market_open?: boolean;
  is_paper?: boolean;
  auto_execute?: boolean;
}

import { useReplayActive as useSimActive } from './useReplayStore';

export function useBearToBearishSnapshot(enabled = true, pollMs = 5000) {
  const isSimActive = useSimActive();
  return useQuery<BearToBearishSnapshotResponse>({
    queryKey: SNAPSHOT_KEY,
    queryFn: async () => {
      const res: any = await api.get(`${BASE}/snapshot`);
      return res.data ?? res;
    },
    enabled,
    refetchInterval: isSimActive ? 300 : (pollMs > 0 ? pollMs : false),
  });
}

export function useBearToBearishConfig() {
  return useQuery<Record<string, any>>({
    queryKey: CONFIG_KEY,
    queryFn: async () => {
      const res: any = await api.get(`${BASE}/config`);
      return res.data ?? res;
    },
  });
}

export function useUpdateBearToBearishConfig() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (patch: Record<string, any>) => {
      const res: any = await api.post(`${BASE}/config`, patch);
      return res.data ?? res;
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: CONFIG_KEY });
      qc.invalidateQueries({ queryKey: SNAPSHOT_KEY });
    },
  });
}

export function useBearToBearishScan() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async () => {
      const res: any = await api.post(`${BASE}/scan`);
      return res.data ?? res;
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: SNAPSHOT_KEY });
    },
  });
}

export function useExecuteBearToBearishOrder() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (signalId: string) => {
      const res: any = await api.post(`${BASE}/execute`, { signal_id: signalId });
      return res.data ?? res;
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: SNAPSHOT_KEY });
    },
  });
}
