import React, { useEffect, useLayoutEffect, useMemo, useRef, useState } from 'react';
import { useKiteQuote } from '../../hooks/useKite';
import { useCandles } from '../../hooks/useCandles';
import { useTickerPins } from '../../store/useTickerPins';
import { parseInstrument } from './InstrumentLabel';

// Keep the older compact Kite tile footprint while still honoring the app font picker.
const TILE_FONT = "var(--app-font, 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif)";

// Match Kite/light-theme watchlist semantics.
const UP = 'var(--k-green)';
const DOWN = 'var(--k-red)';
const TICKER_BG = 'var(--k-bg)';
const TICKER_BORDER = 'var(--k-border)';
const CARD_BG = 'var(--k-bg)';
const CARD_BORDER = 'var(--k-dim)';
const TEXT = 'var(--k-ink-1)';
const DIM = 'var(--k-ink-5)';

const HIST = new Map<string, number[]>();
const HIST_CAP = 48;

export function pushTickerHistory(sym: string, seed: number | undefined, px: number | undefined): number[] {
  let arr = HIST.get(sym);
  if (!arr) {
    arr = seed != null && seed > 0 ? [seed] : [];
    HIST.set(sym, arr);
  }
  if (px != null && px > 0 && (arr.length === 0 || arr[arr.length - 1] !== px)) {
    arr.push(px);
    if (arr.length > HIST_CAP) arr.splice(0, arr.length - HIST_CAP);
  }
  return [...arr];
}

