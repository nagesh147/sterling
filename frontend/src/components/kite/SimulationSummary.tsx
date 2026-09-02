import React, { useMemo } from 'react';
import { useSimulationStore } from '../../hooks/useSimulation';
import { k } from '../../styles/kiteUI';

/**
 * End-of-simulation summary modal.
 * Reads showSummary from the store; self-contained — no props needed.
 */
export function SimulationSummary() {
  const { status, date, startTime, endTime, showSummary, setShowSummary } = useSimulationStore();

  if (!showSummary) return null;

  const stats = status.stats;
  const onClose = () => setShowSummary(false);

  const winRate = stats.trades_entered > 0
    ? ((stats.wins / stats.trades_entered) * 100).toFixed(1)
    : '0.0';

  return (
    <div className="sim-summary-overlay" onClick={(e) => { if (e.target === e.currentTarget) onClose(); }}>
      <div className="sim-summary-card">
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 20 }}>
          <h2 style={{ fontSize: 16, fontWeight: 700, color: k.text, margin: 0 }}>Simulation Complete</h2>
          <span style={{ fontSize: 12, color: k.dim }}>{date} ({startTime} – {endTime})</span>
        </div>

        {/* Stats Grid */}
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 12, marginBottom: 24 }}>
          <StatBox label="Signals Fired" value={stats.signals_fired} />
          <StatBox label="Trades Entered" value={stats.trades_entered} />
          <StatBox label="Win Rate" value={`${winRate}%`} color={stats.wins > stats.losses ? k.green : k.text} />
          <StatBox label="Wins" value={stats.wins} color={k.green} />
          <StatBox label="Losses" value={stats.losses} color={k.red} />
          <StatBox
            label="Total P&L"
            value={`${stats.pnl > 0 ? '+' : ''}${stats.pnl.toFixed(2)}`}
            color={stats.pnl > 0 ? k.green : stats.pnl < 0 ? k.red : k.text}
          />
        </div>

        {/* Cumulative Equity Curve Sparkline */}
        <EquityCurveSparkline trades={stats.trades || []} />

        {/* Strategy Breakdown */}
        <StrategyTable events={stats.events} trades={stats.trades || []} />

        {/* Executed Trades Table */}
        <ExecutedTradesTable trades={stats.trades || []} />

        {/* Action Buttons */}
        <div style={{ display: 'flex', gap: 10, justifyContent: 'flex-end', flexWrap: 'wrap' }}>
          {stats.events.length > 0 && (
            <button
              onClick={() => exportSignalsToCSV(stats.events, date)}
              style={{
                padding: '8px 14px', background: `color-mix(in srgb, ${k.green} 15%, transparent)`,
                border: `1px solid color-mix(in srgb, ${k.green} 30%, transparent)`,
                borderRadius: 6, color: k.green, fontSize: 11, fontWeight: 600, cursor: 'pointer',
              }}
            >
              📥 Export Signals CSV
            </button>
          )}
          {(stats.trades || []).length > 0 && (
            <button
              onClick={() => exportTradesToCSV(stats.trades || [], date)}
              style={{
                padding: '8px 14px', background: `color-mix(in srgb, ${k.cyan} 15%, transparent)`,
                border: `1px solid color-mix(in srgb, ${k.cyan} 30%, transparent)`,
                borderRadius: 6, color: k.cyan, fontSize: 11, fontWeight: 600, cursor: 'pointer',
              }}
            >
              📥 Export Trades CSV
            </button>
          )}
          <button
            onClick={onClose}
            style={{
              padding: '8px 14px', background: 'transparent', border: `1px solid ${k.border}`,
              borderRadius: 6, color: k.text, fontSize: 11, fontWeight: 600, cursor: 'pointer',
            }}
          >
            Close
          </button>
          <button
            onClick={() => { onClose(); useSimulationStore.getState().setBarOpen(true); }}
            style={{
              padding: '8px 14px', background: `color-mix(in srgb, ${k.cyan} 15%, transparent)`,
              border: `1px solid color-mix(in srgb, ${k.cyan} 30%, transparent)`,
              borderRadius: 6, color: k.cyan, fontSize: 11, fontWeight: 600, cursor: 'pointer',
            }}
          >
            Replay Again
          </button>
        </div>
      </div>
    </div>
  );
}

function exportTradesToCSV(trades: any[], date: string) {
  if (!trades || trades.length === 0) return;
  const headers = ['Trade ID', 'Entry Time', 'Exit Time', 'Strategy', 'Symbol', 'Underlying', 'Direction', 'Option Type', 'Strike', 'Lots', 'Quantity', 'Entry Price', 'Exit Price', 'Status', 'PnL (INR)', 'PnL (%)', 'Duration (Mins)'];
  const rows = trades.map(tr => [
    tr.trade_id,
    tr.entry_time_iso,
    tr.exit_time_iso,
    (tr.strategy || '').toUpperCase(),
    tr.symbol,
    tr.underlying,
    tr.direction,
    tr.opt_type,
    tr.strike,
    tr.lots,
    tr.quantity,
    tr.entry_price,
    tr.exit_price || '',
    tr.status,
    tr.pnl_usd,
    tr.pnl_pct,
    tr.duration_mins,
  ]);
  const csvContent = [headers.join(','), ...rows.map(r => r.join(','))].join('\n');
  const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = `sterling_replay_trades_${date}.csv`;
  a.click();
  URL.revokeObjectURL(url);
}

