import React from 'react';
import { useSignalStream } from '../hooks/useSignalStream';
import { c as t } from '../styles/terminalUI';

const DOT: Record<string, string> = {
  connecting: t.amber,
  connected: t.green,
  disconnected: t.dim,
};

const styles: React.CSSProperties = {
  display: 'inline-flex', alignItems: 'center', gap: 6,
  background: t.surface, border: `1px solid ${t.border}`,
  borderRadius: 4, padding: '4px 10px', fontSize: 11,
};

interface Props { underlying: string }

export function StreamBadge({ underlying }: Props) {
  const { data, status } = useSignalStream(underlying, 30);

  const dotColor = DOT[status];
  const label = status === 'connected' ? 'LIVE'
    : status === 'connecting' ? (data ? 'RECONNECTING' : 'CONNECTING')
    : 'STREAM OFF';

  return (
    <div style={styles}>
      <span style={{
        width: 7, height: 7, borderRadius: '50%',
        background: dotColor,
        display: 'inline-block',
      }} />
      <span style={{ color: status === 'connected' ? t.dim : status === 'connecting' ? t.dim : t.dim }}>
        {label}
      </span>
      {data && !data.error && status === 'connected' && (
        <>
          <span style={{ color: t.border, margin: '0 2px' }}>|</span>
          <span style={{ color: data.signal_trend === 1 ? t.green : data.signal_trend === -1 ? t.red : t.dim }}>
            {data.signal_trend === 1 ? '▲' : data.signal_trend === -1 ? '▼' : '~'}
          </span>
          {data.green_arrow && <span style={{ color: t.green, fontWeight: 700 }}>↑ ARROW</span>}
          {data.red_arrow && <span style={{ color: t.red, fontWeight: 700 }}>↓ ARROW</span>}
          <span style={{ color: t.border, margin: '0 2px' }}>|</span>
          <span style={{ color: t.dim }}>${(data.spot_price ?? 0).toLocaleString('en-US', { maximumFractionDigits: 0 })}</span>
        </>
      )}
    </div>
  );
}