export function mergeTickerSeries(
  candlePoints: number[],
  livePoints: number[],
  cap = HIST_CAP,
): number[] {
  const merged = [...candlePoints.filter((v) => v > 0), ...livePoints.filter((v) => v > 0)];
  if (merged.length === 0) return [];
  const deduped = merged.filter((value, index) => index === 0 || value !== merged[index - 1]);
  return deduped.slice(-cap);
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
  const pad = Math.max(3, Math.round(height * 0.07));
  const h = height - pad * 2;
  const stepX = width / (points.length - 1);
  const d = points
    .map((p, i) => `${(i * stepX).toFixed(1)},${(pad + h - ((p - min) / range) * h).toFixed(1)}`)
    .join(' ');
  return (
    <svg width={width} height={height} style={{ display: 'block', overflow: 'visible', flexShrink: 0 }} aria-hidden>
      <polyline points={d} fill="none" stroke={color} strokeWidth={scaled(width / 76, 1.6, 1.1)} strokeLinejoin="round" strokeLinecap="round" />
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
  const liveSeries = useMemo(() => pushTickerHistory(sym, close ?? open, last), [sym, close, open, last]);
  const series = useMemo(() => {
    const toMs = (t: number) => (t < 1e12 ? t * 1000 : t);
    let candleSeries: number[] = [];
    if (candles && candles.length > 1) {
      const lastDay = new Date(toMs(candles[candles.length - 1].time)).toDateString();
      const dayBars = candles.filter((c) => new Date(toMs(c.time)).toDateString() === lastDay);
      candleSeries = (dayBars.length > 1 ? dayBars : candles).map((c) => c.close).filter((v) => v > 0);
    }
    const merged = mergeTickerSeries(candleSeries, liveSeries);
    if (merged.length > 1) return merged;
    const base = close ?? open ?? last;
    return base != null && base > 0 ? [base, last ?? base] : [];
  }, [candles, liveSeries, close, open, last]);

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

  const cardW = scaled(tileScale, 250, 195);
  const cardH = scaled(tileScale, 104, 82);
  const chartW = scaled(tileScale, 76, 58);
  const chartH = scaled(tileScale, 46, 36);
  const titleSize = scaled(tileScale, 12, 10);
  const secondarySize = scaled(tileScale, 9.5, 8);
  const priceSize = scaled(tileScale, 24, 18);
  const changeSize = scaled(tileScale, 12.5, 10);
  const compactDerivative = Boolean(label.secondary);

  return (
    <div
      onMouseEnter={() => setHover(true)}
      onMouseLeave={() => setHover(false)}
      title={label.full}
      style={{
        display: 'flex', alignItems: 'center', gap: scaled(tileScale, 12, 8),
        background: CARD_BG,
        border: `1px solid ${CARD_BORDER}`,
        borderRadius: scaled(tileScale, 6, 5),
        padding: `${scaled(tileScale, 12, 9)}px ${scaled(tileScale, 14, 10)}px`,
        width: cardW,
        minHeight: cardH,
        flexShrink: 0,
        boxShadow: 'none',
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
          position: 'absolute', top: scaled(tileScale, 3, 2), right: scaled(tileScale, 3, 2),
          width: scaled(tileScale, 14, 10), height: scaled(tileScale, 14, 10), padding: 0, lineHeight: '12px',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          fontSize: scaled(tileScale, 11, 8), fontWeight: 300,
          background: 'transparent', border: 'none', borderRadius: 3,
          color: DIM, cursor: 'pointer',
          opacity: hover ? 0.7 : 0,
          pointerEvents: hover ? 'auto' : 'none',
          transition: 'opacity .12s, color .12s',
        }}
        onMouseEnter={(e) => { e.currentTarget.style.opacity = '1'; e.currentTarget.style.color = TEXT; }}
        onMouseLeave={(e) => { e.currentTarget.style.opacity = '0.7'; e.currentTarget.style.color = DIM; }}
      >
        ×
      </button>

      <div style={{ display: 'flex', flexDirection: 'column', flex: 1, minWidth: 0, maxWidth: cardW - chartW - scaled(tileScale, 38, 28) }}>
        {compactDerivative ? (
          <div style={{ display: 'flex', alignItems: 'baseline', gap: scaled(tileScale, 5, 3), minWidth: 0, marginBottom: scaled(tileScale, 7, 4), paddingRight: scaled(tileScale, 8, 4) }}>
            <span style={{
              fontSize: titleSize, fontWeight: 700, color: TEXT,
              letterSpacing: '0.015em', textTransform: 'uppercase', lineHeight: 1.2,
              overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', minWidth: 0,
            }}>
              {label.full}
            </span>
          </div>
        ) : (
          <div style={{ display: 'flex', alignItems: 'baseline', gap: scaled(tileScale, 5, 3), minWidth: 0, marginBottom: scaled(tileScale, 7, 4), paddingRight: scaled(tileScale, 8, 4) }}>
            <span style={{
              fontSize: titleSize, fontWeight: 700, color: TEXT,
              letterSpacing: '0.015em', textTransform: 'uppercase', lineHeight: 1.2,
              overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', minWidth: 0,
            }}>
              {label.primary}
            </span>
            {label.market && (
              <span style={{ fontSize: secondarySize, fontWeight: 700, color: DIM, lineHeight: 1.2, whiteSpace: 'nowrap', flexShrink: 0 }}>
                {label.market}
              </span>
            )}
          </div>
        )}

        <span ref={flashRef} style={{
          fontSize: priceSize, fontWeight: 300, color: TEXT,
          fontVariantNumeric: 'tabular-nums lining-nums', letterSpacing: '-0.015em',
          lineHeight: 1.08,
          whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'clip',
        }}>
          {priceStr}
        </span>

        <div style={{ display: 'flex', alignItems: 'baseline', gap: scaled(tileScale, 12, 7), marginTop: scaled(tileScale, 6, 3), minHeight: scaled(tileScale, 16, 12) }}>
          {abs != null && (
            <span style={{ fontSize: changeSize, fontWeight: 500, color: movementColor, fontVariantNumeric: 'tabular-nums lining-nums', lineHeight: 1.2, whiteSpace: 'nowrap' }}>{absStr}</span>
          )}
          {pct != null && (
            <span style={{ fontSize: changeSize, fontWeight: 500, color: movementColor, fontVariantNumeric: 'tabular-nums lining-nums', lineHeight: 1.2, whiteSpace: 'nowrap' }}>{pctStr}</span>
          )}
          {abs == null && <span style={{ fontSize: scaled(tileScale, 11, 9), fontWeight: 400, color: DIM }}>{hasPrice ? (label.market || exch) : 'no data'}</span>}
        </div>
      </div>

      <button
        type="button"
        onClick={(e) => { e.stopPropagation(); onOpenChart?.(sym); }}
        disabled={!onOpenChart}
        title={onOpenChart ? `Open ${label.full} chart` : undefined}
        style={{
          flex: `0 0 ${chartW}px`, alignSelf: 'center',
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
        background: 'var(--k-bg)', color: TEXT, cursor: 'pointer', fontFamily: TILE_FONT,
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
      const avail = outer.clientWidth - 40;
      const over = copyW > 0 && copyW > avail;
      setOverflow(over);
      setShift(over ? copyW + 10 : 0);
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
    <KiteCard key={w.symbol} sym={w.symbol} q={quotes?.[w.symbol]} tileScale={tileScale} onOpenChart={onOpenChart} />
  ));

  const GAP = 10;
  const duration = Math.min(120, Math.max(12, shift / 45));

  return (
    <div
      ref={outerRef}
      onMouseEnter={() => setHover(true)}
      onMouseLeave={() => setHover(false)}
      style={{
        background: TICKER_BG,
        borderBottom: `1px solid ${TICKER_BORDER}`,
        padding: '10px 20px', flexShrink: 0, overflow: 'hidden',
        fontFamily: TILE_FONT, position: 'relative',
      }}
    >
      <div
        style={{
          position: 'absolute', top: 6, right: 10, zIndex: 4,
          display: 'inline-flex', alignItems: 'center', gap: 4,
          padding: '3px 5px', borderRadius: 7,
          background: 'color-mix(in srgb, var(--k-bg) 94%, transparent)', border: '1px solid var(--k-border)',
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
