import React from 'react';
import { card, cardHead, cardBody, c, alpha, grpBox, grpTitle } from '../../styles/terminalUI';
import { useV2Backtest, V2SymbolMetrics } from '../../hooks/useSterlingV2';

const pct = (v: number, d = 1): string => (v == null || !isFinite(v) ? '—' : `${(v * 100).toFixed(d)}%`);
const num = (v: number, d = 2): string => (v == null || !isFinite(v) ? '—' : v.toFixed(d));
const signColor = (v: number): string => (v > 0 ? c.green : v < 0 ? c.red : c.dim);

const th: React.CSSProperties = {
  textAlign: 'right', padding: '6px 10px', fontSize: 9, fontWeight: 600,
  letterSpacing: '0.06em', color: c.dim, textTransform: 'uppercase',
  borderBottom: `1px solid ${c.border}`,
};
const td: React.CSSProperties = {
  textAlign: 'right', padding: '7px 10px', fontSize: 11, color: c.bright,
  fontVariantNumeric: 'tabular-nums', borderBottom: `1px solid ${alpha(c.border, 0.5)}`,
};

function Stat({ label, value, color }: { label: string; value: string; color?: string }) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
      <span style={{ fontSize: 9, letterSpacing: '0.07em', color: c.dim, fontWeight: 600, textTransform: 'uppercase' }}>{label}</span>
      <span style={{ fontSize: 20, fontWeight: 800, color: color || c.bright, fontVariantNumeric: 'tabular-nums' }}>{value}</span>
    </div>
  );
}

export function V2ResearchPane({ active }: { active: boolean }) {
  const { data, isLoading, error } = useV2Backtest(active);

  return (
    <div style={card}>
      <div style={cardHead}>
        <span>V2 RESEARCH — TEST SLICE (untouched 20%)</span>
        {data && (
          <span style={{ marginLeft: 'auto', fontSize: 10, color: c.dim }}>
            {data.strategy} · {data.tf}
          </span>
        )}
      </div>
      <div style={cardBody}>
        {isLoading && <div style={{ color: c.dim, fontSize: 12 }}>Running leak-free backtest…</div>}
        {error && <div style={{ color: c.red, fontSize: 12 }}>{String((error as Error).message)}</div>}
        {data && (
          <>
            <div style={{ ...grpBox, marginBottom: 14 }}>
              <div style={grpTitle}>PORTFOLIO (correlation-weighted, −20% DD breaker)</div>
              <div style={{ display: 'flex', gap: 32, flexWrap: 'wrap' }}>
                <Stat label="Net" value={pct(data.portfolio.net)} color={signColor(data.portfolio.net)} />
                <Stat label="Sharpe" value={num(data.portfolio.sharpe)} color={signColor(data.portfolio.sharpe)} />
                <Stat label="Max DD" value={pct(data.portfolio.max_dd)} color={c.red} />
              </div>
              <div style={{ fontSize: 10, color: c.dim, marginTop: 4 }}>
                Weights:{' '}
                {Object.entries(data.portfolio.weights).map(([k, v]) => `${k} ${(v * 100).toFixed(0)}%`).join(' · ')}
              </div>
            </div>

            <table style={{ width: '100%', borderCollapse: 'collapse' }}>
              <thead>
                <tr>
                  <th style={{ ...th, textAlign: 'left' }}>Symbol</th>
                  <th style={th}>Trades</th>
                  <th style={th}>Win</th>
                  <th style={th}>PF</th>
                  <th style={th}>Sharpe</th>
                  <th style={th}>Net</th>
                  <th style={th}>Max DD</th>
                </tr>
              </thead>
              <tbody>
                {Object.entries(data.per_symbol).map(([sym, m]: [string, V2SymbolMetrics]) => (
                  <tr key={sym}>
                    <td style={{ ...td, textAlign: 'left', fontWeight: 700 }}>{sym}</td>
                    <td style={td}>{m.trades}</td>
                    <td style={td}>{pct(m.win)}</td>
                    <td style={{ ...td, color: m.pf >= 1 ? c.green : c.red }}>{num(m.pf)}</td>
                    <td style={{ ...td, color: signColor(m.sharpe) }}>{num(m.sharpe)}</td>
                    <td style={{ ...td, color: signColor(m.net) }}>{pct(m.net)}</td>
                    <td style={{ ...td, color: c.red }}>{pct(m.max_dd)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            <div style={{ color: c.dim, fontSize: 10, marginTop: 10, lineHeight: 1.5 }}>
              V2 stack = long+short signals + vol-targeted sizing + correlation-aware portfolio
              with a hard −20% drawdown breaker (trailing exit rejected; conviction gate off for
              the combined book). Baseline long-only {data.strategy} was net-negative on all three
              symbols (see docs/sterling_v2/baseline_report.md).
            </div>
          </>
        )}
      </div>
    </div>
  );
}
