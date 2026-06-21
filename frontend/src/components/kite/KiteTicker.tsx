import React, { useEffect, useLayoutEffect, useRef, useState } from 'react';
import { useKiteWatchlist, useKiteQuote } from '../../hooks/useKite';
import { InstrumentLabel } from './InstrumentLabel';
import { k } from '../../styles/kiteUI';

// Use the single app-wide Kite font (Inter stack) so tiles match the rest of the UI.
const TILE_FONT = k.fontFamily;

const UP = '#10B981';
const DOWN = '#EF4444';
const SPARK = '#4184f3';

// Per-symbol intraday tick buffer, kept module-level so it accumulates across
// re-renders/remounts (like the price-flash prevRef). Seeded from the day's open
// so a sparkline has shape on the very first paint, then grows with each poll —
// no per-tile history request, so large watchlists stay on the single quote poll.
const HIST = new Map<string, number[]>();
const HIST_CAP = 48;

function pushHist(sym: string, seed: number | undefined, px: number | undefined): number[] {
  let arr = HIST.get(sym);
  if (!arr) {
    arr = seed != null && seed > 0 ? [seed] : [];
    HIST.set(sym, arr);
  }
  if (px != null && px > 0 && (arr.length === 0 || arr[arr.length - 1] !== px)) {
    arr.push(px);
    if (arr.length > HIST_CAP) arr.shift();
  }
  return arr;
}

function Sparkline({ points, color, width = 187, height = 34 }: {
  points: number[]; color: string; width?: number; height?: number;
}) {
  if (!points || points.length < 2) return <div style={{ height, marginTop: 8 }} />;
  const min = Math.min(...points);
  const max = Math.max(...points);
  const range = max - min || 1;
  const pad = 3;
  const h = height - pad * 2;
  const stepX = width / (points.length - 1);
  const d = points
    .map((p, i) => `${(i * stepX).toFixed(1)},${(pad + h - ((p - min) / range) * h).toFixed(1)}`)
    .join(' ');
  return (
    <svg width={width} height={height} style={{ display: 'block', marginTop: 8, overflow: 'visible' }}>
      <polyline points={d} fill="none" stroke={color} strokeWidth={1.6} strokeLinejoin="round" strokeLinecap="round" />
    </svg>
  );
}

function KiteCard({ sym, q }: { sym: string; q: any }) {
  const flashRef = useRef<HTMLSpanElement>(null);
  const prevRef = useRef<number | null>(null);

  const last: number | undefined = q?.last_price;
  const close: number | undefined = q?.ohlc?.close;
  const open: number | undefined = q?.ohlc?.open;
  const hasPrice = last != null && last > 0;

  let abs: number | null = null;
  let pct: number | null = null;
  if (hasPrice && close && close > 0) {
    abs = last! - close;
    pct = (abs / close) * 100;
  } else if (q?.net_change != null) {
    abs = q.net_change;
  }
  const up = (abs ?? 0) >= 0;
  const chgColor = abs == null ? 'var(--t-dim)' : up ? UP : DOWN;

  const series = pushHist(sym, close ?? open, last);

  useEffect(() => {
    const prev = prevRef.current;
    if (flashRef.current && hasPrice && prev != null && last !== prev) {
      const cls = last! > prev ? 'price-flash-up' : 'price-flash-down';
      flashRef.current.classList.remove('price-flash-up', 'price-flash-down');
      void flashRef.current.offsetWidth;
      flashRef.current.classList.add(cls);
    }
    if (hasPrice) prevRef.current = last!;
  }, [last, hasPrice]);

  const segments = sym.split(':');
  const exch = segments[0] || '';
  const rawTs = segments.slice(1).join(':') || sym;

  const priceStr = hasPrice
    ? last!.toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
    : '—';
  const absStr = abs != null ? `${abs >= 0 ? '+' : ''}${abs.toFixed(2)}` : '';
  const pctStr = pct != null ? `${pct >= 0 ? '+' : ''}${pct.toFixed(2)}%` : '';

  return (
    <div style={{
      display: 'flex', flexDirection: 'column',
      background: 'var(--t-bg3)', border: '1px solid var(--t-border)',
      borderRadius: 8, padding: '12px 14px', width: 215, flexShrink: 0,
    }}>
      <span style={{
        fontSize: 12, fontWeight: 700, color: 'var(--t-bright)',
        letterSpacing: '0.04em', textTransform: 'uppercase',
        overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
      }}>
        <InstrumentLabel symbol={rawTs} />
      </span>

      <span ref={flashRef} style={{
        fontSize: 24, fontWeight: 300, color: 'var(--t-bright)',
        fontVariantNumeric: 'tabular-nums', letterSpacing: '-0.01em',
        marginTop: 8, lineHeight: 1.1,
      }}>
        {priceStr}
      </span>

      <div style={{ display: 'flex', alignItems: 'baseline', gap: 14, marginTop: 6, minHeight: 16 }}>
        {abs != null && (
          <span style={{ fontSize: 12.5, fontWeight: 400, color: chgColor, fontVariantNumeric: 'tabular-nums' }}>{absStr}</span>
        )}
        {pct != null && (
          <span style={{ fontSize: 12.5, fontWeight: 400, color: chgColor, fontVariantNumeric: 'tabular-nums' }}>{pctStr}</span>
        )}
        {abs == null && <span style={{ fontSize: 11, color: 'var(--t-dim)' }}>{hasPrice ? exch : 'no data'}</span>}
      </div>

      <Sparkline points={series} color={SPARK} />
    </div>
  );
}

