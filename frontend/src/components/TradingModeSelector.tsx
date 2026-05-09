import React, { useState } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { useTradingMode, useSetTradingMode } from '../hooks/useTradingMode';

const MODE_COLOR: Record<string, string> = {
  scalping: '#ff7f6e',
  intraday: '#f0c040',
  swing: '#44cc88',
  positional: '#aa88ff',
};

const MODES = ['scalping', 'intraday', 'swing', 'positional'];

function badgeStyle(name: string): React.CSSProperties {
  const color = MODE_COLOR[name] ?? 'var(--text-dim)';
  return {
    display: 'inline-block', padding: '2px 8px', borderRadius: 3,
    fontSize: 10, fontWeight: 700, letterSpacing: 1,
    background: `${color}22`, color, border: `1px solid ${color}55`,
  };
}

export function TradingModeSelector() {
  const { data: current } = useTradingMode();
  const setMode = useSetTradingMode();
  const [toast, setToast] = useState('');
  const qc = useQueryClient();

  const currentName = current?.name ?? 'swing';

  const handleChange = (e: React.ChangeEvent<HTMLSelectElement>) => {
    const name = e.target.value;
    if (name !== currentName) {
      setMode.mutate({ name }, {
        onSuccess: (data) => {
          setToast(`Switched to ${data.config?.display ?? name}`);
          setTimeout(() => setToast(''), 2500);
          qc.invalidateQueries({ queryKey: ['signals-all'] });
          qc.invalidateQueries({ queryKey: ['trading-mode'] });
        },
        onError: (err) => {
          setToast(`Error: ${err.message}`);
          setTimeout(() => setToast(''), 3000);
        },
      });
    }
  };

  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
      <span style={badgeStyle(currentName)}>{currentName.toUpperCase()}</span>
      <select
        style={{
          background: 'var(--bg)', color: 'var(--text-primary)', border: '1px solid var(--border)',
          borderRadius: 3, padding: '4px 8px', fontFamily: 'inherit',
          fontSize: 11, cursor: 'pointer',
        }}
        value={currentName}
        onChange={handleChange}
        disabled={setMode.isPending}
      >
        {MODES.map((m) => (
          <option key={m} value={m}>{m.charAt(0).toUpperCase() + m.slice(1)}</option>
        ))}
      </select>

      {toast && (
        <div style={{
          position: 'fixed', bottom: 24, right: 24,
          background: toast.startsWith('Error') ? '#2a1a1a' : '#1a2a1a',
          color: toast.startsWith('Error') ? 'var(--danger)' : 'var(--accent)',
          border: `1px solid ${toast.startsWith('Error') ? 'var(--danger)' : 'var(--accent)'}`,
          borderRadius: 4, padding: '8px 16px', fontSize: 12, zIndex: 2000,
        }}>
          {toast}
        </div>
      )}
    </div>
  );
}
