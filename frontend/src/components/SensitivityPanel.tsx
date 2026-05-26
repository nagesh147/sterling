import React from 'react';
import { useSensitivity, useRunSensitivity } from '../hooks/useSensitivity';
import { useSelectedUnderlying } from '../store/useStore';
import { c, tint } from '../styles/terminalUI';

const S: Record<string, React.CSSProperties> = {
  card: { background: c.surface, border: `1px solid ${c.border}`, borderRadius: 6, padding: 16, marginBottom: 16 },
  title: { color: c.dim, fontSize: 11, fontWeight: 700, letterSpacing: 2, marginBottom: 12 },
  row: { display: 'flex', gap: 12, alignItems: 'center', marginBottom: 12 },
  btn: { background: tint(c.blue, 14), color: c.blue, border: `1px solid ${c.blue}`, padding: '6px 14px', borderRadius: 4, cursor: 'pointer', fontFamily: 'inherit', fontSize: 12 },
  noData: { color: c.dim, fontSize: 12, padding: '16px 0' },
  stale: { color: c.amber, fontSize: 10 },
};

function HBar({ label, value, max, isTop3, bestVal }: {
  label: string; value: number; max: number; isTop3: boolean; bestVal: string | number;
}) {
  const pct = max > 0 ? Math.min(100, (value / max) * 100) : 0;
  const color = isTop3 ? c.amber : c.border2;
  return (
    <div style={{ marginBottom: 8 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 3 }}>
        <span style={{ color: isTop3 ? c.amber : c.dim, fontSize: 11 }}>{label}</span>
        <span style={{ color: c.dim, fontSize: 10 }}>best: {bestVal} · σ: {value.toFixed(4)}</span>
      </div>
      <div style={{ height: 6, background: c.border, borderRadius: 3 }}>
        <div style={{ width: `${pct}%`, height: '100%', background: color, borderRadius: 3, transition: 'width 0.3s' }} />
      </div>
    </div>
  );
}

export function SensitivityPanel() {
  const underlying = useSelectedUnderlying();
  const { data: cached } = useSensitivity(underlying);
  const { mutate: run, isPending: running, data: fresh, error } = useRunSensitivity();

  const results = fresh ?? cached?.results ?? [];
  const maxSens = results.length > 0 ? Math.max(...results.map(r => r.sensitivity)) : 0;

  return (
    <div style={S.card}>
      <div style={S.title}>PARAMETER SENSITIVITY</div>
      <div style={S.row}>
        <button style={S.btn} disabled={running} onClick={() => run({ underlying })}>
          {running ? 'Sweeping…' : 'Run Sensitivity'}
        </button>
        {cached?.computed_at && !fresh && (
          <span style={S.stale}>
            Cached{cached.is_stale ? ' (stale)' : ''}: {cached.computed_at}
          </span>
        )}
      </div>

      {error && <div style={{ color: c.red, fontSize: 11 }}>{String(error)}</div>}

      {results.length === 0 && !running && (
        <div style={S.noData}>No results — click Run Sensitivity to sweep parameters</div>
      )}

      {results.length > 0 && (
        <div>
          {results.map((r, i) => (
            <HBar
              key={r.parameter}
              label={r.parameter}
              value={r.sensitivity}
              max={maxSens}
              isTop3={i < 3}
              bestVal={r.best_value}
            />
          ))}
        </div>
      )}
    </div>
  );
}
