import React, { useState, useEffect } from 'react';
import { useScoringWeights, useUpdateScoringWeights, useResetScoringWeights } from '../hooks/useScoringWeights';
import type { ScoringWeights } from '../hooks/useScoringWeights';

const S: Record<string, React.CSSProperties> = {
  card:   { background: '#141414', border: '1px solid #222', borderRadius: 6, padding: 16, marginBottom: 16 },
  title:  { color: '#888', fontSize: 11, letterSpacing: 2, marginBottom: 14 },
  header: { display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 14 },
  row:    { display: 'flex', alignItems: 'center', gap: 12, marginBottom: 10 },
  label:  { color: '#888', fontSize: 11, width: 120, flexShrink: 0 },
  slider: { flex: 1, accentColor: '#44cc88' },
  val:    { color: '#e0e0e0', fontSize: 12, width: 40, textAlign: 'right' as const },
  sum:    { display: 'flex', justifyContent: 'space-between', padding: '8px 0', borderTop: '1px solid #1e1e1e', marginTop: 8 },
  btn:    { background: '#1a2a1a', color: '#44cc88', border: '1px solid #44cc88', padding: '5px 14px', borderRadius: 3, cursor: 'pointer', fontFamily: 'inherit', fontSize: 11 },
  btnGrey:{ background: '#1a1a1a', color: '#555', border: '1px solid #333', padding: '5px 14px', borderRadius: 3, cursor: 'pointer', fontFamily: 'inherit', fontSize: 11 },
  warn:   { color: '#f0c040', fontSize: 10, marginTop: 4 },
  saved:  { color: '#44cc88', fontSize: 10, marginTop: 4 },
};

const LABELS: Record<keyof ScoringWeights, string> = {
  regime:      'Macro regime',
  signal:      '1H signal',
  execution:   'Exec timing',
  dte:         'Days to expiry',
  health:      'Contract health',
  risk_reward: 'Risk / reward',
};

const DEFAULT: ScoringWeights = {
  regime: 0.20, signal: 0.20, execution: 0.15,
  dte: 0.15, health: 0.20, risk_reward: 0.10,
};

export function ScoringWeightsPanel() {
  const { data, isLoading } = useScoringWeights();
  const update = useUpdateScoringWeights();
  const reset  = useResetScoringWeights();
  const [local, setLocal] = useState<ScoringWeights>(DEFAULT);
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    if (data) setLocal(data);
  }, [data]);

  const totalWeight = Object.values(local).reduce((a, b) => a + b, 0);
  const sumOk = Math.abs(totalWeight - 1.0) < 0.01;

  const set = (key: keyof ScoringWeights, v: number) =>
    setLocal(prev => ({ ...prev, [key]: Math.round(v * 100) / 100 }));

  const handleSave = () => {
    update.mutate(local, {
      onSuccess: () => { setSaved(true); setTimeout(() => setSaved(false), 2000); },
    });
  };

  const handleReset = () => {
    reset.mutate(undefined, {
      onSuccess: (d) => { setLocal(d); setSaved(true); setTimeout(() => setSaved(false), 2000); },
    });
  };

  if (isLoading) return null;

  return (
    <div style={S.card}>
      <div style={S.header}>
        <div style={S.title}>SCORING WEIGHTS</div>
        <div style={{ display: 'flex', gap: 8 }}>
          <button style={S.btnGrey} onClick={handleReset} disabled={reset.isPending}>RESET</button>
          <button style={sumOk ? S.btn : { ...S.btn, opacity: 0.5 }} onClick={handleSave}
            disabled={update.isPending || !sumOk}>
            {update.isPending ? 'SAVING…' : 'SAVE'}
          </button>
        </div>
      </div>

      {(Object.keys(local) as Array<keyof ScoringWeights>).map(key => (
        <div key={key} style={S.row}>
          <span style={S.label}>{LABELS[key]}</span>
          <input
            type="range" min={0} max={1} step={0.05}
            value={local[key]}
            onChange={e => set(key, parseFloat(e.target.value))}
            style={S.slider}
          />
          <span style={S.val}>{(local[key] * 100).toFixed(0)}%</span>
        </div>
      ))}

      <div style={S.sum}>
        <span style={{ color: '#555', fontSize: 11 }}>Total weight</span>
        <span style={{ color: sumOk ? '#44cc88' : '#cc4444', fontSize: 12, fontWeight: 700 }}>
          {(totalWeight * 100).toFixed(0)}%
          {!sumOk && ' (must equal 100%)'}
        </span>
      </div>
      {saved && <div style={S.saved}>Weights saved.</div>}
      {update.error && <div style={S.warn}>{(update.error as Error).message}</div>}
    </div>
  );
}
