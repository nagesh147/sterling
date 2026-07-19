import React, { useEffect, useLayoutEffect, useMemo, useRef, useState } from 'react';
import { useKiteQuote } from '../../hooks/useKite';
import { useCandles } from '../../hooks/useCandles';
import { useTickerPins } from '../../store/useTickerPins';
import { parseInstrument } from './InstrumentLabel';

// Keep the card close to the supplied Kite-style reference while still honoring
// the app font picker when the user customizes typography.
const TILE_FONT = "var(--app-font, 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif)";

// Match Kite/light-theme watchlist semantics.
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

function formatTickerLabel(rawTs: string, exchange: string): { primary: string; secondary: string; market: string; full: string } {
  const parsed = parseInstrument(rawTs);
  if (parsed) {
    const expiry = [parsed.day ? String(parsed.day) : null, parsed.month].filter(Boolean).join(' ');
    const secondary = [expiry, parsed.strike, parsed.type].filter(Boolean).join(' ');
    const full = [parsed.underlying, secondary].filter(Boolean).join(' ');
    return { primary: parsed.underlying, secondary, market: exchange, full };
  }

  const market = isIndexSymbol(rawTs, exchange) ? 'INDEX' : exchange;
  return { primary: rawTs, secondary: '', market, full: rawTs };
}

const scaled = (scale: number, value: number, min?: number) => {
  const next = Math.round(value * scale * 10) / 10;
  return min == null ? next : Math.max(min, next);
};

function Sparkline({ points, color, width, height }: {
  points: number[]; color: string; width: number; height: number;
}) {
  if (!points || points.length < 2) return <div style={{ width, height }} />;
  const min = Math.min(...points);
  const max = Math.max(...points);
  const range = max - min || 1;
  const pad = Math.max(4, Math.round(height * 0.06));
  const h = height - pad * 2;
  const stepX = width / (points.length - 1);
  const d = points
    .map((p, i) => `${(i * stepX).toFixed(1)},${(pad + h - ((p - min) / range) * h).toFixed(1)}`)
    .join(' ');
  return (
    <svg width={width} height={height} style={{ display: 'block', overflow: 'visible', flexShrink: 0 }} aria-hidden>
      <polyline points={d} fill="none" stroke={color} strokeWidth={scaled(width / 138, 2.4, 1.6)} strokeLinejoin="round" strokeLinecap="round" />
    </svg>
  );
}

function KiteCard({ sym, q, tileScale, onOpenChart }: { sym: string; q: any; tileScale: number; onOpenChart?: (symbol: string) => void }) {
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
  const label = formatTickerLabel(rawTs, exch);

  const priceStr = hasPrice
    ? last!.toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
    : '—';
  const absStr = abs != null ? `${abs >= 0 ? '+' : ''}${abs.toFixed(2)}` : '';
  const pctStr = pct != null ? `${pct >= 0 ? '+' : ''}${pct.toFixed(2)}%` : '';

  const cardW = scaled(tileScale, 360, 280);
  const cardH = scaled(tileScale, 146, 112);
  const chartW = scaled(tileScale, 138, 96);
  const chartH = scaled(tileScale, 82, 58);
  const padX = scaled(tileScale, 20, 14);
  const padY = scaled(tileScale, 20, 14);

  return (
    <div
      onMouseEnter={() => setHover(true)}
      onMouseLeave={() => setHover(false)}
      title={label.full}
      style={{
        display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: scaled(tileScale, 18, 12),
        background: CARD_BG,
        border: `1px solid ${CARD_BORDER}`,
        borderRadius: scaled(tileScale, 16, 12),
        padding: `${padY}px ${padX}px ${scaled(tileScale, 18, 13)}px ${scaled(tileScale, 22, 15)}px`,
        width: cardW,
        minHeight: cardH,
        flexShrink: 0,
        boxShadow: '0 1px 4px rgba(15, 23, 42, 0.08)',
        boxSizing: 'border-box',
        color: TEXT,
        position: 'relative',
        WebkitFontSmoothing: 'antialiased',
        MozOsxFontSmoothing: 'grayscale',
        textRendering: 'geometricPrecision',
      }}
    >
      <button
        onClick={(e) => { e.stopPropagation(); unpin(sym); }}
        title="Remove from ticker"
        aria-label={`Remove ${label.full} from ticker`}
        style={{
          position: 'absolute', top: 8, right: 8,
          width: 20, height: 20, padding: 0,
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          fontSize: 15, fontWeight: 300, lineHeight: 1,
          background: 'transparent', border: 'none', borderRadius: 4,
          color: DIM, cursor: 'pointer', opacity: hover ? 0.85 : 0.45,
          transition: 'opacity .12s, color .12s',
        }}
        onMouseEnter={(e) => { e.currentTarget.style.opacity = '1'; e.currentTarget.style.color = TEXT; }}
        onMouseLeave={(e) => { e.currentTarget.style.opacity = hover ? '0.85' : '0.45'; e.currentTarget.style.color = DIM; }}
      >
        ×
      </button>

      <div style={{ display: 'flex', flexDirection: 'column', minWidth: 0, flex: '1 1 auto' }}>
        <div style={{ display: 'flex', alignItems: 'baseline', gap: scaled(tileScale, 8, 5), minWidth: 0, marginBottom: scaled(tileScale, 15, 9), paddingRight: 14 }}>
          <span style={{
            fontSize: scaled(tileScale, 18, 14), fontWeight: 700, color: TEXT, lineHeight: 1.2,
            overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', minWidth: 0,
          }}>
            {label.primary}
          </span>
          {label.secondary && (
            <span style={{ fontSize: scaled(tileScale, 15, 11), fontWeight: 600, color: TEXT, lineHeight: 1.2, whiteSpace: 'nowrap', flexShrink: 0 }}>
              {label.secondary}
            </span>
          )}
          {!label.secondary && label.market && (
            <span style={{ fontSize: scaled(tileScale, 15, 11), fontWeight: 700, color: DIM, lineHeight: 1.2, whiteSpace: 'nowrap', flexShrink: 0 }}>
              {label.market}
            </span>
          )}
        </div>

        <span ref={flashRef} style={{
          fontSize: scaled(tileScale, 42, 30), fontWeight: 300, color: TEXT,
          fontVariantNumeric: 'tabular-nums lining-nums', letterSpacing: '-0.02em',
          lineHeight: 1,
        }}>
          {priceStr}
        </span>

        <div style={{ display: 'flex', alignItems: 'baseline', gap: scaled(tileScale, 26, 14), marginTop: scaled(tileScale, 14, 8), minHeight: scaled(tileScale, 24, 18) }}>
          {abs != null && (
            <span style={{
              fontSize: scaled(tileScale, 19, 14), fontWeight: 500, color: movementColor,
              fontVariantNumeric: 'tabular-nums lining-nums', lineHeight: 1.2,
            }}>
              {absStr}
            </span>
          )}
          {pct != null && (
            <span style={{
              fontSize: scaled(tileScale, 19, 14), fontWeight: 500, color: movementColor,
              fontVariantNumeric: 'tabular-nums lining-nums', lineHeight: 1.2,
            }}>
              {pctStr}
            </span>
          )}
          {abs == null && <span style={{ fontSize: scaled(tileScale, 12, 10), fontWeight: 400, color: DIM }}>{hasPrice ? (label.market || exch) : 'no data'}</span>}
        </div>
      </div>

      <button
        type="button"
        onClick={(e) => { e.stopPropagation(); onOpenChart?.(sym); }}
        disabled={!onOpenChart}
        title={onOpenChart ? `Open ${label.full} chart` : undefined}
        style={{
          flex: `0 0 ${chartW}px`, alignSelf: 'center', marginTop: scaled(tileScale, 16, 8),
          border: 'none', background: 'transparent', padding: 0,
          cursor: onOpenChart ? 'pointer' : 'default', opacity: onOpenChart ? 1 : 0.95,
        }}
      >
        <Sparkline points={series} color={movementColor} width={chartW} height={chartH} />
      </button>
    </div>
  );
}

