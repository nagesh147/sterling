import React, { useEffect, useLayoutEffect, useMemo, useRef, useState } from 'react';
import { useKiteQuote } from '../../hooks/useKite';
import { useCandles } from '../../hooks/useCandles';
import { useTickerPins } from '../../store/useTickerPins';
import { TickerTile } from './ticker/TickerTile';
import { type TickerTileStyle } from '../../utils/tickerTileStyles';
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

/**
 * One pinned instrument: fetches its data, hands it to the chosen preset.
 *
 * Kept as a component per tile rather than one bulk fetch because each tile
 * pulls its own candle history, and React Query dedupes identical symbols
 * across the strip and the rest of the app for free.
 */
function KiteCard({ sym, q, tileScale, tileStyle, onOpenChart }: {
  sym: string; q: any; tileScale: number; tileStyle: TickerTileStyle; onOpenChart?: (symbol: string) => void;
}) {
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

  const segments = sym.split(':');
  const exch = segments[0] || '';
  const rawTs = segments.slice(1).join(':') || sym;
  const label = formatTickerLabel(rawTs, exch);

  return (
    <TickerTile
      style={tileStyle}
      scale={tileScale}
      onOpenChart={onOpenChart}
      onUnpin={unpin}
      data={{
        symbol: sym,
        primary: label.primary,
        secondary: label.secondary,
        market: label.market || exch,
        last: hasPrice ? last! : null,
        change: abs,
        changePct: pct,
        open: open ?? null,
        high: q?.ohlc?.high ?? null,
        low: q?.ohlc?.low ?? null,
        series,
      }}
    />
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
  const tileStyle = useTickerPins((s) => s.tileStyle ?? 'card');
  const stripEnabled = useTickerPins((s) => s.stripEnabled ?? true);
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
  // Read inside the ResizeObserver without making it a dependency.
  const tileStyleRef = useRef(tileStyle);
  tileStyleRef.current = tileStyle;

  useLayoutEffect(() => {
    const outer = outerRef.current;
    const copy = copyRef.current;
    if (!outer || !copy) return;
    const measure = () => {
      const copyW = copy.scrollWidth;
      const avail = outer.clientWidth - 40;
      const over = copyW > 0 && copyW > avail;
      setOverflow(over);
      setShift(over || tileStyleRef.current === 'tape' ? copyW + 10 : 0);
    };
    measure();
    const ro = new ResizeObserver(measure);
    ro.observe(outer);
    ro.observe(copy);
    return () => ro.disconnect();
  }, [items.length, tileScale, tileStyle]);

  // Off means gone, not empty: the whole point of the switch is the space.
  if (!stripEnabled) return null;

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
    <KiteCard key={w.symbol} sym={w.symbol} q={quotes?.[w.symbol]} tileScale={tileScale} tileStyle={tileStyle} onOpenChart={onOpenChart} />
  ));

  const GAP = tileStyle === 'tape' ? 0 : tileStyle === 'badge' || tileStyle === 'minimal' ? 6 : 10;
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
        className={overflow || tileStyle === 'tape' ? 'ticker-marquee' : undefined}
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
