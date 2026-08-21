/**
 * One pinned instrument, drawn twelve different ways.
 *
 * Every preset renders the same facts from the same props — the choice is
 * purely which of them get the space. That constraint is what keeps twelve
 * variants maintainable: there is one place that decides what a tile *knows*
 * (`TileData`) and twelve small functions that decide what it *shows*.
 *
 * All of them honour `scale`, keep the unpin control in the same corner, and
 * open the chart on click, so switching presets never relocates a control.
 */
import React from 'react';
import { k, tint } from '../../../styles/kiteUI';
import type { TickerTileStyle } from '../../../utils/tickerTileStyles';

export interface TileData {
  symbol: string;
  /** Display name, e.g. "NIFTY 50". */
  primary: string;
  /** Expiry/strike for a contract, empty for an index. */
  secondary: string;
  /** "INDEX", "NFO", … */
  market: string;
  last: number | null;
  change: number | null;
  changePct: number | null;
  open: number | null;
  high: number | null;
  low: number | null;
  /** Recent prices for the sparkline, oldest first. */
  series: number[];
}

export interface TileProps {
  data: TileData;
  scale: number;
  onOpenChart?: (symbol: string) => void;
  onUnpin?: (symbol: string) => void;
}

const px = (scale: number, base: number, min?: number) => {
  const next = Math.round(base * scale * 10) / 10;
  return min == null ? next : Math.max(min, next);
};

const fmt = (v: number | null, dp = 2) =>
  v == null ? '—' : v.toLocaleString('en-IN', { minimumFractionDigits: dp, maximumFractionDigits: dp });

const signed = (v: number | null, dp = 2) =>
  v == null ? '—' : `${v > 0 ? '+' : ''}${v.toLocaleString('en-IN', { minimumFractionDigits: dp, maximumFractionDigits: dp })}`;

function toneOf(change: number | null): string {
  if (change == null || change === 0) return k.dim;
  return change > 0 ? k.green : k.red;
}

function Sparkline({ points, color, width, height }: { points: number[]; color: string; width: number; height: number }) {
  if (!points || points.length < 2) return <div style={{ width, height, flexShrink: 0 }} />;
  const min = Math.min(...points);
  const max = Math.max(...points);
  const range = max - min || 1;
  const pad = Math.max(2, Math.round(height * 0.08));
  const h = height - pad * 2;
  const stepX = width / (points.length - 1);
  const d = points.map((p, i) => `${(i * stepX).toFixed(1)},${(pad + h - ((p - min) / range) * h).toFixed(1)}`).join(' ');
  return (
    <svg width={width} height={height} aria-hidden style={{ display: 'block', flexShrink: 0, overflow: 'visible' }}>
      <polyline points={d} fill="none" stroke={color} strokeWidth={Math.max(1.1, width / 60)} strokeLinejoin="round" strokeLinecap="round" />
    </svg>
  );
}

/** Where the last price sits between the day's low and high, 0-1. */
function dayPosition(data: TileData): number | null {
  const { low, high, last } = data;
  if (low == null || high == null || last == null || high <= low) return null;
  return Math.min(1, Math.max(0, (last - low) / (high - low)));
}

function UnpinButton({ symbol, onUnpin, scale }: { symbol: string; onUnpin?: (s: string) => void; scale: number }) {
  if (!onUnpin) return null;
  const size = px(scale, 14, 11);
  return (
    <button
      type="button"
      aria-label={`Unpin ${symbol}`}
      title={`Unpin ${symbol}`}
      className="tk-unpin"
      onClick={(e) => { e.stopPropagation(); onUnpin(symbol); }}
      style={{
        position: 'absolute', top: px(scale, 3, 2), right: px(scale, 3, 2),
        width: size, height: size, padding: 0, lineHeight: 1,
        border: 'none', borderRadius: 3, background: 'transparent', color: k.dim,
        fontSize: px(scale, 11, 9), cursor: 'pointer',
      }}
    >
      ×
    </button>
  );
}

