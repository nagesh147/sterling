import React, { useState } from 'react';
import { usePaperState, usePaperTrades, usePaperSummary, PaperPosition } from '../../hooks/usePaperBook';
import { PaperEquityCurve } from './PaperEquityCurve';

const box: React.CSSProperties = {
  border: '1px solid var(--border)', borderRadius: 6, padding: 16, marginBottom: 16,
};
const dim: React.CSSProperties = { color: 'var(--text-dim)', fontSize: 11, letterSpacing: '0.08em' };
const pct = (x?: number) => (x == null ? '—' : `${(x * 100).toFixed(2)}%`);
const usd = (x?: number) => (x == null ? '—' : `$${x.toLocaleString(undefined, { maximumFractionDigits: 2 })}`);

function NotLiveBanner() {
  return (
    <div style={{ background: 'var(--accent)18', border: '1px solid var(--accent)',
                  borderRadius: 6, padding: '8px 14px', marginBottom: 16,
                  fontSize: 11, letterSpacing: '0.12em', fontWeight: 600,
                  color: 'var(--accent)' }}>
      RESEARCH · PAPER · NOT LIVE MONEY — DSR 0.327 &lt; 0.5, not deflation-provable
    </div>
  );
}

export function PositionsTable({ positions }: { positions: PaperPosition[] }) {
  if (!positions?.length) return <div style={dim}>No open positions.</div>;
  return (
    <table style={{ width: '100%', fontSize: 12, borderCollapse: 'collapse' }}>
      <thead>
        <tr style={dim}>
          {['SYMBOL', 'SLEEVE', 'DIR', 'ENTRY', 'SL', 'TP', 'EXIT', 'REDS', 'UNREAL'].map(h => (
            <th key={h} style={{ textAlign: 'left', padding: '4px 8px' }}>{h}</th>
          ))}
        </tr>
      </thead>
      <tbody>
        {positions.map((p, i) => (
          <tr key={i} style={{ borderTop: '1px solid var(--border)' }}>
            <td style={{ padding: '4px 8px' }}>{p.symbol}</td>
            <td style={{ padding: '4px 8px' }}>{p.sleeve ?? '—'}</td>
            <td style={{ padding: '4px 8px',
                         color: p.direction === 'short' ? '#ef4444' : '#22c55e' }}>
              {p.direction}</td>
            <td style={{ padding: '4px 8px' }}>{usd(p.entry_price)}</td>
            <td style={{ padding: '4px 8px' }}>{usd(p.sl)}</td>
            <td style={{ padding: '4px 8px' }}>{usd(p.tp)}</td>
            <td style={{ padding: '4px 8px' }}>{p.exit_mode || '—'}</td>
            <td style={{ padding: '4px 8px' }}>
              {p.current_red_count != null && p.exit_threshold != null ? (
                <>
                  {p.current_red_count}/{p.exit_threshold}
                  <div style={{width: 40, height: 3, background: '#222', marginTop: 1}}>
                    <div style={{width: `${Math.min(100, (p.current_red_count / p.exit_threshold) * 100)}%`, height: '100%', background: p.current_red_count >= p.exit_threshold ? '#f44' : '#4a4'}} />
                  </div>
                </>
              ) : '—'}
            </td>
            <td style={{ padding: '4px 8px',
                         color: (p.unrealized_pnl ?? 0) >= 0 ? '#22c55e' : '#ef4444' }}>
              {pct(p.unrealized_pnl)}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

export function PaperResearchTab() {
  const [mode, setMode] = useState<'guided' | 'pro'>('guided');
  const state = usePaperState();
  const trades = usePaperTrades();
  const summary = usePaperSummary();

  const s = state.data;
  if (state.isLoading) return <div style={dim}>Loading paper book…</div>;
  if (!s?.available) {
    return (
      <div>
        <NotLiveBanner />
        <div style={box}>Paper book not generated yet. Run
          <code> python -m study.paper_trader</code>{s?.reason ? ` (${s.reason})` : ''}.</div>
      </div>
    );
  }

  const sum = summary.data;
  const upColor = (s.return_pct ?? 0) >= 0 ? '#22c55e' : '#ef4444';

  return (
    <div>
      <NotLiveBanner />

      <div style={{ display: 'flex', gap: 8, marginBottom: 16 }}>
        {(['guided', 'pro'] as const).map(m => (
          <button key={m} onClick={() => setMode(m)} style={{
            background: 'none', border: '1px solid var(--border)', borderRadius: 4,
            cursor: 'pointer', fontFamily: 'inherit', fontSize: 11, padding: '6px 14px',
            letterSpacing: '0.08em', fontWeight: mode === m ? 600 : 400,
            color: mode === m ? 'var(--text-primary)' : 'var(--text-dim)',
            borderColor: mode === m ? 'var(--accent)' : 'var(--border)',
          }}>{m.toUpperCase()}</button>
        ))}
        <button onClick={() => { state.refetch(); trades.refetch(); }} style={{
          marginLeft: 'auto', background: 'none', border: '1px solid var(--border)',
          borderRadius: 4, cursor: 'pointer', fontFamily: 'inherit', fontSize: 11,
          padding: '6px 14px', color: 'var(--text-dim)' }}>↻ REFRESH</button>
      </div>

      {/* Hero — both modes */}
      <div style={{ ...box, display: 'flex', alignItems: 'baseline', gap: 16, flexWrap: 'wrap' }}>
        <div style={{ fontSize: 28, fontWeight: 700, color: upColor }}>
          {usd(s.capital)} → {usd(s.total_equity)}
        </div>
        <div style={{ fontSize: 18, color: upColor }}>
          {(s.return_pct ?? 0) >= 0 ? '+' : ''}{s.return_pct}%
        </div>
        <div style={dim}>since {s.inception?.slice(0, 10)} · {s.n_closed} closed</div>
      </div>

      {/* Verdict — both modes, front and center */}
      {sum && (
        <div style={{ ...box, borderColor: 'var(--accent)' }}>
          <div style={dim}>HONEST VERDICT</div>
          <div style={{ fontSize: 13, marginTop: 6 }}>{sum.verdict}</div>
          <div style={{ ...dim, marginTop: 6 }}>{sum.provenance}</div>
        </div>
      )}

      {/* Kill-switch + live paper stats — both modes */}
      <div style={{ display: 'flex', gap: 16, flexWrap: 'wrap' }}>
        <div style={{ ...box, flex: 1, minWidth: 200 }}>
          <div style={dim}>KILL-SWITCH</div>
          <div style={{ fontSize: 16, marginTop: 6,
                        color: s.tripped ? '#ef4444' : '#22c55e' }}>
            {s.tripped ? 'TRIPPED · FLAT' : `ARMED · ${s.buffer_to_trip}% buffer`}
          </div>
          <div style={{ ...dim, marginTop: 4 }}>
            drawdown {pct(s.breaker?.drawdown)} / trip at {pct(s.breaker?.threshold)}
          </div>
        </div>
        <div style={{ ...box, flex: 1, minWidth: 200 }}>
          <div style={dim}>LIVE PAPER-FORWARD</div>
          <div style={{ fontSize: 13, marginTop: 6 }}>
            Sharpe {s.realized?.sharpe?.toFixed(2)} · ret {pct(s.realized?.ret)} ·
            maxDD {pct(s.realized?.max_dd)} · n {s.realized?.n}
          </div>
        </div>
      </div>

      <div style={box}>
        <div style={dim}>OPEN POSITIONS</div>
        <div style={{ marginTop: 8 }}><PositionsTable positions={s.open_positions ?? []} /></div>
      </div>

      {/* Pro-only: equity curve + validation panel + ledger */}
      {mode === 'pro' && (
        <>
          <div style={box}>
            <div style={dim}>REALIZED (CLOSED) EQUITY · by trade #
              <span style={{ marginLeft: 8 }}>→ +open unrealized = {usd(s.total_equity)}</span>
            </div>
            <div style={{ marginTop: 8 }}><PaperEquityCurve points={s.equity_curve ?? []} /></div>
          </div>

          {sum && (
            <div style={box}>
              <div style={dim}>BACKTEST VALIDATION (static, out-of-sample)</div>
              <div style={{ fontSize: 13, marginTop: 6 }}>
                OOS return +{sum.oos_return_pct}% · Sharpe {sum.oos_sharpe} ·
                DSR {sum.dsr} ({sum.provable ? 'provable' : 'NOT provable, <0.5'}) ·
                IS→OOS corr +{sum.is_oos_corr}
              </div>
            </div>
          )}

          <div style={box}>
            <div style={dim}>CLOSED-TRADE LEDGER ({trades.data?.n ?? 0})</div>
            <div style={{ marginTop: 8, maxHeight: 320, overflow: 'auto' }}>
              <table style={{ width: '100%', fontSize: 12, borderCollapse: 'collapse' }}>
                <thead><tr style={dim}>
                  {['EXIT', 'SYMBOL', 'SLEEVE', 'DIR', 'PNL%'].map(h => (
                    <th key={h} style={{ textAlign: 'left', padding: '4px 8px' }}>{h}</th>))}
                </tr></thead>
                <tbody>
                  {(trades.data?.trades ?? []).slice().reverse().map((tr, i) => (
                    <tr key={i} style={{ borderTop: '1px solid var(--border)' }}>
                      <td style={{ padding: '4px 8px' }}>{tr.exit_time?.slice(0, 10)}</td>
                      <td style={{ padding: '4px 8px' }}>{tr.symbol}</td>
                      <td style={{ padding: '4px 8px' }}>{tr.sleeve}</td>
                      <td style={{ padding: '4px 8px' }}>{tr.direction}</td>
                      <td style={{ padding: '4px 8px',
                                   color: tr.pnl_pct >= 0 ? '#22c55e' : '#ef4444' }}>
                        {(tr.pnl_pct * 100).toFixed(2)}%</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </>
      )}
    </div>
  );
}
