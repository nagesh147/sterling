import React, { useEffect, useLayoutEffect, useMemo, useRef, useState } from 'react';
import { useKiteQuote } from '../../hooks/useKite';
import { useCandles } from '../../hooks/useCandles';
import { useTickerPins } from '../../store/useTickerPins';
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

function Sparkline({ points, color, width = 80, height = 40 }: {
  points: number[]; color: string; width?: number; height?: number;
}) {
  if (!points || points.length < 2) return <div style={{ width, height }} />;
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
    <svg width={width} height={height} style={{ display: 'block', overflow: 'visible', flexShrink: 0 }}>
      <polyline points={d} fill="none" stroke={color} strokeWidth={1.6} strokeLinejoin="round" strokeLinecap="round" />
    </svg>
  );
}

function KiteCard({ sym, q }: { sym: string; q: any }) {
  const flashRef = useRef<HTMLSpanElement>(null);
  const prevRef = useRef<number | null>(null);
  const unpin = useTickerPins((s) => s.unpin);

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

  // Real intraday shape: drive the sparkline from 5-minute candles of the latest
  // trading day. This shows a proper curve (not a 2-point slanted line) and, at
  // EOD / when the market is offline, renders the complete day's chart. The live
  // tick is appended so the curve still tracks the latest price between candle
  // refreshes. Falls back to the accumulated tick buffer if candles aren't ready.
  const { data: candles } = useCandles(sym, '5m', 90);
  const series = useMemo(() => {
    const toMs = (t: number) => (t < 1e12 ? t * 1000 : t);
    if (candles && candles.length > 1) {
      const lastDay = new Date(toMs(candles[candles.length - 1].time)).toDateString();
      const dayBars = candles.filter((c) => new Date(toMs(c.time)).toDateString() === lastDay);
      const pts = (dayBars.length > 1 ? dayBars : candles).map((c) => c.close).filter((v) => v > 0);
      if (last != null && last > 0 && pts.length && pts[pts.length - 1] !== last) pts.push(last);
      if (pts.length > 1) return pts;
    }
    // Fallback: accumulated live ticks, else a flat baseline so something renders.
    let s = pushHist(sym, close ?? open, last);
    if (s.length < 2) {
      const base = close ?? open;
      if (base != null && base > 0 && last != null && last > 0) s = [base, last];
      else if (last != null && last > 0) s = [last, last];
    }
    return s;
  }, [candles, last, close, open, sym]);

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
      display: 'flex', alignItems: 'center', gap: 12,
      border: '1px solid var(--t-border)',
      borderRadius: 8, padding: '12px 14px', width: 250, flexShrink: 0,
      position: 'relative',
    }}>
      {/* Tiny close — removes this instrument from the ticker row */}
      <button
        onClick={(e) => { e.stopPropagation(); unpin(sym); }}
        title="Remove from ticker"
        aria-label={`Remove ${rawTs} from ticker`}
        style={{
          position: 'absolute', top: 3, right: 3,
          width: 14, height: 14, padding: 0, lineHeight: '12px',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          fontSize: 11, fontWeight: 600,
          background: 'transparent', border: 'none', borderRadius: 3,
          color: 'var(--t-dim)', cursor: 'pointer', opacity: 0.6,
        }}
        onMouseEnter={(e) => { e.currentTarget.style.opacity = '1'; e.currentTarget.style.color = 'var(--t-bright)'; }}
        onMouseLeave={(e) => { e.currentTarget.style.opacity = '0.6'; e.currentTarget.style.color = 'var(--t-dim)'; }}
      >
        ×
      </button>

      {/* Left: name + price + change */}
      <div style={{ display: 'flex', flexDirection: 'column', flex: 1, minWidth: 0 }}>
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
      </div>

      {/* Right: sparkline, vertically centred, tinted by direction */}
      <Sparkline points={series} color={abs == null ? SPARK : up ? UP : DOWN} width={76} height={46} />
    </div>
  );
}

export function KiteTicker() {
  // Top-bar tiles are driven by an explicit pin list (NIFTY + SENSEX by default),
  // NOT the Market Watch list. Users pin/unpin from a watch row or signal row.
  const pins = useTickerPins((s) => s.pins);
  const items = useMemo(() => pins.map((symbol) => ({ symbol })), [pins]);
  // Quote (not LTP) so each tile shows day-change + a sparkline.
  const symbols = pins;
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
        height: 56, borderBottom: '1px solid var(--t-border)',
        display: 'flex', alignItems: 'center', padding: '0 20px', flexShrink: 0,
        fontFamily: TILE_FONT,
      }}>
        <span style={{ color: 'var(--t-dim)', fontSize: 11 }}>
          No pinned tiles — add instruments from a Market Watch or Signals row’s “Add to Ticker”.
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
      borderBottom: '1px solid var(--t-border)',
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