function SizeControlButton({ label, onClick }: { label: string; onClick: () => void }) {
  return (
    <button
      type="button"
      onClick={(e) => { e.stopPropagation(); onClick(); }}
      style={{
        width: 24, height: 22, border: '1px solid #d6d6d6', borderRadius: 5,
        background: '#fff', color: TEXT, cursor: 'pointer', fontFamily: TILE_FONT,
        fontSize: 13, lineHeight: 1, display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
      }}
    >
      {label}
    </button>
  );
}

export function KiteTicker({ onOpenChart }: { onOpenChart?: (symbol: string) => void }) {
  const pins = useTickerPins((s) => s.pins);
  const tileScale = useTickerPins((s) => s.tileScale ?? 1);
  const increaseTileScale = useTickerPins((s) => s.increaseTileScale);
  const decreaseTileScale = useTickerPins((s) => s.decreaseTileScale);
  const resetTileScale = useTickerPins((s) => s.resetTileScale);
  const items = useMemo(() => pins.map((symbol) => ({ symbol })), [pins]);
  const symbols = pins;
  const { data: quotes } = useKiteQuote(symbols, items.length > 0);
  const outerRef = useRef<HTMLDivElement>(null);
  const copyRef = useRef<HTMLDivElement>(null);
  const [overflow, setOverflow] = useState(false);
  const [shift, setShift] = useState(0);
  const [hover, setHover] = useState(false);

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
  }, [items.length, tileScale]);

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
    <KiteCard key={w.symbol} sym={w.symbol} q={quotes?.[w.symbol]} tileScale={tileScale} onOpenChart={onOpenChart} />
  ));

  const GAP = 12;
  const duration = Math.min(140, Math.max(14, shift / 45));

  return (
    <div
      ref={outerRef}
      onMouseEnter={() => setHover(true)}
      onMouseLeave={() => setHover(false)}
      style={{
        background: TICKER_BG,
        borderBottom: `1px solid ${TICKER_BORDER}`,
        padding: '14px 16px', flexShrink: 0, overflow: 'hidden',
        fontFamily: TILE_FONT, position: 'relative',
      }}
    >
      <div
        style={{
          position: 'absolute', top: 8, right: 12, zIndex: 4,
          display: 'inline-flex', alignItems: 'center', gap: 4,
          padding: '3px 5px', borderRadius: 7,
          background: 'rgba(255,255,255,0.94)', border: '1px solid #e0e0e0',
          boxShadow: '0 1px 5px rgba(15, 23, 42, 0.10)',
          opacity: hover ? 1 : 0, pointerEvents: hover ? 'auto' : 'none',
          transition: 'opacity .12s ease',
        }}
      >
        <SizeControlButton label="−" onClick={decreaseTileScale} />
        <button
          type="button"
          onClick={(e) => { e.stopPropagation(); resetTileScale(); }}
          title="Reset ticker tile size"
          style={{
            border: 'none', background: 'transparent', cursor: 'pointer', color: DIM,
            fontSize: 10, minWidth: 34, fontFamily: TILE_FONT,
          }}
        >
          {Math.round(tileScale * 100)}%
        </button>
        <SizeControlButton label="+" onClick={increaseTileScale} />
      </div>

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
