import React, { useState } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { useTradingMode, useSetTradingMode } from '../hooks/useTradingMode';
import { api } from '../utils/api';

const MODE_COLOR: Record<string, string> = {
  scalping:   '#ff7f6e',
  intraday:   '#f0c040',
  swing:      '#44cc88',
  positional: '#aa88ff',
};

const MODE_DESC: Record<string, string> = {
  scalping:   'Fast · 1m–15m · 1×ATR stop',
  intraday:   'Day · 5m–1H · 1.5×ATR stop',
  swing:      'Swing · 1H–4H · 2×ATR stop',
  positional: 'Position · 4H–D · 3×ATR stop',
};

const MODES = ['scalping', 'intraday', 'swing', 'positional'];

export function TradingModeSelector() {
  const { data: current, isLoading } = useTradingMode();
  const setMode = useSetTradingMode();
  const [toast, setToast] = useState('');
  const [refreshing, setRefreshing] = useState(false);
  const qc = useQueryClient();

  const currentName = current?.name ?? 'swing';
  const color = MODE_COLOR[currentName] ?? 'var(--text-dim)';

  const handleChange = (e: React.ChangeEvent<HTMLSelectElement>) => {
    const name = e.target.value;
    if (name === currentName || setMode.isPending) return;

    setMode.mutate({ name }, {
      onSuccess: async (data) => {
        const display = data.config?.display ?? name;
        setToast(`⚡ Switched to ${display} — refreshing signals…`);
        qc.invalidateQueries({ queryKey: ['trading-mode'] });

        // Immediately recompute signals with new mode settings
        setRefreshing(true);
        try {
          await api.post('/api/v1/directional/refresh-signals', {});
          qc.invalidateQueries({ queryKey: ['signals-all'] });
          qc.invalidateQueries({ queryKey: ['signal-alerts'] });
          setToast(`✅ ${display} mode active — signals updated`);
        } catch {
          setToast(`✅ ${display} mode saved (signals refresh in 30s)`);
        } finally {
          setRefreshing(false);
          setTimeout(() => setToast(''), 3000);
        }
      },
      onError: (err) => {
        setToast(`Error: ${err.message}`);
        setTimeout(() => setToast(''), 3000);
      },
    });
  };

  const isPending = setMode.isPending || refreshing || isLoading;

  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
      {/* current mode badge */}
      <span style={{
        display: 'inline-block', padding: '3px 9px', borderRadius: 4,
        fontSize: 10, fontWeight: 800, letterSpacing: 1,
        background: color + '22', color, border: `1px solid ${color}55`,
        minWidth: 70, textAlign: 'center',
      }}>
        {isPending ? '…' : currentName.toUpperCase()}
      </span>

      {/* dropdown */}
      <select
        style={{
          background: 'var(--bg)', color: 'var(--text-primary)',
          border: `1px solid ${color}77`,
          borderRadius: 4, padding: '4px 8px', fontFamily: 'inherit',
          fontSize: 11, cursor: isPending ? 'wait' : 'pointer',
          outline: 'none', minWidth: 100,
        }}
        value={currentName}
        onChange={handleChange}
        disabled={isPending}
        title={MODE_DESC[currentName] ?? ''}
      >
        {MODES.map((m) => (
          <option key={m} value={m}>
            {m.charAt(0).toUpperCase() + m.slice(1)}
          </option>
        ))}
      </select>

      {/* mode description */}
      <span style={{ fontSize: 9, color: 'var(--text-faint)', display: 'none' }}>
        {MODE_DESC[currentName]}
      </span>

      {/* toast */}
      {toast && (
        <div style={{
          position: 'fixed', bottom: 24, right: 24,
          background: toast.startsWith('Error') ? '#2a1a1a' : '#111f11',
          color: toast.startsWith('Error') ? 'var(--danger)' : 'var(--accent)',
          border: `1px solid ${toast.startsWith('Error') ? '#cc444466' : '#44cc8866'}`,
          borderRadius: 5, padding: '10px 18px', fontSize: 12, zIndex: 2000,
          boxShadow: '0 4px 20px #00000088',
        }}>
          {toast}
        </div>
      )}
    </div>
  );
}
