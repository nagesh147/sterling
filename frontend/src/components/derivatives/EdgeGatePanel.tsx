/**
 * EdgeGatePanel — operator control for the edge-feed admission gate.
 *
 * The edge feed only emits live signals for backtest combos that clear a
 * threshold on net return, Sharpe and trade count (see BACKTEST_EDGE_REPORT).
 * This panel lets the operator tune those thresholds and immediately see how
 * many (and which) combos the new gate admits.
 *
 * Loosen min Sharpe to admit more setups (e.g. Price Action 1h); tighten to
 * keep only the highest-conviction 4h winners. Changes are in-memory (lost on
 * restart), matching the per-strategy profile editor. Edge rows stay
 * display-only — this gate changes WHICH combos show, not whether they trade.
 */
import React, { useEffect, useState } from 'react';
import { c, alpha, card, cardHead, cardBody, grpBox, grpTitle } from '../../styles/terminalUI';
import { EdgeGate, useEdgeGate, usePatchEdgeGate } from '../../hooks/useDerivatives';

const NumRow: React.FC<{
  label: string; hint: string; value: number; step?: number; min?: number; onChange: (v: number) => void;
}> = ({ label, hint, value, step = 0.1, min, onChange }) => (
  <label style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 8, fontSize: 11, color: c.dim }}>
    <span>
      {label}
      <span style={{ marginLeft: 6, fontSize: 9, color: c.dim, fontWeight: 400 }}>— {hint}</span>
    </span>
    <input
      type="number" step={step} min={min} value={Number.isFinite(value) ? value : 0}
      onChange={(e) => onChange(parseFloat(e.target.value))}
      style={{
        width: 90, background: c.bg, border: `1px solid ${c.border}`,
        borderRadius: 4, color: c.bright, padding: '3px 6px',
        fontFamily: 'inherit', fontSize: 11, textAlign: 'right',
      }}
    />
  </label>
);

export const EdgeGatePanel: React.FC = () => {
  const q = useEdgeGate();
  const patch = usePatchEdgeGate();
  const persisted = q.data?.gate;
  const [draft, setDraft] = useState<EdgeGate | null>(persisted ?? null);

  useEffect(() => {
    if (persisted) setDraft(persisted);
  }, [persisted]);

  if (!draft) {
    return <div style={{ ...card, padding: 16, fontSize: 11, color: c.dim }}>Loading edge gate…</div>;
  }

  const set = <K extends keyof EdgeGate>(k: K, v: number) =>
    setDraft({ ...draft, [k]: Number.isFinite(v) ? v : 0 });

  const dirty = JSON.stringify(draft) !== JSON.stringify(persisted);
  const admitted = q.data?.admitted ?? [];

  return (
    <div style={card}>
      <div style={cardHead}>
        <span>EDGE FEED · ADMISSION GATE</span>
        <span style={{ marginLeft: 8, fontSize: 9, color: c.dim }}>
          {q.data?.admitted_count ?? 0} combo{(q.data?.admitted_count ?? 0) === 1 ? '' : 's'} admitted
        </span>
        <span style={{ marginLeft: 'auto' }}>
          <button
            disabled={!dirty || patch.isPending}
            onClick={() => patch.mutate(draft)}
            style={{
              padding: '4px 10px', borderRadius: 5,
              background: dirty ? alpha(c.blue, 0.15) : 'transparent',
              border: `1px solid ${dirty ? alpha(c.blue, 0.4) : c.border}`,
              color: dirty ? c.blue : c.dim, fontSize: 10, fontWeight: 700,
              letterSpacing: '0.06em', cursor: dirty ? 'pointer' : 'default',
              fontFamily: 'inherit',
            }}>
            {patch.isPending ? 'APPLYING…' : dirty ? 'APPLY' : 'SAVED'}
          </button>
        </span>
      </div>
      <div style={{ ...cardBody, display: 'flex', flexDirection: 'column', gap: 14 }}>

        <div style={{ ...grpBox, gap: 8 }}>
          <div style={grpTitle}>THRESHOLDS</div>
          <NumRow label="Min Sharpe" hint="risk-adjusted edge floor"
                  value={draft.min_sharpe} step={0.1}
                  onChange={(v) => set('min_sharpe', v)} />
          <NumRow label="Min net return" hint="decimal, e.g. 0.0 = breakeven"
                  value={draft.min_net_return} step={0.05}
                  onChange={(v) => set('min_net_return', v)} />
          <NumRow label="Min trades" hint="sample-size floor"
                  value={draft.min_trades} step={1} min={0}
                  onChange={(v) => set('min_trades', Math.round(v))} />
          <div style={{ fontSize: 9, color: c.dim, marginTop: 2 }}>
            Default 0.8 / 0.0 / 50 admits the 4h winners. Lower Min Sharpe to ~0.7 to also
            admit Price Action 1h. In-memory — resets on restart.
          </div>
        </div>

        <div style={{ ...grpBox, gap: 6 }}>
          <div style={grpTitle}>ADMITTED COMBOS</div>
          {admitted.length === 0 ? (
            <div style={{ fontSize: 10, color: c.dim }}>None — the gate is too strict for the current results.</div>
          ) : (
            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 10 }}>
              <thead>
                <tr style={{ color: c.dim, textAlign: 'left' }}>
                  {['Strategy', 'TF', 'Sym', 'Prof', 'Shrp', 'PF', 'Net', 'Score'].map((h) => (
                    <th key={h} style={{ padding: '2px 4px', fontWeight: 700, fontSize: 8.5, letterSpacing: '0.06em' }}>{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {admitted.map((cmb) => (
                  <tr key={`${cmb.strategy}:${cmb.tf}:${cmb.symbol}:${cmb.profile}`} style={{ color: c.text, borderTop: `1px solid ${c.border2}` }}>
                    <td style={{ padding: '2px 4px' }}>{cmb.strategy}</td>
                    <td style={{ padding: '2px 4px' }}>{cmb.tf}</td>
                    <td style={{ padding: '2px 4px' }}>{cmb.symbol.replace('USD', '')}</td>
                    <td style={{ padding: '2px 4px' }}>{cmb.profile}</td>
                    <td style={{ padding: '2px 4px' }}>{cmb.sharpe.toFixed(2)}</td>
                    <td style={{ padding: '2px 4px' }}>{cmb.pf.toFixed(2)}</td>
                    <td style={{ padding: '2px 4px', color: cmb.net_return >= 0 ? c.green : c.red }}>
                      {(cmb.net_return * 100).toFixed(0)}%
                    </td>
                    <td style={{ padding: '2px 4px', fontWeight: 700, color: c.amber }}>{cmb.signal_score.toFixed(0)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      </div>
    </div>
  );
};
