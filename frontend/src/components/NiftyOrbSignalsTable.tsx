import React from 'react';
import { useOrbSignals } from '../hooks/useOrbSignals';
import { KiteActionButtons } from './kite/KiteActionButtons';
import { useOrderWindowStore } from '../store/useOrderWindowStore';

import { parseInstrument } from './kite/InstrumentLabel';

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

export function NiftyOrbSignalsTable({ onOpenChart }: { onOpenChart?: (quoteKey: string) => void } = {}) {
  const openOrderWindow = useOrderWindowStore((s) => s.openOrderWindow);
  const { signals: rows, isLoading, error } = useOrbSignals(true);
  const gates = blockedByGate(rows);
  const live = rows.filter(r => r.state === 'SIGNAL').length;
  if (isLoading) return <div style={{ padding: 12, color: 'var(--t-dim)', fontSize: 10 }}>Scanning ORB universe…</div>;
  if (error) return <div style={{ padding: 12, color: 'var(--t-red)', fontSize: 10 }}>ORB signal feed unavailable: {(error as Error).message}</div>;

  const isWeeklyRow = (symbol?: string | null) => {
    if (!symbol) return false;
    const parsed = parseInstrument(symbol);
    return parsed?.isWeekly ?? false;
  };

  const weeklyRows = rows.filter(r => isWeeklyRow(r.optionSymbol || r.underlying));
  const monthlyRows = rows.filter(r => !isWeeklyRow(r.optionSymbol || r.underlying));
  const hasBothSeries = weeklyRows.length > 0 && monthlyRows.length > 0;

  const renderRow = (row: typeof rows[0]) => (
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
      <td style={{ ...cell, textAlign: 'right', color: 'var(--t-bright)', fontWeight: 600 }}>
        {row.maxLossInr == null ? '—' : `₹${row.maxLossInr.toFixed(0)}`}
        {row.deltaSource === 'assumed' && (
          <span title="Delta assumed 0.50 — the premium could not be solved for volatility" style={{ marginLeft: 4, color: 'var(--t-orange, var(--k-brand))' }}>≈</span>
        )}
      </td>
      <td style={{ ...cell, textAlign: 'right', color: row.quoteAgeS != null && row.quoteAgeS > 15 ? 'var(--t-red)' : 'var(--t-dim)' }}>
        {row.quoteAgeS == null ? '—' : `${row.quoteAgeS.toFixed(1)}s`}
      </td>
      <td style={cell}>{row.dataSource || '—'}</td>
      <td style={{ ...cell, whiteSpace: 'normal', minWidth: 190, color: 'var(--t-dim)' }}>{row.reason || '—'}</td>
      <td style={{ ...cell, textAlign: 'right' }}>
        <KiteActionButtons
          onBuy={() => openOrderWindow({
            symbol: row.optionSymbol || row.underlying,
            exchange: 'NFO',
            initialSide: 'BUY',
            lotSize: row.quantity || 1,
            lastPrice: row.optionPremium || row.spot || 0,
            tag: 'ORB',
          })}
          onSell={() => openOrderWindow({
            symbol: row.optionSymbol || row.underlying,
            exchange: 'NFO',
            initialSide: 'SELL',
            lotSize: row.quantity || 1,
            lastPrice: row.optionPremium || row.spot || 0,
            tag: 'ORB',
          })}
        />
      </td>
      <td style={{ ...cell, textAlign: 'right' }}>
        <KiteActionButtons
          onChart={() => onOpenChart?.(`NFO:${row.optionSymbol || row.underlying}`)}
        />
      </td>
    </tr>
  );

  return (
    <div style={{ width: '100%', overflowX: 'auto', border: '1px solid var(--t-border)', borderRadius: 6, background: 'var(--t-bg)' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '9px 11px', borderBottom: '1px solid var(--t-border)' }}>
        <div style={{ fontSize: 10, fontWeight: 600, letterSpacing: '0.1em', color: 'var(--t-bright)' }}>ORB SIGNALS</div>
        <div style={{ fontSize: 9, color: 'var(--t-dim)' }}>
          {live} actionable · {rows.length} scanned
        </div>
      </div>
      {!!gates.length && (
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6, padding: '8px 11px', borderBottom: '1px solid var(--t-border)' }}>
          {gates.map(([reason, count]) => (
            <span key={reason} style={{ fontSize: 9, color: 'var(--t-dim)', border: '1px solid var(--t-border)', borderRadius: 4, padding: '2px 6px' }}>
              {reason} <span style={{ color: 'var(--t-bright)' }}>{count}</span>
            </span>
          ))}
        </div>
      )}
      <table style={{ width: '100%', borderCollapse: 'collapse', fontFamily: 'monospace' }}>
        <thead><tr>{['Instrument', 'State', 'Direction', 'Spot', 'ORB', 'VWAP', 'Vol', 'Option', 'Strike', 'Expiry', 'Entry', 'SL', 'Target', 'Qty', 'Stop Risk', 'Max Loss', 'Quote Age', 'Data', 'Why', 'Trade', 'Chart'].map(x => <th key={x} style={{ ...cell, textAlign: 'left', color: 'var(--t-dim)', fontWeight: 500 }}>{x}</th>)}</tr></thead>
        <tbody>
          {!hasBothSeries ? (
            rows.map(renderRow)
          ) : (
            <React.Fragment>
              {weeklyRows.map(renderRow)}
              <tr key="weekly-monthly-spacer" style={{ height: 10 }}>
                <td colSpan={21} style={{ background: 'transparent', borderTop: '1px solid var(--t-border)', padding: 0 }} />
              </tr>
              {monthlyRows.map(renderRow)}
            </React.Fragment>
          )}
        </tbody>
      </table>
      {!rows.length && <div style={{ padding: 16, color: 'var(--t-dim)', fontSize: 10 }}>No configured underlyings are producing ORB signals.</div>}
    </div>
  );
}

export default NiftyOrbSignalsTable;
