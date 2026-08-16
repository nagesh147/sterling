import React from 'react';
import type { AdaptiveEdgeSession, AdaptiveEdgeSignal } from '../../types/adaptiveEdge';
import type { AdaptiveEdgeRow } from './AdaptiveEdgePanel';
import { fmt } from './AdaptiveEdgePanel';

const C = { text: '#444', muted: '#9b9b9b', border: '#ededed' };

function chip(text: string, key: string) {
  return (
    <span
      key={key}
      style={{
        display: 'inline-flex',
        alignItems: 'center',
        gap: 4,
        padding: '3px 8px',
        border: `1px solid ${C.border}`,
        borderRadius: 99,
        fontSize: 11,
        color: C.text,
        background: '#fff',
      }}
    >
      {text}
    </span>
  );
}

export function AdaptiveEdgeMetricsStrip({
  session,
  watched,
  selectedRow,
  activeSymbol,
  taken,
  skipped,
}: {
  session?: AdaptiveEdgeSession;
  watched: AdaptiveEdgeSignal[];
  selectedRow?: AdaptiveEdgeRow;
  activeSymbol?: string;
  taken: number;
  skipped: number;
}) {
  const sym = activeSymbol || selectedRow?.underlying || selectedRow?.instrument || 'NIFTY 50';
  const symNorm = sym.toUpperCase();
  const isNifty = (symNorm.includes('NIFTY') && !symNorm.includes('BANK') && !symNorm.includes('FIN')) || symNorm === 'NIFTY-I';
  const isBankNifty = symNorm.includes('BANK');
  const isFinNifty = symNorm.includes('FIN');
  const isSensex = symNorm.includes('SENSEX');

  const spot = selectedRow?.spotEntry ?? (
    isSensex ? 78100 :
    isBankNifty ? 51200 :
    isFinNifty ? 23450 :
    isNifty ? (session?.last_poc ? 24405 : 24405) :
    2500
  );

  const poc = selectedRow?.poc ?? (
    isNifty ? (session?.last_poc ?? 24405) :
    Math.round(spot * 0.9992)
  );

  const vwap = selectedRow?.vwap ?? (
    isNifty ? (session?.last_vwap ?? 24409.84) :
    Number((spot * 1.0004).toFixed(2))
  );

  const cvd = selectedRow?.cvd ?? (
    isNifty ? (session?.last_cvd ?? 32055) :
    ((selectedRow?.optionType === 'PE') ? -Math.round(spot * 0.42) : Math.round(spot * 0.42))
  );

  const symLabel = isSensex ? 'SENSEX' : isBankNifty ? 'BANKNIFTY' : isFinNifty ? 'FINNIFTY' : isNifty ? 'NIFTY' : sym;

  const items: React.ReactNode[] = [];
  if (poc != null) items.push(chip(`${symLabel} POC ${fmt(poc, 0)}`, 'poc'));
  if (vwap != null) items.push(chip(`${symLabel} VWAP ${fmt(vwap)}`, 'vwap'));
  if (cvd != null) items.push(chip(`${symLabel} CVD ${cvd > 0 ? '+' : ''}${fmt(cvd, 0)}`, 'cvd'));
  if (session?.profit_giveback != null) items.push(chip(`Giveback ${fmt(session.profit_giveback)}`, 'gb'));
  items.push(chip(`${taken} taken`, 'taken'));
  if (skipped) items.push(chip(`${skipped.toLocaleString('en-IN')} skipped`, 'skip'));
  watched.forEach((item) => {
    const uUpper = item.underlying.toUpperCase();
    const isStockGroup = uUpper.includes('STOCK') || uUpper.includes('F&O');
    const label = isStockGroup ? 'F&O Stocks · Spot & DTE Shield' : `${item.underlying} · ${item.skip_reason ?? 'Spot Scan'}`;
    items.push(chip(label, item.id));
  });
  if (!items.length) return null;
  return (
    <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6, marginTop: 10 }}>
      {items}
    </div>
  );
}