const shell = (scale: number, extra: React.CSSProperties = {}): React.CSSProperties => ({
  position: 'relative',
  boxSizing: 'border-box',
  border: `1px solid ${k.border}`,
  borderRadius: px(scale, 6, 4),
  background: k.bg,
  cursor: 'pointer',
  flexShrink: 0,
  fontVariantNumeric: 'tabular-nums',
  ...extra,
});

const Name = ({ data, size }: { data: TileData; size: number }) => (
  <span style={{ fontSize: size, fontWeight: 600, color: k.text, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
    {data.primary}
    {data.secondary && <span style={{ color: k.dim, fontWeight: 400 }}> {data.secondary}</span>}
  </span>
);

const MarketChip = ({ market, size }: { market: string; size: number }) => (
  <span style={{
    fontSize: size, fontWeight: 700, letterSpacing: '.06em', color: k.dim,
    border: `1px solid ${k.border}`, borderRadius: 2, padding: '0 3px', whiteSpace: 'nowrap',
  }}>
    {market}
  </span>
);

/* ── the twelve ─────────────────────────────────────────────────────────── */

function Card({ data, scale, onUnpin }: TileProps) {
  const tone = toneOf(data.change);
  return (
    <div style={shell(scale, { width: px(scale, 250, 195), display: 'flex', alignItems: 'center', gap: px(scale, 12, 8), padding: `${px(scale, 11, 8)}px ${px(scale, 13, 9)}px` })}>
      <UnpinButton symbol={data.symbol} onUnpin={onUnpin} scale={scale} />
      <div style={{ flex: 1, minWidth: 0, display: 'flex', flexDirection: 'column', gap: px(scale, 3, 2) }}>
        <div style={{ display: 'flex', alignItems: 'baseline', gap: px(scale, 5, 3), minWidth: 0 }}>
          <Name data={data} size={px(scale, 11.5, 9.5)} />
          <MarketChip market={data.market} size={px(scale, 8, 7)} />
        </div>
        <span style={{ fontSize: px(scale, 22, 17), fontWeight: 300, color: k.text, lineHeight: 1.05 }}>{fmt(data.last)}</span>
        <span style={{ fontSize: px(scale, 11, 9), color: tone }}>
          {signed(data.change)} ({signed(data.changePct)}%)
        </span>
      </div>
      <Sparkline points={data.series} color={tone} width={px(scale, 74, 54)} height={px(scale, 44, 34)} />
    </div>
  );
}

function Quote({ data, scale, onUnpin }: TileProps) {
  const tone = toneOf(data.change);
  const cell = (label: string, value: number | null) => (
    <span key={label} style={{ display: 'flex', flexDirection: 'column', minWidth: 0 }}>
      <span style={{ fontSize: px(scale, 7.5, 7), color: k.dim, letterSpacing: '.05em' }}>{label}</span>
      <span style={{ fontSize: px(scale, 10, 8.5), color: k.text }}>{fmt(value)}</span>
    </span>
  );
  return (
    <div style={shell(scale, { width: px(scale, 268, 210), display: 'flex', flexDirection: 'column', gap: px(scale, 6, 4), padding: `${px(scale, 10, 8)}px ${px(scale, 12, 9)}px` })}>
      <UnpinButton symbol={data.symbol} onUnpin={onUnpin} scale={scale} />
      <div style={{ display: 'flex', alignItems: 'baseline', gap: px(scale, 5, 3) }}>
        <Name data={data} size={px(scale, 11, 9.5)} />
        <MarketChip market={data.market} size={px(scale, 8, 7)} />
      </div>
      <div style={{ display: 'flex', alignItems: 'baseline', gap: px(scale, 8, 6) }}>
        <span style={{ fontSize: px(scale, 19, 15), fontWeight: 300, color: k.text }}>{fmt(data.last)}</span>
        <span style={{ fontSize: px(scale, 10, 8.5), color: tone }}>{signed(data.changePct)}%</span>
        <Sparkline points={data.series} color={tone} width={px(scale, 52, 40)} height={px(scale, 20, 16)} />
      </div>
      <div style={{ display: 'flex', gap: px(scale, 14, 10) }}>
        {cell('OPEN', data.open)}{cell('HIGH', data.high)}{cell('LOW', data.low)}
      </div>
    </div>
  );
}

function Spark({ data, scale, onUnpin }: TileProps) {
  const tone = toneOf(data.change);
  const w = px(scale, 168, 130);
  const h = px(scale, 62, 48);
  return (
    <div style={shell(scale, { width: w, height: h, overflow: 'hidden' })}>
      <UnpinButton symbol={data.symbol} onUnpin={onUnpin} scale={scale} />
      <div style={{ position: 'absolute', inset: 0, opacity: 0.32, display: 'flex', alignItems: 'flex-end' }}>
        <Sparkline points={data.series} color={tone} width={w} height={h} />
      </div>
      <div style={{ position: 'relative', padding: `${px(scale, 7, 5)}px ${px(scale, 9, 7)}px`, display: 'flex', flexDirection: 'column' }}>
        <Name data={data} size={px(scale, 9.5, 8.5)} />
        <span style={{ fontSize: px(scale, 17, 13), fontWeight: 400, color: k.text, lineHeight: 1.15 }}>{fmt(data.last)}</span>
        <span style={{ fontSize: px(scale, 9.5, 8), color: tone }}>{signed(data.changePct)}%</span>
      </div>
    </div>
  );
}

function Range({ data, scale, onUnpin }: TileProps) {
  const tone = toneOf(data.change);
  const pos = dayPosition(data);
  return (
    <div style={shell(scale, { width: px(scale, 196, 152), display: 'flex', flexDirection: 'column', gap: px(scale, 5, 4), padding: `${px(scale, 9, 7)}px ${px(scale, 11, 8)}px` })}>
      <UnpinButton symbol={data.symbol} onUnpin={onUnpin} scale={scale} />
      <div style={{ display: 'flex', alignItems: 'baseline', gap: px(scale, 5, 3) }}>
        <Name data={data} size={px(scale, 10, 9)} />
        <span style={{ marginLeft: 'auto', fontSize: px(scale, 9.5, 8), color: tone, paddingRight: px(scale, 12, 10) }}>{signed(data.changePct)}%</span>
      </div>
      <span style={{ fontSize: px(scale, 17, 13.5), fontWeight: 300, color: k.text, lineHeight: 1.05 }}>{fmt(data.last)}</span>
      <div
        title={pos == null ? 'Day range unavailable' : `Low ${fmt(data.low)} · High ${fmt(data.high)}`}
        style={{ position: 'relative', height: px(scale, 4, 3), borderRadius: 2, background: k.surfaceHover }}
      >
        {pos != null && (
          <span style={{
            position: 'absolute', top: '50%', left: `${pos * 100}%`, transform: 'translate(-50%, -50%)',
            width: px(scale, 7, 6), height: px(scale, 7, 6), borderRadius: '50%', background: tone,
            border: `1.5px solid ${k.bg}`,
          }} />
        )}
      </div>
      <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: px(scale, 8, 7), color: k.dim }}>
        <span>{fmt(data.low)}</span><span>{fmt(data.high)}</span>
      </div>
    </div>
  );
}

