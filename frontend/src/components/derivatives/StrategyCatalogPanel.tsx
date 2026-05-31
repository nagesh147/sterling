/**
 * StrategyCatalogPanel — "what is this strategy, really?"
 *
 * The candidate tables show terse ids (ma_crossover, smc, …) that don't tell a
 * user what's running: which logic, what timeframe, long or short, which engine,
 * future or option, and how it has performed. Worse, the same id can mean two
 * different things in two engines. This panel pulls the backend strategy catalog
 * (/derivatives/strategy-catalog) and lays it out in plain English, with the
 * exact live, robustness-validated configs and their metrics under each one.
 */
import React, { useState } from 'react';
import { c, alpha, card, cardHead, cardBody, grpBox, grpTitle } from '../../styles/terminalUI';
import { useStrategyCatalog, StrategyCatalogEntry, StrategyCatalogCombo } from '../../hooks/useDerivatives';

const Badge: React.FC<{ text: string; tone: string }> = ({ text, tone }) => (
  <span style={{
    fontSize: 8.5, fontWeight: 800, letterSpacing: '0.06em', padding: '1px 6px',
    borderRadius: 4, border: `1px solid ${alpha(tone, 0.4)}`, color: tone,
    background: alpha(tone, 0.12), whiteSpace: 'nowrap',
  }}>{text}</span>
);

const ComboTable: React.FC<{ combos: StrategyCatalogCombo[] }> = ({ combos }) => (
  <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 10 }}>
    <thead>
      <tr style={{ color: c.dim, textAlign: 'right' }}>
        {['Sym', 'TF', 'Profile', 'Net', 'OOS Sh', 'P(loss)', 'MaxDD', 'Score'].map((h, i) => (
          <th key={h} style={{ padding: '2px 5px', fontWeight: 700, fontSize: 8.5,
            letterSpacing: '0.05em', textAlign: i < 3 ? 'left' : 'right' }}>{h}</th>
        ))}
      </tr>
    </thead>
    <tbody>
      {combos.map((cb) => (
        <tr key={`${cb.symbol}:${cb.tf}:${cb.profile}`} style={{ color: c.text, borderTop: `1px solid ${c.border2}` }}>
          <td style={{ padding: '2px 5px', fontWeight: 700 }}>{cb.symbol}</td>
          <td style={{ padding: '2px 5px' }}>{cb.tf}</td>
          <td style={{ padding: '2px 5px' }} title={cb.bracket}>{cb.profile}</td>
          <td style={{ padding: '2px 5px', textAlign: 'right', color: cb.net_return_pct >= 0 ? c.green : c.red }}>
            {cb.net_return_pct >= 0 ? '+' : ''}{cb.net_return_pct}%
          </td>
          <td style={{ padding: '2px 5px', textAlign: 'right' }}>{cb.oos_sharpe ?? '—'}</td>
          <td style={{ padding: '2px 5px', textAlign: 'right',
            color: cb.p_loss_pct <= 20 ? c.green : cb.p_loss_pct <= 30 ? c.amber : c.red }}>
            {cb.p_loss_pct}%
          </td>
          <td style={{ padding: '2px 5px', textAlign: 'right', color: c.red }}>{cb.max_dd_pct}%</td>
          <td style={{ padding: '2px 5px', textAlign: 'right', fontWeight: 800, color: c.amber }}>{cb.signal_score}</td>
        </tr>
      ))}
    </tbody>
  </table>
);

