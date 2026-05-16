import React, { useRef } from 'react';
import { useWatchlist } from '../hooks/useWatchlist';
import { useLivePrices } from '../hooks/useLivePrices';

const REGIME_COLOR: Record<string, string> = {
  BULL_TREND: '#00c87a', BEAR_TREND: '#f03050',
  VOLATILE: '#f0a020', RANGING: '#4a5a6a', IDLE: '#4a5a6a',
};

function fmtP(p: number) {
  return p >= 1000
    ? p.toLocaleString('en-US', { maximumFractionDigits: 0 })
    : p.toLocaleString('en-US', { maximumFractionDigits: 3 });
}

export function AllSymbolsTicker() {
  const { data } = useWatchlist();
  const liveP = useLivePrices();
  const ref = useRef<HTMLDivElement>(null);

  const items = data?.items ?? [];
  if (items.length === 0 && Object.keys(liveP).length === 0) {
    return (
      <div style={{ height: 28, background: 'var(--t-bg3)', borderBottom: '1px solid var(--t-border)',
        display: 'flex', alignItems: 'center', padding: '0 12px' }}>
        <span style={{ color: 'var(--t-dim)', fontSize: 10 }}>Loading signal data…</span>
      </div>
    );
  }

  // Build display items: watchlist items supplemented with SSE live prices
  const display = items.length > 0 ? items : Object.keys(liveP).map(sym => ({ underlying: sym } as any));

  const renderItem = (item: typeof items[0], keySuffix = '') => {
    const sym = item.underlying;
    const price = liveP[sym] ?? item.spot_price ?? null;
    const regime = (item as any).macro_regime as string | undefined;
    const regimeColor = REGIME_COLOR[regime ?? ''] ?? '#4a5a6a';
    const scoreL = item.score_long ?? 0;
    const scoreS = item.score_short ?? 0;
    const score = Math.max(scoreL, scoreS);
    const scoreColor = score >= 85 ? '#00c87a' : score >= 75 ? '#f0a020' : '#4a5a6a';
    const trend = item.signal_trend ?? 0;
    const trendColor = trend > 0 ? '#00c87a' : trend < 0 ? '#f03050' : '#4a5a6a';
    const trendArrow = trend > 0 ? '▲' : trend < 0 ? '▼' : '◆';

    return (
      <span
        key={sym + keySuffix}
        style={{
          display: 'inline-flex', alignItems: 'center', gap: 5,
          padding: '0 14px', borderRight: '1px solid var(--t-border)',
          flexShrink: 0, height: '100%',
        }}
      >
        {/* Symbol */}
        <span style={{ color: 'var(--t-bright)', fontWeight: 700, fontSize: 11, letterSpacing: 0.5, fontFamily: 'JetBrains Mono, monospace' }}>
          {sym}
        </span>
        {/* Live price */}
        {price != null && (
          <span style={{ color: trendColor, fontSize: 11, fontFamily: 'JetBrains Mono, monospace' }}>
            ${fmtP(price)}
          </span>
        )}
        {/* Direction arrow */}
        <span style={{ color: trendColor, fontSize: 9 }}>{trendArrow}</span>
        {/* Regime badge */}
        {regime && (
          <span style={{
            fontSize: 9, fontWeight: 700, padding: '0px 5px', borderRadius: 2,
            background: regimeColor + '22', color: regimeColor,
            fontFamily: 'JetBrains Mono, monospace', letterSpacing: '0.04em',
          }}>
            {regime.replace(/_/g, ' ')}
          </span>
        )}
        {/* Score */}
        {score > 0 && (
          <span style={{ fontSize: 9, color: scoreColor, fontFamily: 'JetBrains Mono, monospace', fontWeight: 700 }}>
            {score}
          </span>
        )}
      </span>
    );
  };

  const shouldScroll = display.length > 2;

  return (
    <div
      style={{
        height: 28,
        background: 'var(--t-bg3)',
        borderBottom: '1px solid var(--t-border)',
        overflow: 'hidden',
        display: 'flex',
        alignItems: 'stretch',
        flexShrink: 0,
        position: 'relative',
      }}
      onMouseEnter={() => { if (ref.current) ref.current.style.animationPlayState = 'paused'; }}
      onMouseLeave={() => { if (ref.current) ref.current.style.animationPlayState = 'running'; }}
    >
      {/* Left fade edge */}
      <div style={{
        position: 'absolute', left: 0, top: 0, bottom: 0, width: 20, zIndex: 1,
        background: 'linear-gradient(to right, var(--t-bg3), transparent)',
        pointerEvents: 'none',
      }} />
      <div
        ref={ref}
        style={{
          display: 'inline-flex',
          alignItems: 'stretch',
          whiteSpace: 'nowrap',
          animation: shouldScroll ? 'ticker-move 45s linear infinite' : undefined,
        }}
      >
        {display.map(i => renderItem(i as typeof items[0], ''))}
        {/* duplicate for seamless loop */}
        {shouldScroll && display.map(i => renderItem(i as typeof items[0], '_2'))}
      </div>
      {/* Right fade edge */}
      <div style={{
        position: 'absolute', right: 0, top: 0, bottom: 0, width: 20, zIndex: 1,
        background: 'linear-gradient(to left, var(--t-bg3), transparent)',
        pointerEvents: 'none',
      }} />
    </div>
  );
}