export function KiteTicker() {
  const { items } = useKiteWatchlist();
  // Quote (not LTP) so each tile shows day-change + a sparkline. The symbol set
  // matches MarketWatchPane's quote poll, so React Query collapses them into one.
  const symbols = items.map((w) => w.symbol);
  const { data: quotes } = useKiteQuote(symbols, items.length > 0);
  const outerRef = useRef<HTMLDivElement>(null);
  const copyRef = useRef<HTMLDivElement>(null);
  const [overflow, setOverflow] = useState(false);
  const [shift, setShift] = useState(0);

  useLayoutEffect(() => {
    const outer = outerRef.current;
    const copy = copyRef.current;
    if (!outer || !copy) return;
    const measure = () => {
      const copyW = copy.scrollWidth;
      const avail = outer.clientWidth - 40;
      const over = copyW > 0 && copyW > avail;
      setOverflow(over);
      setShift(over ? copyW + 8 : 0);
    };
    measure();
    const ro = new ResizeObserver(measure);
    ro.observe(outer);
    ro.observe(copy);
    return () => ro.disconnect();
  }, [items.length]);

  if (items.length === 0) {
    return (
      <div style={{
        height: 56, background: 'var(--t-bg2)', borderBottom: '1px solid var(--t-border)',
        display: 'flex', alignItems: 'center', padding: '0 20px', flexShrink: 0,
        fontFamily: TILE_FONT,
      }}>
        <span style={{ color: 'var(--t-dim)', fontSize: 11 }}>
          Kite watchlist empty — search &amp; add instruments from Market Watch tab
        </span>
      </div>
    );
  }

  const cards = items.map((w) => (
    <KiteCard key={w.symbol} sym={w.symbol} q={quotes?.[w.symbol]} />
  ));

  const GAP = 10;
  const duration = Math.min(120, Math.max(12, shift / 45));

  return (
    <div ref={outerRef} style={{
      background: 'var(--t-bg2)', borderBottom: '1px solid var(--t-border)',
      padding: '10px 20px', flexShrink: 0, overflow: 'hidden',
      fontFamily: TILE_FONT,
    }}>
      <div
        className={overflow ? 'ticker-marquee' : undefined}
        style={{
          display: 'flex', alignItems: 'stretch', gap: GAP, width: 'max-content',
          ...(overflow ? { ['--ticker-shift' as string]: `${shift}px`, animationDuration: `${duration}s` } : {}),
        } as React.CSSProperties}
      >
        <div ref={copyRef} style={{ display: 'flex', alignItems: 'stretch', gap: GAP }}>{cards}</div>
        {overflow && <div aria-hidden style={{ display: 'flex', alignItems: 'stretch', gap: GAP }}>{cards}</div>}
      </div>
    </div>
  );
}