function Heat({ data, scale, onUnpin }: TileProps) {
  const tone = toneOf(data.change);
  // Saturation tracks the size of the move, capped at 2% so an outlier does
  // not flatten every other tile to grey.
  const strength = Math.min(1, Math.abs(data.changePct ?? 0) / 2);
  return (
    <div style={shell(scale, {
      width: px(scale, 150, 118),
      padding: `${px(scale, 8, 6)}px ${px(scale, 10, 8)}px`,
      display: 'flex', flexDirection: 'column', gap: px(scale, 2, 1),
      background: tint(tone, Math.round(4 + strength * 22)),
      borderColor: tint(tone, Math.round(18 + strength * 34)),
    })}>
      <UnpinButton symbol={data.symbol} onUnpin={onUnpin} scale={scale} />
      <Name data={data} size={px(scale, 9.5, 8.5)} />
      <span style={{ fontSize: px(scale, 16, 12.5), fontWeight: 400, color: k.text, lineHeight: 1.1 }}>{fmt(data.last)}</span>
      <span style={{ fontSize: px(scale, 10, 8.5), fontWeight: 600, color: tone }}>{signed(data.changePct)}%</span>
    </div>
  );
}

function Stacked({ data, scale, onUnpin }: TileProps) {
  const tone = toneOf(data.change);
  return (
    <div style={shell(scale, { width: px(scale, 128, 100), padding: `${px(scale, 8, 6)}px ${px(scale, 10, 8)}px`, display: 'flex', flexDirection: 'column', gap: px(scale, 1, 1) })}>
      <UnpinButton symbol={data.symbol} onUnpin={onUnpin} scale={scale} />
      <Name data={data} size={px(scale, 9.5, 8.5)} />
      <span style={{ fontSize: px(scale, 16, 12.5), fontWeight: 400, color: k.text, lineHeight: 1.1 }}>{fmt(data.last)}</span>
      <span style={{ fontSize: px(scale, 9.5, 8), color: tone }}>{signed(data.changePct)}%</span>
    </div>
  );
}

