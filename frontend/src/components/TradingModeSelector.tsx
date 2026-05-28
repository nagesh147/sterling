import React, { useRef, useState } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { useTradingMode, useSetTradingMode } from '../hooks/useTradingMode';
import { clearSignalFeed, clearSignalFeedState } from '../hooks/useSignalFeed';
import { api } from '../utils/api';
import { MODE_COLOR } from '../utils/colors';
import { tint } from '../styles/terminalUI';

const MODE_LABEL: Record<string, string> = {
  scalping:   'SCALPING',
  intraday:   'INTRADAY',
  swing:      'SWING',
  positional: 'POSITIONAL',
  all:        'ALL',
};

const MODES = ['all', 'scalping', 'intraday', 'swing', 'positional'];

const MAX_LOCK_MS = 10_000;

export function TradingModeSelector() {
  const { data: current, isLoading } = useTradingMode();
  const setMode   = useSetTradingMode();
  const [toast, setToast]       = useState('');
  const [isChanging, setIsChanging] = useState(false);
  const [pendingMode, setPendingMode] = useState<string | null>(null);
  const lockTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const qc = useQueryClient();

  const currentName = current?.name ?? '';

  const unlock = () => {
    if (lockTimer.current) clearTimeout(lockTimer.current);
    lockTimer.current = null;
    setIsChanging(false);
    setPendingMode(null);
  };

  const handleSelect = (name: string) => {
    if (isChanging) return;
    if (currentName && name === currentName) return;

    setIsChanging(true);
    setPendingMode(name);
    lockTimer.current = setTimeout(unlock, MAX_LOCK_MS);

    setMode.mutate({ name }, {
      onSuccess: async (data) => {
        const display = data.config?.display ?? name;
        setToast(`⚡ ${display} mode — refreshing…`);
        qc.invalidateQueries({ queryKey: ['trading-mode'] });
        // Wipe the entire feed + state tracker. Old entries are tagged with
        // the previous mode and carry SC/IN/SW signal IDs from the old
        // backend cache — keeping them in view causes the "INTRADAY mode but
        // BTCFUT-SC-XXX" mismatch we just fixed on the backend.
        clearSignalFeed();
        clearSignalFeedState();
        try {
          await api.post('/api/v1/directional/refresh-signals', {});
          qc.invalidateQueries({ queryKey: ['signals-all'] });
          qc.invalidateQueries({ queryKey: ['signal-alerts'] });
          setToast(`✅ ${display} active`);
        } catch {
          setToast(`✅ ${display} saved`);
        } finally {
          unlock();
          setTimeout(() => setToast(''), 2500);
        }
      },
      onError: (err) => {
        setToast(`❌ ${err.message}`);
        unlock();
        setTimeout(() => setToast(''), 3000);
      },
    });
  };

  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 4, flexWrap: 'wrap' }}>
      {MODES.map(m => {
        const active   = m === currentName;
        const loading  = isChanging && pendingMode === m;
        const color    = MODE_COLOR[m] ?? 'var(--text-dim)';

        return (
          <button
            key={m}
            onClick={() => handleSelect(m)}
            disabled={isChanging}
            title={m === 'all' ? 'All timeframes combined' : undefined}
            style={{
              padding: '3px 10px',
              borderRadius: 20,
              fontFamily: 'inherit',
              fontSize: 10,
              fontWeight: 800,
              letterSpacing: 0.8,
              cursor: isChanging ? (loading ? 'wait' : 'default') : 'pointer',
              border: `1px solid ${active ? color : 'var(--border)'}`,
              background: active ? tint(color, 13) : 'transparent',
              color: active ? color : isLoading ? 'var(--text-faint)' : 'var(--text-dim)',
              transition: 'all 0.15s',
              opacity: isChanging && !active && !loading ? 0.4 : 1,
              outline: 'none',
            }}
          >
            {loading ? '…' : MODE_LABEL[m]}
          </button>
        );
      })}

      {/* toast */}
      {toast && (
        <div style={{
          position: 'fixed', bottom: 24, right: 24,
          background: toast.startsWith('❌') ? tint('var(--danger)', 12) : tint('var(--accent)', 12),
          color: toast.startsWith('❌') ? 'var(--danger)' : 'var(--accent)',
          border: `1px solid ${toast.startsWith('❌') ? tint('var(--danger)', 40) : tint('var(--accent)', 40)}`,
          borderRadius: 5, padding: '10px 18px', fontSize: 12, zIndex: 2000,
        }}>
          {toast}
        </div>
      )}
    </div>
  );
}
