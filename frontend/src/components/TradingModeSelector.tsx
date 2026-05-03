import React, { useState } from 'react';
import { useTradingMode, useSetTradingMode } from '../hooks/useTradingMode';

const MODE_COLOR: Record<string, string> = {
  scalping: '#ff7f6e',
  intraday: '#f0c040',
  swing: '#44cc88',
  positional: '#aa88ff',
};

const MODES = ['scalping', 'intraday', 'swing', 'positional'];

function badgeStyle(name: string): React.CSSProperties {
  const color = MODE_COLOR[name] ?? '#555';
  return {
    display: 'inline-block', padding: '2px 8px', borderRadius: 3,
    fontSize: 10, fontWeight: 700, letterSpacing: 1,
    background: `${color}22`, color, border: `1px solid ${color}55`,
  };
}

export function TradingModeSelector() {
  const { data: current } = useTradingMode();
  const setMode = useSetTradingMode();
  const [pending, setPending] = useState<string | null>(null);
  const [toast, setToast] = useState('');

  const currentName = current?.name ?? 'swing';

  const handleChange = (e: React.ChangeEvent<HTMLSelectElement>) => {
    const name = e.target.value;
    if (name !== currentName) setPending(name);
  };

  const confirm = () => {
    if (!pending) return;
    setMode.mutate(
      { name: pending },
      {
        onSuccess: (data) => {
          setToast(`Switched to ${data.config?.display ?? pending} mode`);
          setTimeout(() => setToast(''), 3000);
          setPending(null);
        },
        onError: (err) => {
          setToast(`Error: ${err.message}`);
          setTimeout(() => setToast(''), 4000);
          setPending(null);
        },
      },
    );
  };

  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
      <span style={badgeStyle(currentName)}>{currentName.toUpperCase()}</span>
      <select
        style={{
          background: '#111', color: '#ccc', border: '1px solid #333',
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

      {/* Confirmation — renders as soon as pending is set, no query deps */}
      {pending && (
        <div
          style={{
            position: 'fixed', inset: 0, background: '#000000aa',
            display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 1000,
          }}
          onClick={() => setPending(null)}
        >
          <div
            style={{
              background: '#141414', border: '1px solid #333', borderRadius: 6,
              padding: 24, minWidth: 300,
            }}
            onClick={(e) => e.stopPropagation()}
          >
            <div style={{ color: '#e0e0e0', fontWeight: 700, fontSize: 14, marginBottom: 8 }}>
              Switch to {pending.charAt(0).toUpperCase() + pending.slice(1)} mode?
            </div>
            <div style={{ color: '#555', fontSize: 11, marginBottom: 16 }}>
              {currentName.toUpperCase()} → {pending.toUpperCase()}
              {current?.config && (
                <div style={{ marginTop: 10, display: 'flex', flexDirection: 'column', gap: 4 }}>
                  {[
                    ['Current DTE', `${current.config.dte_min}–${current.config.dte_max}d`],
                    ['Current position %', `${(current.config.position_pct * 100).toFixed(1)}%`],
                  ].map(([k, v]) => (
                    <div key={k} style={{ display: 'flex', justifyContent: 'space-between' }}>
                      <span style={{ color: '#444' }}>{k}</span>
                      <span style={{ color: '#888' }}>{v}</span>
                    </div>
                  ))}
                </div>
              )}
            </div>
            <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end' }}>
              <button
                onClick={() => setPending(null)}
                style={{
                  background: '#1a1a1a', color: '#555', border: '1px solid #333',
                  borderRadius: 3, padding: '6px 16px', cursor: 'pointer',
                  fontFamily: 'inherit', fontSize: 12,
                }}
              >
                Cancel
              </button>
              <button
                onClick={confirm}
                disabled={setMode.isPending}
                style={{
                  background: '#1a2a1a', color: '#44cc88', border: '1px solid #44cc88',
                  borderRadius: 3, padding: '6px 16px', cursor: 'pointer',
                  fontFamily: 'inherit', fontSize: 12,
                  opacity: setMode.isPending ? 0.5 : 1,
                }}
              >
                {setMode.isPending ? 'Saving…' : 'Confirm'}
              </button>
            </div>
          </div>
        </div>
      )}

      {toast && (
        <div style={{
          position: 'fixed', bottom: 24, right: 24,
          background: toast.startsWith('Error') ? '#2a1a1a' : '#1a2a1a',
          color: toast.startsWith('Error') ? '#cc4444' : '#44cc88',
          border: `1px solid ${toast.startsWith('Error') ? '#cc4444' : '#44cc88'}`,
          borderRadius: 4, padding: '8px 16px', fontSize: 12, zIndex: 2000,
        }}>
          {toast}
        </div>
      )}
    </div>
  );
}
