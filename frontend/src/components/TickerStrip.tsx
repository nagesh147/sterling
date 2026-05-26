import React, { useEffect, useLayoutEffect, useRef, useState } from 'react';
import { useWatchlist } from '../hooks/useWatchlist';
import { useLivePrices } from '../hooks/useLivePrices';
import { useScalpingConfig } from '../hooks/useScalping';

// ── Module-level price history (survives re-renders) ─────────────────────────
const _history: Map<string, number[]> = new Map();
const MAX_PTS = 80;

function pushPrice(sym: string, price: number) {
  const h = _history.get(sym) ?? [];
  if (h.length > 0 && h[h.length - 1] === price) return; // skip duplicate
  h.push(price);
  if (h.length > MAX_PTS) h.shift();
  _history.set(sym, h);
}

// ── Coin meta ────────────────────────────────────────────────────────────────
const COIN_META: Record<string, { bg: string; fg: string; icon: string }> = {
  BTC: { bg: '#F7931A', fg: '#fff', icon: '₿' },
  ETH: { bg: '#627EEA', fg: '#fff', icon: 'Ξ' },
  SOL: { bg: '#9945FF', fg: '#fff', icon: '◎' },
  XRP: { bg: '#0085C0', fg: '#fff', icon: '✕' },
  BNB: { bg: '#F3BA2F', fg: '#000', icon: 'B' },
  MATIC: { bg: '#8247E5', fg: '#fff', icon: 'M' },
};

function CoinIcon({ sym }: { sym: string }) {
  const m = COIN_META[sym] ?? { bg: '#3B82F6', fg: '#fff', icon: sym[0] };
  return (
    <div style={{
      width: 28, height: 28, borderRadius: '50%',
      background: m.bg, color: m.fg,
      display: 'flex', alignItems: 'center', justifyContent: 'center',
      fontSize: 12, fontWeight: 800, flexShrink: 0,
    }}>
      {m.icon}
    </div>
  );
}

// ── Mini sparkline SVG ───────────────────────────────────────────────────────
function Sparkline({ sym, color }: { sym: string; color: string }) {
  const hist = _history.get(sym) ?? [];
  if (hist.length < 3) {
    return <div style={{ width: 72, height: 28, flexShrink: 0 }} />;
  }
  const W = 72, H = 28;
  const min = Math.min(...hist);
  const max = Math.max(...hist);
  const range = max - min || min * 0.001 || 1;

  const pts = hist.map((p, i) => {
    const x = (i / (hist.length - 1)) * W;
    const y = H - ((p - min) / range) * (H - 2) - 1;
    return `${x.toFixed(1)},${y.toFixed(1)}`;
  }).join(' ');

  // Fill gradient path
  const first = `0,${H}`;
  const last  = `${W},${H}`;
  const fillPts = `${first} ${pts} ${last}`;

  return (
    <svg width={W} height={H} style={{ flexShrink: 0, overflow: 'visible' }}>
      <defs>
        <linearGradient id={`sg-${sym}`} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor={color} stopOpacity="0.25" />
          <stop offset="100%" stopColor={color} stopOpacity="0" />
        </linearGradient>
      </defs>
      <polygon points={fillPts} fill={`url(#sg-${sym})`} />
      <polyline
        points={pts}
        fill="none"
        stroke={color}
        strokeWidth="1.5"
        strokeLinejoin="round"
        strokeLinecap="round"
      />
    </svg>
  );
}

// ── Price formatter ───────────────────────────────────────────────────────────
function fmt(price: number): string {
  if (price >= 10000) return price.toLocaleString('en-US', { maximumFractionDigits: 0 });
  if (price >= 1000)  return price.toLocaleString('en-US', { maximumFractionDigits: 1 });
  if (price >= 1)     return price.toLocaleString('en-US', { maximumFractionDigits: 2 });
  return price.toLocaleString('en-US', { maximumFractionDigits: 4 });
}

