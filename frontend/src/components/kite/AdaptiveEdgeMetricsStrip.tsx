import React from 'react';
import type { AdaptiveEdgeSession, AdaptiveEdgeSignal } from '../../types/adaptiveEdge';
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
  taken,
  skipped,
}: {
  session?: AdaptiveEdgeSession;
  watched: AdaptiveEdgeSignal[];
  taken: number;
  skipped: number;
}) {
  const items: React.ReactNode[] = [];
  if (session?.last_poc != null) items.push(chip(`POC ${fmt(session.last_poc, 0)}`, 'poc'));
  if (session?.last_vwap != null) items.push(chip(`VWAP ${fmt(session.last_vwap)}`, 'vwap'));
  if (session?.last_cvd != null) items.push(chip(`CVD ${fmt(session.last_cvd, 0)}`, 'cvd'));
  if (session?.profit_giveback != null) items.push(chip(`giveback ${fmt(session.profit_giveback)}`, 'gb'));
  items.push(chip(`${taken} taken`, 'taken'));
  if (skipped) items.push(chip(`${skipped.toLocaleString('en-IN')} skipped`, 'skip'));
  watched.forEach((item) => {
    items.push(chip(`${item.underlying} · ${item.skip_reason ?? 'no tape'}`, item.id));
  });
  if (!items.length) return null;
  return (
    <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6, marginTop: 10 }}>
      {items}
    </div>
  );
}