function Split({ data, scale, onUnpin }: TileProps) {
  const tone = toneOf(data.change);
  return (
    <div style={shell(scale, { width: px(scale, 176, 138), padding: `${px(scale, 8, 6)}px ${px(scale, 22, 18)}px ${px(scale, 8, 6)}px ${px(scale, 10, 8)}px`, display: 'flex', alignItems: 'center', gap: px(scale, 8, 6) })}>
      <UnpinButton symbol={data.symbol} onUnpin={onUnpin} scale={scale} />
      <Name data={data} size={px(scale, 10, 9)} />
      <span style={{ marginLeft: 'auto', textAlign: 'right', display: 'flex', flexDirection: 'column' }}>
        <span style={{ fontSize: px(scale, 13, 11), color: k.text }}>{fmt(data.last)}</span>
        <span style={{ fontSize: px(scale, 9, 8), color: tone }}>{signed(data.changePct)}%</span>
      </span>
    </div>
  );
}

function Compact({ data, scale, onUnpin }: TileProps) {
  const tone = toneOf(data.change);
  return (
    <div style={shell(scale, { padding: `${px(scale, 5, 4)}px ${px(scale, 20, 16)}px ${px(scale, 5, 4)}px ${px(scale, 9, 7)}px`, display: 'flex', alignItems: 'baseline', gap: px(scale, 7, 5) })}>
      <UnpinButton symbol={data.symbol} onUnpin={onUnpin} scale={scale} />
      <Name data={data} size={px(scale, 9.5, 8.5)} />
      <span style={{ fontSize: px(scale, 11, 9.5), color: k.text }}>{fmt(data.last)}</span>
      <span style={{ fontSize: px(scale, 9.5, 8), color: tone }}>{signed(data.changePct)}%</span>
    </div>
  );
}

function Row({ data, scale, onUnpin }: TileProps) {
  const tone = toneOf(data.change);
  // Fixed tracks, so prices align down the strip when it wraps.
  return (
    <div style={shell(scale, {
      display: 'grid',
      gridTemplateColumns: `${px(scale, 88, 70)}px ${px(scale, 66, 54)}px ${px(scale, 58, 48)}px`,
      alignItems: 'baseline', gap: px(scale, 8, 6),
      padding: `${px(scale, 5, 4)}px ${px(scale, 20, 16)}px ${px(scale, 5, 4)}px ${px(scale, 9, 7)}px`,
    })}>
      <UnpinButton symbol={data.symbol} onUnpin={onUnpin} scale={scale} />
      <Name data={data} size={px(scale, 9.5, 8.5)} />
      <span style={{ fontSize: px(scale, 10.5, 9), color: k.text, textAlign: 'right' }}>{fmt(data.last)}</span>
      <span style={{ fontSize: px(scale, 9.5, 8), color: tone, textAlign: 'right' }}>{signed(data.changePct)}%</span>
    </div>
  );
}