// ── Ticker card ───────────────────────────────────────────────────────────────
function TickerCard({ item, price, prevPrice }: {
  item: { underlying: string; daily_change_pct?: number | null; signal_trend?: number; score_long?: number; score_short?: number };
  price: number | null;
  prevPrice: number | null;
}) {
  const sym   = item.underlying;
  const hasPrice = price != null && price > 0;
  const chg   = item.daily_change_pct ?? null;
  const isUp  = chg != null ? chg >= 0 : (price != null && prevPrice != null ? price > prevPrice : true);
  const color = !hasPrice ? 'var(--t-dim)' : isUp ? '#10B981' : '#EF4444';
  const chgStr = chg != null ? `${chg >= 0 ? '+' : ''}${chg.toFixed(2)}%` : null;

  // Compute hourly drift from local history as "LAST HOUR" proxy
  const hist = _history.get(sym) ?? [];
  const oldest = hist.length > 1 ? hist[0] : null;
  const hourlyPct = oldest && oldest > 0 && hasPrice
    ? ((price! - oldest) / oldest) * 100
    : null;
  const hourlyColor = hourlyPct == null ? 'var(--t-dim)' : hourlyPct >= 0 ? '#10B981' : '#EF4444';
  const hourlyStr   = hourlyPct != null ? `${hourlyPct >= 0 ? '+' : ''}${hourlyPct.toFixed(2)}%` : '—';

  // Tick flash ref
  const flashRef = useRef<HTMLSpanElement>(null);
  const prevRef  = useRef<number | null>(prevPrice);
  useEffect(() => {
    if (!flashRef.current) return;
    if (prevRef.current != null && price != null && prevRef.current !== price) {
      const cls = price > prevRef.current ? 'price-flash-up' : 'price-flash-down';
      flashRef.current.classList.remove('price-flash-up', 'price-flash-down');
      void flashRef.current.offsetWidth; // reflow
      flashRef.current.classList.add(cls);
    }
    prevRef.current = price;
  }, [price]);

  return (
    <div style={{
      display: 'flex',
      alignItems: 'center',
      gap: 8,
      background: 'var(--t-bg3)',
      border: '1px solid var(--t-border)',
      borderRadius: 8,
      padding: '7px 10px',
      width: 210,
      flexShrink: 0,
      position: 'relative',
      overflow: 'hidden',
    }}>
      {/* Subtle accent glow */}
      <div style={{
        position: 'absolute', top: 0, left: 0, right: 0, height: 1,
        background: `linear-gradient(90deg, transparent, ${color}40, transparent)`,
      }} />

      {/* Left: icon + name */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: 6, flexShrink: 0 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 7 }}>
          <CoinIcon sym={sym} />
          <span style={{
            fontSize: 13, fontWeight: 800, color: 'var(--t-bright)',
            letterSpacing: '0.04em',
          }}>
            {sym}
          </span>
        </div>
        {/* Price row */}
        <div style={{ display: 'flex', alignItems: 'baseline', gap: 5 }}>
          <span style={{ fontSize: 8, color: 'var(--t-dim)', letterSpacing: '0.04em' }}>{sym}</span>
          <span
            ref={flashRef}
            style={{
              fontSize: 11, fontWeight: 700, color, fontVariantNumeric: 'tabular-nums',
              letterSpacing: '-0.01em',
            }}
          >
            {hasPrice ? `$${fmt(price!)}` : 'no data'}
          </span>
          {hasPrice && chgStr && (
            <span style={{ fontSize: 9, color, fontVariantNumeric: 'tabular-nums' }}>
              {chgStr}
            </span>
          )}
        </div>
      </div>

      {/* Middle: sparkline */}
      <div style={{ flex: 1, display: 'flex', justifyContent: 'center', minWidth: 0 }}>
        <Sparkline sym={sym} color={color} />
      </div>

      {/* Right: last hour stat */}
      <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-end', gap: 2, flexShrink: 0 }}>
        <span style={{
          fontSize: 7, fontWeight: 700, letterSpacing: '0.12em',
          color: 'var(--t-dim)',
        }}>
          LAST HOUR
        </span>
        <span style={{
          fontSize: 13, fontWeight: 800, color: hourlyColor,
          fontVariantNumeric: 'tabular-nums', letterSpacing: '-0.01em',
        }}>
          {hourlyStr}
        </span>
        <span style={{ fontSize: 7, color: 'var(--t-dim)', letterSpacing: '0.06em' }}>
          {/* Score as a proxy for momentum */}
          {item.score_long != null
            ? `SCORE ${Math.round(Math.max(item.score_long, item.score_short ?? 0))}`
            : ''}
        </span>
      </div>
    </div>
  );
}

