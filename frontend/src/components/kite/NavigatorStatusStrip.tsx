import React from 'react';
import { DIM, MUTED, TEXT, BORDER } from './kiteSettingsPrimitives';
import { Icons } from '../../styles/kiteUI';
import { useNavigatorStatus } from '../../hooks/useNavigator';
import type { NavigatorHealth } from '../../types/navigator';

const HEALTH_COLOR: Record<NavigatorHealth, string> = {
  DISABLED: '#9b9b9b',
  STARTING: '#4184f3',
  WARMING_UP: '#f5a623',
  HEALTHY: '#4caf50',
  DEGRADED: '#f5a623',
  STALE: '#df514c',
  ERROR: '#df514c',
};

const HEALTH_LABEL: Record<NavigatorHealth, string> = {
  DISABLED: 'Navigator off',
  STARTING: 'Starting…',
  WARMING_UP: 'Warming up',
  HEALTHY: 'Healthy',
  DEGRADED: 'Degraded',
  STALE: 'Stale data',
  ERROR: 'Error',
};

/** Compact health indicator — surfaces "no data" vs "no signal" at a glance. */
export function NavigatorStatusStrip({ enabled }: { enabled: boolean }) {
  const { data } = useNavigatorStatus(enabled);
  if (!enabled) return null;
  if (!data) {
    return <div style={{ fontSize: 10.5, color: DIM }}>Navigator: loading status…</div>;
  }

  const color = HEALTH_COLOR[data.health];
  const label = HEALTH_LABEL[data.health];
  const degraded = data.components.filter((c) => c.quality !== 'ok');

  return (
    <div
      role="status"
      title={degraded.length ? `Degraded/unavailable: ${degraded.map((c) => c.name).join(', ')}` : undefined}
      style={{
        display: 'inline-flex', alignItems: 'center', gap: 7, padding: '4px 9px', borderRadius: 6,
        border: `1px solid ${BORDER}`, background: '#fff', fontSize: 10.5, fontWeight: 700, color: TEXT,
      }}
    >
      <span aria-hidden style={{ width: 7, height: 7, borderRadius: '50%', background: color, flexShrink: 0 }} />
      <span>Navigator: {label}</span>
      {data.health === 'STALE' || data.health === 'ERROR' ? <Icons.Warning /> : null}
      {data.calibration_readiness !== 'ready' && data.operating_mode === 'gate' && (
        <span style={{ color: MUTED, fontWeight: 500 }}>(gate locked)</span>
      )}
    </div>
  );
}

export default NavigatorStatusStrip;
