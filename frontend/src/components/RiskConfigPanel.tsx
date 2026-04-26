import React, { useState, useEffect } from 'react';
import { useRiskConfig, useUpdateRiskConfig, useResetRiskConfig } from '../hooks/useRiskConfig';
import type { RiskParams } from '../hooks/useRiskConfig';

const styles: Record<string, React.CSSProperties> = {
  card: { background: '#141414', border: '1px solid #222', borderRadius: 6, padding: 16, marginBottom: 16 },
  title: { color: '#888', fontSize: 11, letterSpacing: 2, marginBottom: 12 },
  grid: { display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 12, marginBottom: 14 },
  fieldWrap: { display: 'flex', flexDirection: 'column', gap: 4 },
  label: { color: '#555', fontSize: 11 },
  input: {
    background: '#111', color: '#e0e0e0', border: '1px solid #2a2a2a',
    borderRadius: 3, padding: '5px 8px', fontFamily: 'inherit', fontSize: 13, width: '100%',
  },
  actions: { display: 'flex', gap: 10 },
  saveBtn: {
    background: '#1a2a1a', color: '#44cc88', border: '1px solid #44cc88',
    padding: '6px 16px', borderRadius: 4, cursor: 'pointer', fontFamily: 'inherit', fontSize: 12,
  },
  resetBtn: {
    background: '#1a1a1a', color: '#888', border: '1px solid #333',
    padding: '6px 16px', borderRadius: 4, cursor: 'pointer', fontFamily: 'inherit', fontSize: 12,
  },
  error: { color: '#cc4444', fontSize: 11, marginTop: 6 },
  saved: { color: '#44cc88', fontSize: 11, marginTop: 6 },
};

const FIELDS: Array<{ key: keyof RiskParams; label: string; step: number }> = [
  { key: 'capital', label: 'CAPITAL (USD)', step: 1000 },
  { key: 'max_position_pct', label: 'MAX POSITION %', step: 0.01 },
  { key: 'max_contracts', label: 'MAX CONTRACTS', step: 1 },
  { key: 'partial_profit_r1', label: 'PARTIAL PROFIT R1', step: 0.1 },
  { key: 'partial_profit_r2', label: 'PARTIAL PROFIT R2', step: 0.1 },
  { key: 'time_stop_dte', label: 'TIME STOP DTE', step: 1 },
  { key: 'financial_stop_pct', label: 'FINANCIAL STOP %', step: 0.05 },
];

export function RiskConfigPanel() {
  const { data } = useRiskConfig();
  const update = useUpdateRiskConfig();
  const reset = useResetRiskConfig();
  const [form, setForm] = useState<RiskParams | null>(null);
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    if (data && !form) setForm(data);
  }, [data]);

  if (!form) return <div style={styles.card}><div style={styles.title}>RISK CONFIG — loading…</div></div>;

  const handleChange = (key: keyof RiskParams, val: string) => {
    setForm(prev => prev ? { ...prev, [key]: parseFloat(val) || 0 } : prev);
    setSaved(false);
  };

  const handleSave = () => {
    if (!form) return;
    update.mutate(form, {
      onSuccess: () => setSaved(true),
    });
  };

  const handleReset = () => {
    reset.mutate(undefined, {
      onSuccess: (data) => {
        setForm(data);
        setSaved(false);
      },
    });
  };

  return (
    <div style={styles.card}>
      <div style={styles.title}>RISK CONFIG</div>
      <div style={styles.grid}>
        {FIELDS.map(({ key, label, step }) => (
          <div key={key} style={styles.fieldWrap}>
            <label style={styles.label}>{label}</label>
            <input
              style={styles.input}
              type="number"
              step={step}
              value={form[key]}
              onChange={e => handleChange(key, e.target.value)}
            />
          </div>
        ))}
      </div>
      <div style={styles.actions}>
        <button style={styles.saveBtn} onClick={handleSave} disabled={update.isPending}>
          {update.isPending ? 'SAVING…' : 'SAVE CONFIG'}
        </button>
        <button style={styles.resetBtn} onClick={handleReset} disabled={reset.isPending}>
          RESET TO DEFAULT
        </button>
      </div>
      {update.error && <div style={styles.error}>{(update.error as Error).message}</div>}
      {saved && <div style={styles.saved}>Saved.</div>}
    </div>
  );
}
