import React, { useState, useRef } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { useTradingMode, useSetTradingMode } from '../hooks/useTradingMode';
import { clearSignalFeedState } from '../hooks/useSignalFeed';
import { api } from '../utils/api';
import { MODE_COLOR } from '../utils/fmt';

const MODE_DESC: Record<string, string> = {
  scalping:   'Fast · 1m–15m · 1×ATR stop',
  intraday:   'Day · 5m–1H · 1.5×ATR stop',
  swing:      'Swing · 1H–4H · 2×ATR stop',
  positional: 'Position · 4H–D · 3×ATR stop',
  all:        'All timeframes combined',
};

const MODES = ['scalping', 'intraday', 'swing', 'positional', 'all'];

const MAX_LOCK_MS = 10_000;

export function TradingModeSelector() {
  const { data: current, isLoading } = useTradingMode();
  const setMode = useSetTradingMode();
  const [toast, setToast] = useState('');
  const [isChanging, setIsChanging] = useState(false);
  const lockTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const qc = useQueryClient();

  const currentName = current?.name ?? '';
  const color = MODE_COLOR[currentName] ?? MODE_COLOR['swing'];

  const unlock = () => {
    if (lockTimer.current) clearTimeout(lockTimer.current);
    lockTimer.current = null;
    setIsChanging(false);
  };

  const handleChange = (e: React.ChangeEvent<HTMLSelectElement>) => {
    const name = e.target.value;
    // If already changing, skip (no external state dependency — just our own flag)
    if (isChanging) return;
    // Don't re-submit the same mode, but only once we have real data from server
    if (currentName && name === currentName) return;

    setIsChanging(true);
    // Safety: always unlock after MAX_LOCK_MS regardless of what happens
    lockTimer.current = setTimeout(unlock, MAX_LOCK_MS);

    setMode.mutate({ name }, {
      onSuccess: async (data) => {
        const display = data.config?.display ?? name;
        setToast(`⚡ Switched to ${display} — refreshing signals…`);
        qc.invalidateQueries({ queryKey: ['trading-mode'] });
        clearSignalFeedState();

        try {
          await api.post('/api/v1/directional/refresh-signals', {});
          qc.invalidateQueries({ queryKey: ['signals-all'] });
          qc.invalidateQueries({ queryKey: ['signal-alerts'] });
          setToast(`✅ ${display} mode active — signals updated`);
        } catch {
          setToast(`✅ ${display} mode saved (signals refresh in 30s)`);
        } finally {
          unlock();
          setTimeout(() => setToast(''), 3000);
        }
      },
      onError: (err) => {
        setToast(`Error: ${err.message}`);
        unlock();
        setTimeout(() => setToast(''), 3000);
      },
    });
  };

  const badgeLabel = isChanging ? '…' : isLoading ? '…' : (currentName || 'swing').toUpperCase();
  const displayColor = MODE_COLOR[currentName || 'swing'] ?? 'var(--text-dim)';

  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
      {/* current mode badge */}
      <span style={{
        display: 'inline-block', padding: '3px 9px', borderRadius: 4,
        fontSize: 10, fontWeight: 800, letterSpacing: 1,
        background: displayColor + '22', color: displayColor,
        border: `1px solid ${displayColor}55`,
        minWidth: 70, textAlign: 'center',
        transition: 'background 0.2s, color 0.2s',
      }}>
        {badgeLabel}
      </span>

      {/* dropdown — never fully disabled; cursor shows state visually */}
      <select
        style={{
          background: 'var(--bg)', color: 'var(--text-primary)',
          border: `1px solid ${displayColor}77`,
          borderRadius: 4, padding: '4px 8px', fontFamily: 'inherit',
          fontSize: 11, cursor: isChanging ? 'wait' : 'pointer',
          outline: 'none', minWidth: 110,
          opacity: isChanging ? 0.6 : 1,
          transition: 'opacity 0.15s',
        }}
        value={currentName || 'swing'}
        onChange={handleChange}
        title={MODE_DESC[currentName] ?? ''}
      >
        {MODES.map((m) => (
          <option key={m} value={m}>
            {m === 'all' ? 'All Modes' : m.charAt(0).toUpperCase() + m.slice(1)}
          </option>
        ))}
      </select>

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
