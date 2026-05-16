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

    const scoreClass = score >= 80 ? 'high' : score >= 60 ? 'mid' : 'low';
    return (
      <span
        key={sym + keySuffix}
        className="sym-ticker-item"
      >
        {/* Direction arrow */}
        <span style={{ color: trendColor, fontSize: 10, fontWeight: 700, fontFamily: 'JetBrains Mono, monospace', width: 10, flexShrink: 0 }}>{trendArrow}</span>
        {/* Symbol */}
        <span style={{ color: 'var(--t-bright)', fontWeight: 800, fontSize: 12, letterSpacing: 0.8, fontFamily: 'JetBrains Mono, monospace' }}>
          {sym}
        </span>
        {/* Live price */}
        {price != null && (
          <span style={{ color: price != null ? trendColor : 'var(--t-dim)', fontSize: 12, fontFamily: 'JetBrains Mono, monospace', fontWeight: 600, fontVariantNumeric: 'tabular-nums' }}>
            ${fmtP(price)}
          </span>
        )}
        {/* Regime badge */}
        {regime && regime !== 'IDLE' && (
          <span style={{
            fontSize: 9, fontWeight: 700, padding: '1px 5px', borderRadius: 2,
            background: regimeColor + '18', color: regimeColor,
            fontFamily: 'JetBrains Mono, monospace', letterSpacing: '0.05em',
            border: `1px solid ${regimeColor}33`,
          }}>
            {regime.replace(/_/g, ' ')}
          </span>
        )}
        {/* Score badge */}
        {score >= 60 && (
          <span className={`score-badge ${scoreClass}`}>{score}</span>
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
