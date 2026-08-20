import React from 'react';
import { useOrbSignals } from '../hooks/useOrbSignals';

const cell: React.CSSProperties = { padding: '8px 9px', borderBottom: '1px solid var(--t-border)', fontSize: 10, whiteSpace: 'nowrap' };

export function NiftyOrbSignalsTable() {
  const { signals: rows, isLoading, error } = useOrbSignals(true);
  if (isLoading) return <div style={{ padding: 12, color: 'var(--t-dim)', fontSize: 10 }}>Scanning ORB universe…</div>;
  if (error) return <div style={{ padding: 12, color: 'var(--t-red)', fontSize: 10 }}>ORB signal feed unavailable: {(error as Error).message}</div>;
  return (
    <div style={{ width: '100%', overflowX: 'auto', border: '1px solid var(--t-border)', borderRadius: 6, background: 'var(--t-bg)' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '9px 11px', borderBottom: '1px solid var(--t-border)' }}>
        <div style={{ fontSize: 10, fontWeight: 600, letterSpacing: '0.1em', color: 'var(--t-bright)' }}>ORB SIGNALS</div>
        <div style={{ fontSize: 9, color: 'var(--t-dim)' }}>{rows.length} feed rows</div>
      </div>
      <table style={{ width: '100%', borderCollapse: 'collapse', fontFamily: 'monospace' }}>
        <thead><tr>{['Instrument', 'State', 'Direction', 'Spot', 'ORB', 'VWAP', 'Vol', 'Option', 'Strike', 'Expiry', 'Entry', 'SL', 'Target', 'Qty', 'Stop Risk', 'Max Loss', 'Data'].map(x => <th key={x} style={{ ...cell, textAlign: 'left', color: 'var(--t-dim)', fontWeight: 500 }}>{x}</th>)}</tr></thead>
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
            <td style={{ ...cell, textAlign: 'right', color: 'var(--t-bright)', fontWeight: 600 }}>{row.maxLossInr == null ? '—' : `₹${row.maxLossInr.toFixed(0)}`}</td>
            <td style={cell}>{row.dataSource || '—'}</td>
          </tr>
        ))}</tbody>
      </table>
      {!rows.length && <div style={{ padding: 16, color: 'var(--t-dim)', fontSize: 10 }}>No configured underlyings are producing ORB signals.</div>}
    </div>
  );
}

export default NiftyOrbSignalsTable;