function exportSignalsToCSV(events: any[], date: string) {
  if (!events || events.length === 0) return;
  const headers = ['Time', 'Strategy', 'Instrument', 'Direction', 'Strength', 'Entry Price', 'Stop Loss', 'Target Price'];
  const rows = events.map(ev => [
    ev.time_iso,
    (ev.strategy || '').toUpperCase(),
    ev.instrument,
    ev.direction,
    ev.strength,
    ev.entry,
    ev.stop,
    ev.target,
  ]);
  const csvContent = [headers.join(','), ...rows.map(r => r.join(','))].join('\n');
  const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = `sterling_replay_signals_${date}.csv`;
  a.click();
  URL.revokeObjectURL(url);
}

function StrategyTable({ events, trades }: { events: any[]; trades: any[] }) {
  const breakdown = useMemo(() => {
    const map = new Map<string, { count: number; wins: number; losses: number; pnl: number }>();
    
    (events || []).forEach(ev => {
      const s = map.get(ev.strategy) || { count: 0, wins: 0, losses: 0, pnl: 0 };
      s.count++;
      map.set(ev.strategy, s);
    });

    (trades || []).forEach(tr => {
      const s = map.get(tr.strategy) || { count: 0, wins: 0, losses: 0, pnl: 0 };
      if (tr.status === 'WIN') s.wins++;
      else if (tr.status === 'LOSS') s.losses++;
      s.pnl += (tr.pnl_usd || 0);
      map.set(tr.strategy, s);
    });

    return Array.from(map.entries()).map(([name, data]) => ({ name, ...data }));
  }, [events, trades]);

  return (
    <>
      <h3 style={{ fontSize: 12, color: k.dim, textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: 12, fontWeight: 600 }}>Strategy Breakdown</h3>
      <table style={{ width: '100%', fontSize: 11, textAlign: 'left', borderCollapse: 'collapse', marginBottom: 24 }}>
        <thead>
          <tr style={{ borderBottom: `1px solid ${k.border}`, color: k.dim }}>
            <th style={{ padding: '6px 0', fontWeight: 500 }}>Strategy</th>
            <th style={{ padding: '6px 0', fontWeight: 500 }}>Signals</th>
            <th style={{ padding: '6px 0', fontWeight: 500 }}>Wins</th>
            <th style={{ padding: '6px 0', fontWeight: 500 }}>Losses</th>
            <th style={{ padding: '6px 0', fontWeight: 500, textAlign: 'right' }}>Realized P&L</th>
          </tr>
        </thead>
        <tbody>
          {breakdown.map(s => (
            <tr key={s.name} style={{ borderBottom: `1px solid ${k.border}` }}>
              <td style={{ padding: '8px 0', color: k.text, fontWeight: 600 }}>[{s.name.toUpperCase()}]</td>
              <td style={{ padding: '8px 0', color: k.text }}>{s.count}</td>
              <td style={{ padding: '8px 0', color: k.green, fontWeight: 600 }}>{s.wins}</td>
              <td style={{ padding: '8px 0', color: k.red, fontWeight: 600 }}>{s.losses}</td>
              <td style={{ padding: '8px 0', textAlign: 'right', fontWeight: 700, color: s.pnl >= 0 ? k.green : k.red }}>
                {s.pnl >= 0 ? '+' : ''}₹{s.pnl.toFixed(2)}
              </td>
            </tr>
          ))}
          {breakdown.length === 0 && (
            <tr><td colSpan={5} style={{ padding: '12px 0', color: k.dim, textAlign: 'center' }}>No strategies triggered</td></tr>
          )}
        </tbody>
      </table>
    </>
  );
}

function StatBox({ label, value, color = k.text }: { label: string; value: string | number; color?: string }) {
  return (
    <div style={{ background: k.surface, padding: '12px', borderRadius: 8, border: `1px solid ${k.border}` }}>
      <div style={{ fontSize: 10, color: k.dim, textTransform: 'uppercase', letterSpacing: '0.04em', marginBottom: 4 }}>{label}</div>
      <div style={{ fontSize: 18, fontWeight: 700, color }}>{value}</div>
    </div>
  );
}