// ── Main component ────────────────────────────────────────────────────────────
export function TickerStrip() {
  const { data }  = useWatchlist();
  const liveP     = useLivePrices();
  const cfgQ      = useScalpingConfig();
  const prevPriceRef = useRef<Record<string, number>>({});
  const outerRef  = useRef<HTMLDivElement>(null);
  const copyRef   = useRef<HTMLDivElement>(null);
  const [overflow, setOverflow] = useState(false);
  const [shift, setShift] = useState(0);

  const items = data?.items ?? [];

  // Build display list: watchlist items preferred, SSE fallback
  const symSet = new Set(items.map(i => i.underlying));
  const liveOnlySyms = Object.keys(liveP).filter(s => !symSet.has(s));

  let displayItems = [
    ...items,
    ...liveOnlySyms.map(s => ({ underlying: s })),
  ] as typeof items;

  // Sync with the Scalping symbol selection: when specific symbols are chosen
  // in settings, the top row shows exactly those (empty list = "ALL"). Every
  // selected symbol is shown in selection order — even ones with no market
  // data yet (rendered as a "no data" card) so the count always matches.
  const selectedSyms = cfgQ.data?.config?.symbols ?? [];
  const hasSelection = selectedSyms.length > 0;
  if (hasSelection) {
    const bySym = new Map(displayItems.map(i => [i.underlying.toUpperCase(), i]));
    displayItems = selectedSyms.map(
      s => bySym.get(s.toUpperCase()) ?? ({ underlying: s.toUpperCase() } as typeof items[number]),
    );
  }

  // Update price history on every price tick
  useEffect(() => {
    for (const [sym, price] of Object.entries(liveP)) {
      if (price > 0) pushPrice(sym, price);
    }
  }, [liveP]);

  // Marquee: scroll only when the row is wider than the bar. Re-measures on
  // resize and whenever card count/width changes (ResizeObserver covers both).
  useLayoutEffect(() => {
    const outer = outerRef.current;
    const copy = copyRef.current;
    if (!outer || !copy) return;
    const measure = () => {
      const copyW = copy.scrollWidth;
      const avail = outer.clientWidth - 40; // minus the 20px horizontal padding each side
      const over = copyW > 0 && copyW > avail;
      setOverflow(over);
      setShift(over ? copyW + 8 : 0); // one copy width + inter-copy gap
    };
    measure();
    const ro = new ResizeObserver(measure);
    ro.observe(outer);
    ro.observe(copy);
    return () => ro.disconnect();
  }, [displayItems.length]);

  if (displayItems.length === 0) {
    return (
      <div style={{
        height: 56,
        background: 'var(--t-bg2)',
        borderBottom: '1px solid var(--t-border)',
        display: 'flex', alignItems: 'center',
        padding: '0 16px', flexShrink: 0,
      }}>
        <span style={{ color: 'var(--t-dim)', fontSize: 11 }}>Loading market data…</span>
      </div>
    );
  }

  const cards = displayItems.map(item => {
    const raw = liveP[item.underlying] ?? item.spot_price ?? null;
    const price = raw && raw > 0 ? raw : null;
    // In ALL mode, hide symbols that have no price; when symbols are
    // explicitly selected, always show them (placeholder card if no data).
    if (price == null && !hasSelection) return null;
    const prev = price != null ? (prevPriceRef.current[item.underlying] ?? null) : null;
    if (price != null) prevPriceRef.current[item.underlying] = price;
    return (
      <TickerCard key={item.underlying} item={item} price={price} prevPrice={prev} />
    );
  }).filter(Boolean);

  const GAP = 8;
  const duration = Math.min(120, Math.max(12, shift / 45)); // ~45px/sec, like a news crawl
  return (
    <div ref={outerRef} style={{
      background: 'var(--t-bg2)',
      borderBottom: '1px solid var(--t-border)',
      padding: '6px 20px',
      flexShrink: 0,
      overflow: 'hidden',
    }}>
      <div
        className={overflow ? 'ticker-marquee' : undefined}
        style={{
          display: 'flex', alignItems: 'center', gap: GAP, width: 'max-content',
          ...(overflow
            ? { ['--ticker-shift' as string]: `${shift}px`, animationDuration: `${duration}s` }
            : {}),
        } as React.CSSProperties}
      >
        <div ref={copyRef} style={{ display: 'flex', alignItems: 'center', gap: GAP }}>
          {cards}
        </div>
        {overflow && (
          <div aria-hidden style={{ display: 'flex', alignItems: 'center', gap: GAP }}>
            {cards}
          </div>
        )}
      </div>
    </div>
  );
}
