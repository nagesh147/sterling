import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';

export type StatArbPairConfig = {
  name: string;
  asset_x: string;
  asset_y: string;
  asset_z?: string;
  hedge_ratio_y: number;
  hedge_ratio_z: number;
  enabled: boolean;
};

export type StatArbConfig = {
  enabled: boolean;
  auto_trade: boolean;
  timeframe: string;
  lookback_bars: number;
  entry_z_score: number;
  exit_z_score: number;
  stop_loss_z_score: number;
  max_position_usd: number;
  pairs: StatArbPairConfig[];
};

export type StatArbSignal = {
  pair_name: string;
  timestamp_ms: number;
  asset_x: string;
  asset_y: string;
  asset_z: string | null;
  current_z: number;
  current_spread: number;
  mean_spread: number;
  std_dev: number;
  state: 'armed' | 'active_long' | 'active_short' | 'neutral';
  action: 'ENTRY_LONG' | 'ENTRY_SHORT' | 'EXIT' | 'NONE';
  suggested_size_x: number;
  suggested_size_y: number;
  suggested_size_z: number;
};

export type StatArbScanResponse = {
  signals: StatArbSignal[];
  count: number;
  armed_count: number;
  timestamp_ms: number;
};

const fetchConfig = async (): Promise<{ config: StatArbConfig }> => {
  const r = await fetch('/api/v1/statarb/config');
  if (!r.ok) throw new Error('Failed to fetch statarb config');
  return r.json();
};

const setConfig = async (config: StatArbConfig): Promise<{ config: StatArbConfig }> => {
  const r = await fetch('/api/v1/statarb/config', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(config),
  });
  if (!r.ok) throw new Error('Failed to set statarb config');
  return r.json();
};

const fetchScan = async (): Promise<StatArbScanResponse> => {
  const r = await fetch('/api/v1/statarb/scan');
  if (!r.ok) throw new Error('Failed to fetch statarb scan');
  return r.json();
};

export function useStatArbConfig() {
  return useQuery({ queryKey: ['statarb_config'], queryFn: fetchConfig });
}

export function useSetStatArbConfig() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: setConfig,
    onSuccess: (data) => {
      qc.setQueryData(['statarb_config'], data);
    },
  });
}

export function useStatArbScan() {
  return useQuery({
    queryKey: ['statarb_scan'],
    queryFn: fetchScan,
    refetchInterval: 10000,
  });
}