function EquityCurveSparkline({ trades }: { trades: any[] }) {
  const equityPoints = useMemo(() => {
    let pnl = 0;
    const points = [0];
    (trades || []).forEach(tr => {
      pnl += (tr.pnl_usd || 0);
      points.push(pnl);
    });
    return points;
  }, [trades]);

  if (equityPoints.length < 2) return null;

  const min = Math.min(...equityPoints);
  const max = Math.max(...equityPoints);
  const range = max - min || 1;
  const width = 430;
  const height = 44;

  const pointsSvg = equityPoints.map((pt, i) => {
    const x = (i / (equityPoints.length - 1)) * width;
    const y = height - ((pt - min) / range) * (height - 8) - 4;
    return `${x},${y}`;
  }).join(' ');

  const isPositive = equityPoints[equityPoints.length - 1] >= 0;
  const color = isPositive ? k.green : k.red;

  return (
    <div style={{ marginBottom: 20 }}>
      <div style={{ fontSize: 10, color: k.dim, textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: 6, fontWeight: 600 }}>Equity Curve Sparkline (Realized P&L ₹)</div>
      <div style={{ background: k.surface, padding: '8px 12px', borderRadius: 8, border: `1px solid ${k.border}` }}>
        <svg width="100%" height={height} viewBox={`0 0 ${width} ${height}`} preserveAspectRatio="none">
          <polyline fill="none" stroke={color} strokeWidth="2" points={pointsSvg} strokeLinecap="round" strokeLinejoin="round" />
        </svg>
      </div>
    </div>
  );
}

function ExecutedTradesTable({ trades }: { trades: any[] }) {
  if (!trades || trades.length === 0) return null;

  return (
    <>
      <h3 style={{ fontSize: 12, color: k.dim, textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: 12, fontWeight: 600 }}>Executed Trades Log</h3>
      <div style={{ maxHeight: 180, overflowY: 'auto', marginBottom: 24, borderRadius: 6, border: `1px solid ${k.border}` }}>
        <table style={{ width: '100%', fontSize: 11, textAlign: 'left', borderCollapse: 'collapse' }}>
          <thead>
            <tr style={{ borderBottom: `1px solid ${k.border}`, color: k.dim, position: 'sticky', top: 0, background: k.surface }}>
              <th style={{ padding: '6px 8px', fontWeight: 500 }}>ID</th>
              <th style={{ padding: '6px 8px', fontWeight: 500 }}>Time</th>
              <th style={{ padding: '6px 8px', fontWeight: 500 }}>Strategy</th>
              <th style={{ padding: '6px 8px', fontWeight: 500 }}>Symbol</th>
              <th style={{ padding: '6px 8px', fontWeight: 500 }}>Lots</th>
              <th style={{ padding: '6px 8px', fontWeight: 500 }}>Entry</th>
              <th style={{ padding: '6px 8px', fontWeight: 500 }}>Exit</th>
              <th style={{ padding: '6px 8px', fontWeight: 500 }}>Status</th>
              <th style={{ padding: '6px 8px', fontWeight: 500, textAlign: 'right' }}>Realized P&L</th>
            </tr>
          </thead>
          <tbody>
            {trades.map(tr => {
              const isWin = tr.status === 'WIN';
              return (
                <tr key={tr.trade_id} style={{ borderBottom: `1px solid color-mix(in srgb, ${k.text} 6%, transparent)` }}>
                  <td style={{ padding: '6px 8px', fontFamily: 'monospace', color: k.cyan, fontWeight: 600 }}>{tr.trade_id}</td>
                  <td style={{ padding: '6px 8px', color: k.dim }}>{tr.entry_time_iso}</td>
                  <td style={{ padding: '6px 8px', color: k.text, fontWeight: 600 }}>[{tr.strategy.toUpperCase()}]</td>
                  <td style={{ padding: '6px 8px', color: k.text, fontWeight: 600 }}>{tr.symbol}</td>
                  <td style={{ padding: '6px 8px', color: k.dim }}>{tr.lots}L</td>
                  <td style={{ padding: '6px 8px', color: k.text }}>₹{tr.entry_price}</td>
                  <td style={{ padding: '6px 8px', color: k.text }}>{tr.exit_price ? `₹${tr.exit_price}` : '--'}</td>
                  <td style={{ padding: '6px 8px' }}>
                    <span style={{
                      padding: '2px 6px', borderRadius: 4, fontSize: 9, fontWeight: 700,
                      background: isWin ? `color-mix(in srgb, ${k.green} 15%, transparent)` : `color-mix(in srgb, ${k.red} 15%, transparent)`,
                      color: isWin ? k.green : k.red,
                    }}>
                      {tr.status}
                    </span>
                  </td>
                  <td style={{ padding: '6px 8px', textAlign: 'right', fontWeight: 700, color: tr.pnl_usd >= 0 ? k.green : k.red }}>
                    {tr.pnl_usd >= 0 ? '+' : ''}₹{tr.pnl_usd.toFixed(2)}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </>
  );
}
