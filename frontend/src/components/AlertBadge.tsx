import React from 'react';
import { useAlerts } from '../hooks/useAlerts';

export function AlertBadge() {
  const { data } = useAlerts();
  if (!data || data.triggered_count === 0) return null;

  return (
    <div style={{
      display: 'inline-flex', alignItems: 'center', gap: 5,
      background: '#cc444422', border: '1px solid #cc444444',
      borderRadius: 4, padding: '4px 10px', fontSize: 11, cursor: 'default',
    }}
    title="Click Alerts tab to view">
      <span style={{ color: '#cc4444', fontWeight: 700 }}>
        🔔 {data.triggered_count}
      </span>
      <span style={{ color: '#cc6666' }}>ALERT{data.triggered_count > 1 ? 'S' : ''}</span>
    </div>
  );
}
