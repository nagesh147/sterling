import React from 'react';
import { useSignalStream } from '../hooks/useSignalStream';

const DOT: Record<string, string> = {
  connecting: '#f0a500',
  connected: '#44cc88',
  disconnected: '#555',
};

const styles: React.CSSProperties = {
  display: 'inline-flex', alignItems: 'center', gap: 6,
  background: '#141414', border: '1px solid #222',
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
        boxShadow: status === 'connected' ? `0 0 6px ${dotColor}` : 'none',
        display: 'inline-block',
      }} />
      <span style={{ color: status === 'connected' ? '#666' : status === 'connecting' ? '#888' : '#444' }}>
        {label}
      </span>
      {data && !data.error && status === 'connected' && (
        <>
          <span style={{ color: '#333', margin: '0 2px' }}>|</span>
          <span style={{ color: data.signal_trend === 1 ? '#44cc88' : data.signal_trend === -1 ? '#cc4444' : '#888' }}>
            {data.signal_trend === 1 ? '▲' : data.signal_trend === -1 ? '▼' : '~'}
          </span>
          {data.green_arrow && <span style={{ color: '#44cc88', fontWeight: 700 }}>↑ ARROW</span>}
          {data.red_arrow && <span style={{ color: '#cc4444', fontWeight: 700 }}>↓ ARROW</span>}
          <span style={{ color: '#333', margin: '0 2px' }}>|</span>
          <span style={{ color: '#888' }}>${(data.spot_price ?? 0).toLocaleString('en-US', { maximumFractionDigits: 0 })}</span>
        </>
      )}
    </div>
  );
}