function Badge({ data, scale, onUnpin }: TileProps) {
  const tone = toneOf(data.change);
  return (
    <div style={shell(scale, {
      borderRadius: 999, borderColor: tint(tone, 34), background: tint(tone, 8),
      padding: `${px(scale, 3, 2)}px ${px(scale, 18, 15)}px ${px(scale, 3, 2)}px ${px(scale, 9, 7)}px`,
      display: 'flex', alignItems: 'baseline', gap: px(scale, 6, 4),
    })}>
      <UnpinButton symbol={data.symbol} onUnpin={onUnpin} scale={scale} />
      <span style={{ fontSize: px(scale, 9, 8), fontWeight: 700, color: k.text, whiteSpace: 'nowrap' }}>{data.primary}</span>
      <span style={{ fontSize: px(scale, 9.5, 8.5), color: tone }}>{fmt(data.last, 1)}</span>
    </div>
  );
}

function Minimal({ data, scale, onUnpin }: TileProps) {
  const tone = toneOf(data.change);
  return (
    <div
      title={`${data.primary} · ${signed(data.change)} (${signed(data.changePct)}%)`}
      style={shell(scale, {
        border: 'none', background: 'transparent',
        padding: `${px(scale, 3, 2)}px ${px(scale, 16, 13)}px ${px(scale, 3, 2)}px ${px(scale, 5, 4)}px`,
      })}
    >
      <UnpinButton symbol={data.symbol} onUnpin={onUnpin} scale={scale} />
      <span style={{ fontSize: px(scale, 13, 11), color: tone, fontWeight: 500 }}>{fmt(data.last, 1)}</span>
    </div>
  );
}

/** One item of the scrolling tape. The scroll itself belongs to the strip. */
function TapeItem({ data, scale, onUnpin }: TileProps) {
  const tone = toneOf(data.change);
  return (
    <span style={{ display: 'inline-flex', alignItems: 'baseline', gap: px(scale, 6, 4), padding: `0 ${px(scale, 12, 9)}px`, whiteSpace: 'nowrap', position: 'relative' }}>
      <span style={{ fontSize: px(scale, 10, 9), fontWeight: 700, color: k.text }}>{data.primary}</span>
      <span style={{ fontSize: px(scale, 10, 9), color: k.text }}>{fmt(data.last)}</span>
      <span style={{ fontSize: px(scale, 9.5, 8.5), color: tone }}>{signed(data.changePct)}%</span>
      <UnpinButton symbol={data.symbol} onUnpin={onUnpin} scale={scale} />
    </span>
  );
}

const RENDERERS: Record<TickerTileStyle, (p: TileProps) => React.ReactElement> = {
  card: Card, quote: Quote, spark: Spark, range: Range, heat: Heat,
  stacked: Stacked, split: Split, compact: Compact, row: Row,
  badge: Badge, minimal: Minimal, tape: TapeItem,
};

export function TickerTile({ style, ...props }: TileProps & { style: TickerTileStyle }) {
  const Renderer = RENDERERS[style] ?? Card;
  const { data, onOpenChart } = props;
  return (
    <div
      role="button"
      tabIndex={0}
      aria-label={`${data.primary}, ${fmt(data.last)}, ${signed(data.changePct)} percent`}
      onClick={() => onOpenChart?.(data.symbol)}
      onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); onOpenChart?.(data.symbol); } }}
      className="tk-tile"
      style={{ display: style === 'tape' ? 'inline-flex' : 'inline-block' }}
    >
      <Renderer {...props} />
    </div>
  );
}