const StrategyCard: React.FC<{ s: StrategyCatalogEntry }> = ({ s }) => {
  const [open, setOpen] = useState(s.live);
  const longOnly = s.direction.toLowerCase().startsWith('long only');
  return (
    <div style={{ ...grpBox, gap: 6, opacity: s.live ? 1 : 0.62 }}>
      {/* header row */}
      <button onClick={() => setOpen((o) => !o)} style={{
        display: 'flex', alignItems: 'center', gap: 8, background: 'transparent',
        border: 'none', color: c.bright, cursor: 'pointer', fontFamily: 'inherit',
        fontSize: 12, fontWeight: 700, padding: 0, textAlign: 'left', width: '100%',
      }}>
        <span style={{ fontSize: 9, color: c.dim, width: 10 }}>{open ? '▾' : '▸'}</span>
        <span>{s.name}</span>
        <span style={{ fontSize: 9, color: c.dim, fontWeight: 400 }}>({s.id})</span>
        <span style={{ marginLeft: 'auto', display: 'flex', gap: 5, alignItems: 'center' }}>
          <Badge text={longOnly ? 'LONG ONLY' : 'LONG & SHORT'} tone={longOnly ? c.blue : c.amber} />
          {s.live
            ? <Badge text={`${s.live_combo_count} LIVE`} tone={c.green} />
            : <Badge text="NOT LIVE" tone={c.dim} />}
        </span>
      </button>

      <div style={{ fontSize: 10.5, color: c.text, paddingLeft: 18 }}>{s.tagline}</div>

      {open && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 8, paddingLeft: 18, marginTop: 2 }}>
          <div style={{ fontSize: 10, color: c.dim, lineHeight: 1.5 }}>{s.how_it_works}</div>

          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 12, fontSize: 9.5, color: c.dim }}>
            <span><b style={{ color: c.text }}>Engine:</b> {s.engine}</span>
          </div>
          <div style={{ fontSize: 9.5, color: c.dim }}>
            <b style={{ color: c.text }}>Routing:</b> {s.instrument}
          </div>
          {s.note && (
            <div style={{ fontSize: 9.5, color: c.amber, background: alpha(c.amber, 0.08),
              border: `1px solid ${alpha(c.amber, 0.25)}`, borderRadius: 4, padding: '5px 7px', lineHeight: 1.45 }}>
              ⚠ {s.note}
            </div>
          )}

          {s.live ? (
            <div style={{ marginTop: 2 }}>
              <div style={{ fontSize: 8.5, fontWeight: 700, color: c.dim, letterSpacing: '0.06em', marginBottom: 3 }}>
                LIVE VALIDATED CONFIGS
              </div>
              <ComboTable combos={s.combos} />
            </div>
          ) : (
            <div style={{ fontSize: 9.5, color: c.dim, fontStyle: 'italic' }}>
              No config of this strategy currently clears the robustness gate, so it is not
              emitting live edge signals.
            </div>
          )}
        </div>
      )}
    </div>
  );
};

export const StrategyCatalogPanel: React.FC = () => {
  const q = useStrategyCatalog();
  const d = q.data;

  if (!d) {
    return <div style={{ ...card, padding: 16, fontSize: 11, color: c.dim }}>
      {q.isError ? 'Failed to load strategy catalog.' : 'Loading strategy catalog…'}
    </div>;
  }

  return (
    <div style={card}>
      <div style={cardHead}>
        <span>STRATEGY CATALOG · WHAT'S ACTUALLY RUNNING</span>
        <span style={{ marginLeft: 'auto', fontSize: 9, color: c.dim }}>
          {d.strategies.filter((s) => s.live).length} of {d.strategies.length} live
        </span>
      </div>
      <div style={{ ...cardBody, display: 'flex', flexDirection: 'column', gap: 12 }}>

        <div style={{ fontSize: 9.5, color: c.dim, lineHeight: 1.5, display: 'flex', flexDirection: 'column', gap: 5 }}>
          <div><b style={{ color: c.green }}>Edge feed</b> — {d.engines.edge_feed}</div>
          <div><b style={{ color: c.cyan }}>Scalping scanner</b> — {d.engines.scalping_scanner}</div>
          <div style={{ marginTop: 2 }}><b style={{ color: c.text }}>Futures vs options</b> — {d.routing}</div>
        </div>

        <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
          {d.strategies.map((s) => <StrategyCard key={s.id} s={s} />)}
        </div>

        <div style={{ fontSize: 8.5, color: c.dim, fontStyle: 'italic', borderTop: `1px solid ${c.border}`, paddingTop: 6 }}>
          Metrics are from the robustness scan on real 1-minute data: <b>OOS Sh</b> = out-of-sample
          Sharpe (CPCV), <b>P(loss)</b> = Monte-Carlo probability of ending underwater, <b>MaxDD</b> =
          worst-case drawdown. Higher score = higher conviction.
        </div>
      </div>
    </div>
  );
};
