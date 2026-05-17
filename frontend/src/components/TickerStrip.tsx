import React, { useEffect, useRef } from 'react';
import { useWatchlist } from '../hooks/useWatchlist';
import { useLivePrices } from '../hooks/useLivePrices';

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
      boxShadow: `0 0 8px ${m.bg}60`,
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
  price: number;
  prevPrice: number | null;
}) {
  const sym   = item.underlying;
  const chg   = item.daily_change_pct ?? null;
  const isUp  = chg != null ? chg >= 0 : (price > (prevPrice ?? price));
  const color = isUp ? '#10B981' : '#EF4444';
  const chgStr = chg != null ? `${chg >= 0 ? '+' : ''}${chg.toFixed(2)}%` : null;

  // Compute hourly drift from local history as "LAST HOUR" proxy
  const hist = _history.get(sym) ?? [];
  const oldest = hist.length > 1 ? hist[0] : null;
  const hourlyPct = oldest && oldest > 0 && price > 0
    ? ((price - oldest) / oldest) * 100
    : null;
  const hourlyColor = hourlyPct == null ? 'var(--t-dim)' : hourlyPct >= 0 ? '#10B981' : '#EF4444';
  const hourlyStr   = hourlyPct != null ? `${hourlyPct >= 0 ? '+' : ''}${hourlyPct.toFixed(2)}%` : '—';

  // Tick flash ref
  const flashRef = useRef<HTMLSpanElement>(null);
  const prevRef  = useRef<number | null>(prevPrice);
  useEffect(() => {
    if (!flashRef.current) return;
    if (prevRef.current != null && prevRef.current !== price) {
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
            ${fmt(price)}
          </span>
          {chgStr && (
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
  const prevPriceRef = useRef<Record<string, number>>({});

  const items = data?.items ?? [];

  // Build display list: watchlist items preferred, SSE fallback
  const symSet = new Set(items.map(i => i.underlying));
  const liveOnlySyms = Object.keys(liveP).filter(s => !symSet.has(s));

  const displayItems = [
    ...items,
    ...liveOnlySyms.map(s => ({ underlying: s })),
  ] as typeof items;

  // Update price history on every price tick
  useEffect(() => {
    for (const [sym, price] of Object.entries(liveP)) {
      if (price > 0) pushPrice(sym, price);
    }
  }, [liveP]);

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

  return (
    <div style={{
      background: 'var(--t-bg2)',
      borderBottom: '1px solid var(--t-border)',
      padding: '6px 20px',
      display: 'flex',
      alignItems: 'center',
      gap: 8,
      flexShrink: 0,
      overflowX: 'auto',
      scrollbarWidth: 'none',
    } as React.CSSProperties}>
      {displayItems.map(item => {
        const price = liveP[item.underlying] ?? item.spot_price ?? null;
        if (!price || price <= 0) return null;
        const prev = prevPriceRef.current[item.underlying] ?? null;
        prevPriceRef.current[item.underlying] = price;
        return (
          <TickerCard
            key={item.underlying}
            item={item}
            price={price}
            prevPrice={prev}
          />
        );
      })}
    </div>
  );
}
