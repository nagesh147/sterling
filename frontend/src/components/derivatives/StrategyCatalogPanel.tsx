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
import React from 'react';
import { c, card, cardHead, cardBody, grpBox } from '../../styles/terminalUI';
import { useStrategyCatalog, StrategyCatalogEntry, StrategyCatalogCombo } from '../../hooks/useDerivatives';

const Badge: React.FC<{ text: string; tone: string }> = ({ text, tone }) => (
  <span style={{
    fontSize: 9, fontWeight: 800, letterSpacing: '0.04em', padding: '2px 6px',
    borderRadius: 4, color: tone, background: `${tone}22`, whiteSpace: 'nowrap',
  }}>{text}</span>
);

const ComboTable: React.FC<{ combos: StrategyCatalogCombo[] }> = ({ combos }) => (
  <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 10, marginTop: 10 }}>
    <thead>
      <tr style={{ color: c.dim, textAlign: 'right' }}>
        {['Sym', 'TF', 'Profile', 'Net', 'OOS Sh', 'P(loss)', 'MaxDD', 'Score'].map((h, i) => (
          <th key={h} style={{ padding: '2px 5px', fontWeight: 600, fontSize: 9,
            letterSpacing: '0.05em', textAlign: i < 3 ? 'left' : 'right', borderBottom: `1px solid ${c.border}`, color: c.muted }}>{h}</th>
        ))}
      </tr>
    </thead>
    <tbody>
      {combos.map((cb) => (
        <tr key={`${cb.symbol}:${cb.tf}:${cb.profile}`} style={{ color: c.text, borderBottom: `1px solid ${c.border2}` }}>
          <td style={{ padding: '4px 5px', fontWeight: 700 }}>{cb.symbol}</td>
          <td style={{ padding: '4px 5px' }}>{cb.tf}</td>
          <td style={{ padding: '4px 5px' }} title={cb.bracket}>{cb.profile}</td>
          <td style={{ padding: '4px 5px', textAlign: 'right', color: cb.net_return_pct >= 0 ? c.green : c.red }}>
            {cb.net_return_pct >= 0 ? '+' : ''}{cb.net_return_pct}%
          </td>
          <td style={{ padding: '4px 5px', textAlign: 'right' }}>{cb.oos_sharpe ?? '—'}</td>
          <td style={{ padding: '4px 5px', textAlign: 'right',
            color: cb.p_loss_pct <= 20 ? c.green : cb.p_loss_pct <= 30 ? c.amber : c.red }}>
            {cb.p_loss_pct}%
          </td>
          <td style={{ padding: '4px 5px', textAlign: 'right', color: c.red }}>{cb.max_dd_pct}%</td>
          <td style={{ padding: '4px 5px', textAlign: 'right', fontWeight: 800, color: c.amber }}>{cb.signal_score}</td>
        </tr>
      ))}
    </tbody>
  </table>
);

const SimpleStrategyCard: React.FC<{ s: StrategyCatalogEntry }> = ({ s }) => {
  if (!s.live) return null; // Keep it simple by only showing what's actually running
  
  return (
    <div style={{ ...grpBox, padding: '10px 12px' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 6 }}>
        <span style={{ fontSize: 11, fontWeight: 700, color: c.bright }}>
          {s.name.replace('scalping/', '').toUpperCase().replace(/_/g, ' ')}
        </span>
        <div style={{ display: 'flex', gap: 4 }}>
          {s.combos.slice(0, 3).map((cb, i) => (
            <Badge key={i} text={cb.tf} tone={c.blue} />
          ))}
        </div>
      </div>
      
      <div style={{ fontSize: 10, color: c.text, lineHeight: 1.5, marginBottom: 2 }}>
        {s.tagline}
      </div>
      <div style={{ fontSize: 9.5, color: c.dim, lineHeight: 1.4, marginBottom: 8, fontStyle: 'italic' }}>
        {s.how_it_works}
      </div>
      
      <div style={{ display: 'flex', gap: 16, fontSize: 9.5, color: c.dim }}>
        <span><b style={{ color: c.text }}>Engine:</b> {s.engine.split('.')[0]}</span>
        <span><b style={{ color: c.text }}>Routing:</b> {s.instrument.split(',')[0]}</span>
      </div>

      {s.combos.length > 0 && (
        <ComboTable combos={s.combos} />
      )}
    </div>
  );
};

export const StrategyCatalogPanel: React.FC = () => {
  const q = useStrategyCatalog();
  const d = q.data;

  if (!d) {
    return (
      <div style={{ ...card, padding: 16, fontSize: 11, color: c.dim }}>
        {q.isError ? 'Failed to load strategy catalog.' : 'Loading strategy catalog…'}
      </div>
    );
  }

  const liveStrategies = d.strategies.filter((s) => s.live);

  return (
    <div style={card}>
      <div style={cardHead}>
        <span>STRATEGY CATALOG · WHAT'S ACTUALLY RUNNING</span>
        <span style={{ marginLeft: 'auto', fontSize: 9, color: c.dim }}>
          {liveStrategies.length} ACTIVE ALGORITHMS
        </span>
      </div>
      <div style={{ ...cardBody, display: 'flex', flexDirection: 'column', gap: 10 }}>
        
        <div style={{ fontSize: 9.5, color: c.amber, background: `${c.amber}11`, padding: '8px 12px', borderRadius: 4, border: `1px solid ${c.amber}33`, lineHeight: 1.5 }}>
          <b>Why only these symbols?</b> Not every strategy works on every coin. The AI Gatekeeper simulates every strategy across all symbols and timeframes, but automatically deletes combinations that fail to prove a statistical edge in Out-Of-Sample testing. <b>If a symbol or timeframe isn't listed below, it was tested and rejected.</b> The tables below show the verified survivors.
        </div>

        {liveStrategies.map((s) => (
          <SimpleStrategyCard key={s.id} s={s} />
        ))}
      </div>
    </div>
  );
};

