import React from 'react';
import { k } from '../../styles/kiteUI';

/**
 * Five-level depth ladder plus the session statistics that sit beside it.
 *
 * Extracted from the order window so the signal board shows the same numbers
 * from the same code — a second ladder implementation would drift in formatting
 * and, worse, in which field it reads for a total.
 */
const num = (v: unknown) => Number(v ?? 0);
const px = (v: unknown) => (v != null && !isNaN(Number(v)) ? Number(v).toFixed(2) : '—');
const qty = (v: unknown) => (v == null ? '—' : Number(v).toLocaleString('en-IN'));

export interface KiteQuoteLike {
  depth?: { buy?: { price?: number; orders?: number; quantity?: number }[]; sell?: { price?: number; orders?: number; quantity?: number }[] };
  buy_quantity?: number;
  sell_quantity?: number;
  ohlc?: { open?: number; high?: number; low?: number; close?: number };
  volume?: number;
  average_price?: number;
  lower_circuit_limit?: number;
  upper_circuit_limit?: number;
  last_quantity?: number;
  last_trade_time?: string;
  oi?: number;
  last_price?: number;
}

export function DepthLadder({ quote, levels = 5 }: { quote?: KiteQuoteLike; levels?: number }) {
  const buy = quote?.depth?.buy ?? [];
  const sell = quote?.depth?.sell ?? [];
  const cell: React.CSSProperties = { flex: 1, textAlign: 'right', fontVariantNumeric: 'tabular-nums', padding: '3px 6px' };

  if (!buy.length && !sell.length) {
    return <div style={{ fontSize: 9.5, color: k.dim, padding: '6px 2px' }}>Depth unavailable — the broker returned no book for this contract.</div>;
  }

  return (
    <div style={{ border: `1px solid ${k.border}`, borderRadius: 4, overflow: 'hidden' }}>
      <div style={{ display: 'flex', fontSize: 8.5, color: k.dim, borderBottom: `1px solid ${k.border}`, background: k.surface, padding: '3px 0' }}>
        {['Bid', 'Orders', 'Qty', 'Offer', 'Orders', 'Qty'].map((h, i) => <span key={h + i} style={cell}>{h}</span>)}
      </div>
      {Array.from({ length: levels }).map((_, i) => {
        const b = buy[i] ?? {}; const s = sell[i] ?? {};
        return (
          <div key={i} style={{ display: 'flex', fontSize: 9.5, borderBottom: `1px solid ${k.surface}` }}>
            <span style={{ ...cell, color: k.blue, fontWeight: 500 }}>{px(b.price)}</span>
            <span style={{ ...cell, color: k.dim }}>{b.orders ?? '—'}</span>
            <span style={{ ...cell, color: k.text }}>{qty(b.quantity)}</span>
            <span style={{ ...cell, color: k.orange, fontWeight: 500 }}>{px(s.price)}</span>
            <span style={{ ...cell, color: k.dim }}>{s.orders ?? '—'}</span>
            <span style={{ ...cell, color: k.text }}>{qty(s.quantity)}</span>
          </div>
        );
      })}
      <div style={{ display: 'flex', fontSize: 9.5, fontWeight: 700, padding: '3px 0', background: k.surface }}>
        <span style={{ ...cell, textAlign: 'left', color: k.blue }}>Total</span>
        <span style={{ ...cell, color: k.blue }}>{num(quote?.buy_quantity).toLocaleString('en-IN')}</span>
        <span style={{ flex: 1 }} />
        <span style={{ ...cell, textAlign: 'left', color: k.orange }}>Total</span>
        <span style={{ ...cell, color: k.orange }}>{num(quote?.sell_quantity).toLocaleString('en-IN')}</span>
      </div>
    </div>
  );
}

/** Session statistics for a contract — the block Kite shows beneath the ladder. */
export function QuoteStats({ quote, extra }: { quote?: KiteQuoteLike; extra?: { label: string; value: string }[] }) {
  const o = quote?.ohlc ?? {};
  const items: { label: string; value: string }[] = [
    { label: 'Open', value: px(o.open) },
    { label: 'High', value: px(o.high) },
    { label: 'Low', value: px(o.low) },
    { label: 'Prev. close', value: px(o.close) },
    { label: 'Volume', value: qty(quote?.volume) },
    { label: 'Avg. price', value: px(quote?.average_price) },
    { label: 'Lower circuit', value: px(quote?.lower_circuit_limit) },
    { label: 'Upper circuit', value: px(quote?.upper_circuit_limit) },
    { label: 'LTQ', value: qty(quote?.last_quantity) },
    { label: 'LTT', value: quote?.last_trade_time ? String(quote.last_trade_time).replace('T', ' ').slice(0, 19) : '—' },
    { label: 'OI', value: qty(quote?.oi) },
    ...(extra ?? []),
  ];
  return (
    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(78px, 1fr))', gap: 4 }}>
      {items.map((it) => (
        <div key={it.label} style={{ border: `1px solid ${k.border}`, borderRadius: 3, padding: '4px 6px', background: k.bg, minWidth: 0 }}>
          <div style={{ fontSize: 8, color: k.dim, textTransform: 'uppercase', letterSpacing: '.03em', whiteSpace: 'nowrap' }}>{it.label}</div>
          <div style={{ fontSize: 10.5, fontWeight: 600, color: k.text, fontVariantNumeric: 'tabular-nums', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{it.value}</div>
        </div>
      ))}
    </div>
  );
}
