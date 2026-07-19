import React, { useEffect, useLayoutEffect, useMemo, useRef, useState } from 'react';
import { useKiteQuote } from '../../hooks/useKite';
import { useCandles } from '../../hooks/useCandles';
import { useTickerPins } from '../../store/useTickerPins';

// Keep the classic Chromium card treatment, but use the native UI stack so text
// stays crisp across Chrome/Chromium instead of depending on a downloaded webfont.
const TILE_FONT = "-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif";

// Match the Kite light-theme watchlist semantics exactly.
const UP = '#4caf50';
const DOWN = '#df514c';
const TICKER_BG = '#f7f9fc';
const TICKER_BORDER = '#e5e7eb';
const CARD_BG = '#ffffff';
const CARD_BORDER = '#e0e0e0';
const TEXT = '#333333';
const DIM = '#9b9b9b';

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

function isIndexSymbol(symbol: string, exchange: string): boolean {
  const value = symbol.toUpperCase();
  return exchange === 'INDICES'
    || value.includes('INDEX')
    || value === 'NIFTY 50'
    || value === 'NIFTY BANK'
    || value === 'NIFTY FIN SERVICE'
    || value === 'NIFTY 100'
    || value === 'NIFTY COMMODITIES'
    || value === 'SENSEX'
    || value === 'BANKEX';
}

function Sparkline({ points, color, width = 138, height = 82 }: {
  points: number[]; color: string; width?: number; height?: number;
}) {
  if (!points || points.length < 2) return <div style={{ width, height }} />;
  const min = Math.min(...points);
  const max = Math.max(...points);
  const range = max - min || 1;
  const pad = 5;
  const h = height - pad * 2;
  const stepX = width / (points.length - 1);
  const d = points
    .map((p, i) => `${(i * stepX).toFixed(1)},${(pad + h - ((p - min) / range) * h).toFixed(1)}`)
    .join(' ');
  return (
    <svg width={width} height={height} style={{ display: 'block', overflow: 'visible', flexShrink: 0 }} aria-hidden>
      <polyline points={d} fill="none" stroke={color} strokeWidth={2.4} strokeLinejoin="round" strokeLinecap="round" />
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
  const isUp = (abs ?? 0) > 0;
  const isFlat = abs == null || abs === 0;
  const movementColor = isFlat ? DIM : isUp ? UP : DOWN;

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
  const marketLabel = isIndexSymbol(rawTs, exch) ? 'INDEX' : exch;

  const priceStr = hasPrice
    ? last!.toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
    : '—';
  const absStr = abs != null ? `${abs >= 0 ? '+' : ''}${abs.toFixed(2)}` : '';
  const pctStr = pct != null ? `${pct >= 0 ? '+' : ''}${pct.toFixed(2)}%` : '';

  return (
    <div
      style={{
        display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 18,
        background: CARD_BG,
        border: `1px solid ${CARD_BORDER}`,
        borderRadius: 16,
        padding: '20px 20px 18px 22px',
        width: 360,
        minHeight: 146,
        flexShrink: 0,
        boxShadow: '0 1px 4px rgba(15, 23, 42, 0.08)',
        boxSizing: 'border-box',
        color: TEXT,
        WebkitFontSmoothing: 'antialiased',
        MozOsxFontSmoothing: 'grayscale',
        textRendering: 'geometricPrecision',
      }}
    >
      <div style={{ display: 'flex', flexDirection: 'column', minWidth: 0, flex: '1 1 auto' }}>
        <div style={{ display: 'flex', alignItems: 'baseline', gap: 8, minWidth: 0, marginBottom: 15 }}>
          <span style={{
            fontSize: 18, fontWeight: 700, color: TEXT, lineHeight: 1.2,
            overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
          }}>
            {rawTs}
          </span>
          {marketLabel && (
            <span style={{ fontSize: 15, fontWeight: 600, color: DIM, lineHeight: 1.2, whiteSpace: 'nowrap' }}>
              {marketLabel}
            </span>
          )}
        </div>

        <span ref={flashRef} style={{
          fontSize: 42, fontWeight: 300, color: TEXT,
          fontVariantNumeric: 'tabular-nums lining-nums', letterSpacing: '-0.02em',
          lineHeight: 1,
        }}>
          {priceStr}
        </span>

        <div style={{ display: 'flex', alignItems: 'baseline', gap: 26, marginTop: 14, minHeight: 24 }}>
          {abs != null && (
            <span style={{
              fontSize: 19, fontWeight: 400, color: movementColor,
              fontVariantNumeric: 'tabular-nums lining-nums', lineHeight: 1.2,
            }}>
              {absStr}
            </span>
          )}
          {pct != null && (
            <span style={{
              fontSize: 19, fontWeight: 400, color: movementColor,
              fontVariantNumeric: 'tabular-nums lining-nums', lineHeight: 1.2,
            }}>
              {pctStr}
            </span>
          )}
          {abs == null && <span style={{ fontSize: 12, fontWeight: 400, color: DIM }}>{hasPrice ? marketLabel : 'no data'}</span>}
        </div>
      </div>

      <div style={{ flex: '0 0 138px', alignSelf: 'center', marginTop: 16 }}>
        <Sparkline points={series} color={movementColor} width={138} height={82} />
      </div>
    </div>
  );
}

export function KiteTicker() {
  const pins = useTickerPins((s) => s.pins);
  const items = useMemo(() => pins.map((symbol) => ({ symbol })), [pins]);
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
      const avail = outer.clientWidth - 32;
      const over = copyW > 0 && copyW > avail;
      setOverflow(over);
      setShift(over ? copyW + 12 : 0);
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
        height: 72, background: TICKER_BG, borderBottom: `1px solid ${TICKER_BORDER}`,
        display: 'flex', alignItems: 'center', padding: '0 16px', flexShrink: 0,
        fontFamily: TILE_FONT,
      }}>
        <span style={{ color: DIM, fontSize: 11 }}>
          No pinned tiles — add instruments from a Market Watch or Signals row’s “Add to Ticker”.
        </span>
      </div>
    );
  }

  const cards = items.map((w) => (
    <KiteCard key={w.symbol} sym={w.symbol} q={quotes?.[w.symbol]} />
  ));

  const GAP = 12;
  const duration = Math.min(120, Math.max(12, shift / 45));

  return (
    <div ref={outerRef} style={{
      background: TICKER_BG,
      borderBottom: `1px solid ${TICKER_BORDER}`,
      padding: '14px 16px', flexShrink: 0, overflow: 'hidden',
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
