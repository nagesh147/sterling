import React from 'react';
import { useOrbSignals } from '../hooks/useOrbSignals';

const cell: React.CSSProperties = { padding: '8px 9px', borderBottom: '1px solid var(--t-border)', fontSize: 10, whiteSpace: 'nowrap' };

/** Counts of the gate that stopped each non-signal, strongest reason first. */
function blockedByGate(rows: { state: string; reason: string | null }[]) {
  const counts = new Map<string, number>();
  for (const row of rows) {
    if (row.state === 'SIGNAL' || !row.reason) continue;
    counts.set(row.reason, (counts.get(row.reason) ?? 0) + 1);
  }
  return [...counts.entries()].sort((a, b) => b[1] - a[1]);
}

export function NiftyOrbSignalsTable() {
  const { signals: rows, isLoading, error } = useOrbSignals(true);
  const gates = blockedByGate(rows);
  const live = rows.filter(r => r.state === 'SIGNAL').length;
  if (isLoading) return <div style={{ padding: 12, color: 'var(--t-dim)', fontSize: 10 }}>Scanning ORB universe…</div>;
  if (error) return <div style={{ padding: 12, color: 'var(--t-red)', fontSize: 10 }}>ORB signal feed unavailable: {(error as Error).message}</div>;
  return (
    <div style={{ width: '100%', overflowX: 'auto', border: '1px solid var(--t-border)', borderRadius: 6, background: 'var(--t-bg)' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '9px 11px', borderBottom: '1px solid var(--t-border)' }}>
        <div style={{ fontSize: 10, fontWeight: 600, letterSpacing: '0.1em', color: 'var(--t-bright)' }}>ORB SIGNALS</div>
        <div style={{ fontSize: 9, color: 'var(--t-dim)' }}>
          {live} actionable · {rows.length} scanned
        </div>
      </div>
      {!!gates.length && (
        // Which filter is holding the universe back, rather than a bare
        // "no signals". The engine names the first unmet gate per candidate.
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6, padding: '8px 11px', borderBottom: '1px solid var(--t-border)' }}>
          {gates.map(([reason, count]) => (
            <span key={reason} style={{ fontSize: 9, color: 'var(--t-dim)', border: '1px solid var(--t-border)', borderRadius: 4, padding: '2px 6px' }}>
              {reason} <span style={{ color: 'var(--t-bright)' }}>{count}</span>
            </span>
          ))}
        </div>
      )}
      <table style={{ width: '100%', borderCollapse: 'collapse', fontFamily: 'monospace' }}>
        <thead><tr>{['Instrument', 'State', 'Direction', 'Spot', 'ORB', 'VWAP', 'Vol', 'Option', 'Strike', 'Expiry', 'Entry', 'SL', 'Target', 'Qty', 'Stop Risk', 'Max Loss', 'Quote Age', 'Data', 'Why'].map(x => <th key={x} style={{ ...cell, textAlign: 'left', color: 'var(--t-dim)', fontWeight: 500 }}>{x}</th>)}</tr></thead>
        <tbody>{rows.map(row => (
          <tr key={row.id}>
            <td style={{ ...cell, color: 'var(--t-bright)', fontWeight: 600 }}>{row.underlying}</td>
            <td style={{ ...cell, color: row.state === 'SIGNAL' ? 'var(--t-green)' : row.state === 'ERROR' || row.state === 'REJECTED' ? 'var(--t-red)' : 'var(--t-dim)' }}>{row.state}</td>
            <td style={{ ...cell, color: row.direction === 'long' ? 'var(--t-green)' : row.direction === 'short' ? 'var(--t-red)' : 'var(--t-dim)', fontWeight: 600 }}>{row.direction?.toUpperCase() || '—'}</td>
            <td style={{ ...cell, textAlign: 'right' }}>{row.spot?.toFixed(2) || '—'}</td>
            <td style={{ ...cell, textAlign: 'right' }}>{row.orbHigh == null ? '—' : `${row.orbHigh.toFixed(2)}/${row.orbLow?.toFixed(2) ?? '—'}`}</td>
            <td style={{ ...cell, textAlign: 'right' }}>{row.vwap?.toFixed(2) || '—'}</td>
            <td style={{ ...cell, textAlign: 'right' }}>{row.volumeRatio == null ? '—' : `${row.volumeRatio.toFixed(2)}x`}</td>
            <td style={{ ...cell, color: row.optionType === 'CE' ? 'var(--t-green)' : row.optionType === 'PE' ? 'var(--t-red)' : 'var(--t-dim)', fontWeight: 600 }}>{row.optionSymbol || '—'}</td>
            <td style={{ ...cell, textAlign: 'right' }}>{row.optionStrike ?? '—'}</td>
            <td style={cell}>{row.optionExpiry || '—'}</td>
            <td style={{ ...cell, textAlign: 'right' }}>{row.optionPremium?.toFixed(2) || '—'}</td>
            <td style={{ ...cell, textAlign: 'right' }}>{row.stopPremium?.toFixed(2) || '—'}</td>
            <td style={{ ...cell, textAlign: 'right' }}>{row.targetPremium?.toFixed(2) || '—'}</td>
            <td style={{ ...cell, textAlign: 'right' }}>{row.quantity ?? '—'}</td>
            <td style={{ ...cell, textAlign: 'right' }}>{row.riskInr == null ? '—' : `₹${row.riskInr.toFixed(0)}`}</td>
            {/* Full premium outlay: what this position loses if the option expires
                worthless. "Stop Risk" alone understated a plan by up to 16x. */}
            <td style={{ ...cell, textAlign: 'right', color: 'var(--t-bright)', fontWeight: 600 }}>
              {row.maxLossInr == null ? '—' : `₹${row.maxLossInr.toFixed(0)}`}
              {row.deltaIsEstimated && (
                /* Kite publishes no Greeks, so delta 0.50 is assumed and every
                   premium-domain number here -- including the stop armed at the
                   broker -- rests on that assumption. */
                <span title="Delta assumed 0.50: broker publishes no Greeks" style={{ marginLeft: 4, color: 'var(--t-orange, #f06428)' }}>≈</span>
              )}
            </td>
            {/* A stale quote is the most common reason a plan is unexecutable. */}
            <td style={{ ...cell, textAlign: 'right', color: row.quoteAgeS != null && row.quoteAgeS > 15 ? 'var(--t-red)' : 'var(--t-dim)' }}>
              {row.quoteAgeS == null ? '—' : `${row.quoteAgeS.toFixed(1)}s`}
            </td>
            <td style={cell}>{row.dataSource || '—'}</td>
            <td style={{ ...cell, whiteSpace: 'normal', minWidth: 190, color: 'var(--t-dim)' }}>{row.reason || '—'}</td>
          </tr>
        ))}</tbody>
      </table>
      {!rows.length && <div style={{ padding: 16, color: 'var(--t-dim)', fontSize: 10 }}>No configured underlyings are producing ORB signals.</div>}
    </div>
  );
}

export default NiftyOrbSignalsTable;
