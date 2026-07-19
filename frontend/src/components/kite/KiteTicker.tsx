import React, { useEffect, useLayoutEffect, useMemo, useRef, useState } from 'react';
import { useKiteQuote } from '../../hooks/useKite';
import { useCandles } from '../../hooks/useCandles';
import { useTickerPins } from '../../store/useTickerPins';
import { InstrumentLabel } from './InstrumentLabel';
import { SignalMarker } from './SignalMarker';

// Keep the classic Chromium card treatment, but use the native UI stack so text
// stays crisp across Chrome/Chromium instead of depending on a downloaded webfont.
const TILE_FONT = "-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif";

// Match Kite/light-theme watchlist semantics: profit/up = Fruit Salad green.
const UP = '#4caf50';
const DOWN = '#EF4444';
const SPARK = '#4caf50';
const TICKER_BG = '#fff';
const TICKER_BORDER = '#e0e0e0';
const CARD_BORDER = '#9b9b9b';
const TEXT = '#333';
const DIM = '#777';

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
  const [hover, setHover] = useState(false);

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
  const chgColor = abs == null || abs === 0 ? DIM : isUp ? UP : DOWN;
  const priceColor = abs == null || abs === 0 ? TEXT : chgColor;

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

  const priceStr = hasPrice
    ? last!.toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
    : '—';
  const absStr = abs != null ? `${abs >= 0 ? '+' : ''}${abs.toFixed(2)}` : '';
  const pctStr = pct != null ? `${pct >= 0 ? '+' : ''}${pct.toFixed(2)}%` : '';

  return (
    <div
      onMouseEnter={() => setHover(true)}
      onMouseLeave={() => setHover(false)}
      style={{
        display: 'flex', alignItems: 'center', gap: 12,
        background: TICKER_BG,
        border: `1px solid ${CARD_BORDER}`,
        borderRadius: 6,
        padding: '12px 14px',
        width: 250,
        flexShrink: 0,
        position: 'relative',
        boxShadow: 'none',
        boxSizing: 'border-box',
        color: TEXT,
        WebkitFontSmoothing: 'antialiased',
        MozOsxFontSmoothing: 'grayscale',
        textRendering: 'geometricPrecision',
      }}>
      <button
        onClick={(e) => { e.stopPropagation(); unpin(sym); }}
        title="Remove from ticker"
        aria-label={`Remove ${rawTs} from ticker`}
        style={{
          position: 'absolute', top: 3, right: 3,
          width: 14, height: 14, padding: 0, lineHeight: '12px',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          fontSize: 11, fontWeight: 100,
          background: 'transparent', border: 'none', borderRadius: 3,
          color: DIM, cursor: 'pointer',
          opacity: hover ? 0.7 : 0,
          pointerEvents: hover ? 'auto' : 'none',
          transition: 'opacity .12s',
        }}
        onMouseEnter={(e) => { e.currentTarget.style.opacity = '1'; e.currentTarget.style.color = TEXT; }}
        onMouseLeave={(e) => { e.currentTarget.style.opacity = '0.7'; e.currentTarget.style.color = DIM; }}
      >
        ×
      </button>

      <div style={{ display: 'flex', flexDirection: 'column', flex: 1, minWidth: 0 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 5, minWidth: 0 }}>
          <span style={{
            fontSize: 12, fontWeight: 100, color: TEXT,
            letterSpacing: '0.015em', textTransform: 'uppercase', lineHeight: 1.2,
            overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
          }}>
            <InstrumentLabel symbol={rawTs} />
          </span>
          <SignalMarker symbol={sym} color={DIM} />
        </div>

        <span ref={flashRef} style={{
          fontSize: 24, fontWeight: 100, color: priceColor,
          fontVariantNumeric: 'tabular-nums lining-nums', letterSpacing: '-0.015em',
          marginTop: 7, lineHeight: 1.08,
        }}>
          {priceStr}
        </span>

        <div style={{ display: 'flex', alignItems: 'baseline', gap: 12, marginTop: 6, minHeight: 16 }}>
          {abs != null && (
            <span style={{ fontSize: 12.5, fontWeight: 100, color: chgColor, fontVariantNumeric: 'tabular-nums lining-nums', lineHeight: 1.2 }}>{absStr}</span>
          )}
          {pct != null && (
            <span style={{ fontSize: 12.5, fontWeight: 100, color: chgColor, fontVariantNumeric: 'tabular-nums lining-nums', lineHeight: 1.2 }}>{pctStr}</span>
          )}
          {abs == null && <span style={{ fontSize: 11, fontWeight: 100, color: DIM }}>{hasPrice ? exch : 'no data'}</span>}
        </div>
      </div>

      <Sparkline points={series} color={abs == null || abs === 0 ? SPARK : isUp ? UP : DOWN} width={76} height={46} />
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
        height: 56, background: TICKER_BG, borderBottom: `1px solid ${TICKER_BORDER}`,
        display: 'flex', alignItems: 'center', padding: '0 20px', flexShrink: 0,
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

  const GAP = 10;
  const duration = Math.min(120, Math.max(12, shift / 45));

  return (
    <div ref={outerRef} style={{
      background: TICKER_BG,
      borderBottom: `1px solid ${TICKER_BORDER}`,
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
