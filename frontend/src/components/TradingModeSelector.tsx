import React, { useState } from 'react';
import { useTradingMode, useSetTradingMode, useAllTradingModes } from '../hooks/useTradingMode';

const MODE_COLOR: Record<string, string> = {
  scalping: '#ff7f6e',
  intraday: '#f0c040',
  swing: '#44cc88',
  positional: '#aa88ff',
};

const wrapStyle: React.CSSProperties = { display: 'flex', alignItems: 'center', gap: 8 };

function badgeStyle(name: string): React.CSSProperties {
  return {
    display: 'inline-block', padding: '2px 8px', borderRadius: 3,
    fontSize: 10, fontWeight: 700, letterSpacing: 1,
    background: `${MODE_COLOR[name] ?? '#555'}22`,
    color: MODE_COLOR[name] ?? '#888',
    border: `1px solid ${MODE_COLOR[name] ?? '#555'}55`,
  };
}

const styles: Record<string, React.CSSProperties> = {
  wrap: wrapStyle,
  select: {
    background: '#111', color: '#ccc', border: '1px solid #333',
    borderRadius: 3, padding: '4px 8px', fontFamily: 'inherit',
    fontSize: 11, cursor: 'pointer',
  },
  modal: {
    position: 'fixed', inset: 0, background: '#000000aa',
    display: 'flex', alignItems: 'center', justifyContent: 'center',
    zIndex: 1000,
  },
  dialog: {
    background: '#141414', border: '1px solid #333', borderRadius: 6,
    padding: 24, minWidth: 340, maxWidth: 460,
  },
  title: { color: '#e0e0e0', fontWeight: 700, fontSize: 14, marginBottom: 12 },
  row: { display: 'flex', justifyContent: 'space-between', fontSize: 12, padding: '4px 0', color: '#888' },
  val: { color: '#ccc' },
  btns: { display: 'flex', gap: 8, marginTop: 20, justifyContent: 'flex-end' },
  confirmBtn: {
    background: '#1a2a1a', color: '#44cc88', border: '1px solid #44cc88',
    borderRadius: 3, padding: '6px 16px', cursor: 'pointer', fontFamily: 'inherit', fontSize: 12,
  },
  cancelBtn: {
    background: '#1a1a1a', color: '#555', border: '1px solid #333',
    borderRadius: 3, padding: '6px 16px', cursor: 'pointer', fontFamily: 'inherit', fontSize: 12,
  },
  toast: {
    position: 'fixed', bottom: 24, right: 24,
    background: '#1a2a1a', color: '#44cc88',
    border: '1px solid #44cc88', borderRadius: 4,
    padding: '8px 16px', fontSize: 12, zIndex: 2000,
  },
};

export function TradingModeSelector() {
  const { data: current } = useTradingMode();
  const { data: allModes } = useAllTradingModes();
  const setMode = useSetTradingMode();
  const [pending, setPending] = useState<string | null>(null);
  const [toast, setToast] = useState('');

  const handleChange = (e: React.ChangeEvent<HTMLSelectElement>) => {
    const name = e.target.value;
    if (name !== current?.name) setPending(name);
  };

  const confirm = () => {
    if (!pending) return;
    setMode.mutate({ name: pending }, {
      onSuccess: (data) => {
        setToast(`Switched to ${data.config.display} mode`);
        setTimeout(() => setToast(''), 3000);
        setPending(null);
      },
    });
  };

  const currentName = current?.name ?? 'swing';
  const pendingCfg = pending && allModes ? allModes[pending] : null;
  const currentCfg = current?.config;

  return (
    <div style={styles.wrap}>
      <span style={badgeStyle(currentName)}>{currentName.toUpperCase()}</span>
      <select style={styles.select} value={currentName} onChange={handleChange}>
        {['scalping', 'intraday', 'swing', 'positional'].map((m) => (
          <option key={m} value={m}>{m.charAt(0).toUpperCase() + m.slice(1)}</option>
        ))}
      </select>

      {pending && pendingCfg && currentCfg && (
        <div style={styles.modal} onClick={() => setPending(null)}>
          <div style={styles.dialog} onClick={(e) => e.stopPropagation()}>
            <div style={styles.title}>Switch to {pendingCfg.display} mode?</div>
            <div style={{ color: '#666', fontSize: 11, marginBottom: 12 }}>Changes:</div>
            {[
              ['DTE range', `${currentCfg.dte_min}–${currentCfg.dte_max}d → ${pendingCfg.dte_min}–${pendingCfg.dte_max}d`],
              ['Position size', `${(currentCfg.position_pct * 100).toFixed(1)}% → ${(pendingCfg.position_pct * 100).toFixed(1)}%`],
              ['Stop ATR mult', `${currentCfg.stop_atr_mult}× → ${pendingCfg.stop_atr_mult}×`],
              ['Max positions', `${currentCfg.max_concurrent} → ${pendingCfg.max_concurrent}`],
            ].map(([label, val]) => (
              <div key={label as string} style={styles.row}>
                <span>{label}</span>
                <span style={styles.val}>{val}</span>
              </div>
            ))}
            <div style={styles.btns}>
              <button style={styles.cancelBtn} onClick={() => setPending(null)}>Cancel</button>
              <button style={styles.confirmBtn} onClick={confirm}>
                {setMode.isPending ? 'Switching…' : 'Confirm'}
              </button>
            </div>
          </div>
        </div>
      )}

      {toast && <div style={styles.toast}>{toast}</div>}
    </div>
  );
}
