import React, { useEffect, useLayoutEffect, useRef, useState } from 'react';
import { useKiteWatchlist, useKiteLtp } from '../../hooks/useKite';
import { parseTradingsymbol } from '../../utils/fmt';
const SEG_COLORS: Record<string, string> = {
  NSE: '#10B981', NFO: '#8B5CF6', BFO: '#8B5CF6',
  BSE: '#06B6D4', MCX: '#F59E0B', CDS: '#10B981',
};

function segColor(sym: string): string {
  const seg = (sym.split(':')[0] || '').toUpperCase();
  return SEG_COLORS[seg] || 'var(--t-dim)';
}



function KiteCard({ sym, name, ltp, prevRef }: {
  sym: string;
  name: string;
  ltp: number | undefined;
  prevRef: React.MutableRefObject<Record<string, number>>;
}) {
  const flashRef = useRef<HTMLSpanElement>(null);
  const prev = ltp != null ? (prevRef.current[sym] ?? null) : null;
  const hasPrice = ltp != null && ltp > 0;
  const color = hasPrice ? segColor(sym) : 'var(--t-dim)';
  const isUp = !hasPrice ? true : prev == null ? true : ltp! >= prev;
  const chgColor = hasPrice ? (isUp ? '#10B981' : '#EF4444') : 'var(--t-dim)';

  useEffect(() => {
    if (!flashRef.current || !hasPrice || prev == null) return;
    if (ltp !== prev) {
      const cls = ltp! > prev ? 'price-flash-up' : 'price-flash-down';
      flashRef.current.classList.remove('price-flash-up', 'price-flash-down');
      void flashRef.current.offsetWidth;
      flashRef.current.classList.add(cls);
    }
    if (ltp != null) prevRef.current[sym] = ltp;
  }, [ltp]);

  if (ltp != null) prevRef.current[sym] = ltp;

  const segments = sym.split(':');
  const exch = segments[0] || '';
  const rawTs = segments.slice(1).join(':') || sym;
  const displayLabel = parseTradingsymbol(rawTs);

  return (
    <div style={{
      display: 'flex', alignItems: 'center', gap: 8,
      background: 'var(--t-bg3)', border: '1px solid var(--t-border)',
      borderRadius: 8, padding: '7px 10px', width: 210, flexShrink: 0,
      position: 'relative', overflow: 'hidden',
    }}>
      <div style={{
        position: 'absolute', top: 0, left: 0, right: 0, height: 1,
        background: `linear-gradient(90deg, transparent, ${color}40, transparent)`,
      }} />
      <div style={{ display: 'flex', flexDirection: 'column', gap: 6, flexShrink: 0, minWidth: 0 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 7 }}>
          <span style={{
            background: color, color: '#fff', fontSize: 9, fontWeight: 800,
            width: 28, height: 28, borderRadius: '50%', display: 'flex',
            alignItems: 'center', justifyContent: 'center', flexShrink: 0,
          }}>
            {exch.slice(0, 2)}
          </span>
          <span style={{
            fontSize: 13, fontWeight: 800, color: 'var(--t-bright)',
            letterSpacing: '0.04em', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
          }}>
            {displayLabel}
          </span>
        </div>
        <div style={{ display: 'flex', alignItems: 'baseline', gap: 5 }}>
          <span style={{ fontSize: 8, color: 'var(--t-dim)', letterSpacing: '0.04em' }}>{exch}</span>
          <span ref={flashRef} style={{
            fontSize: 11, fontWeight: 700, color: chgColor,
            fontVariantNumeric: 'tabular-nums', letterSpacing: '-0.01em',
          }}>
            {hasPrice ? `₹${ltp!.toLocaleString('en-IN')}` : 'no data'}
          </span>
        </div>
      </div>
    </div>
  );
}

export function KiteTicker() {
  const { items } = useKiteWatchlist();
  const symbols = items.map((w) => w.symbol);
  const { data: ltp } = useKiteLtp(symbols, symbols.length > 0);
  const prevRef = useRef<Record<string, number>>({});
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
        height: 56, background: 'var(--t-bg2)', borderBottom: '1px solid var(--t-border)',
        display: 'flex', alignItems: 'center', padding: '0 20px', flexShrink: 0,
      }}>
        <span style={{ color: 'var(--t-dim)', fontSize: 11 }}>
          Kite watchlist empty — search &amp; add instruments from Market Watch tab
        </span>
      </div>
    );
  }

  const cards = items.map((w) => {
    const p = ltp?.[w.symbol]?.last_price;
    return <KiteCard key={w.symbol} sym={w.symbol} name={w.name || w.symbol} ltp={p} prevRef={prevRef} />;
  });

  const GAP = 8;
  const duration = Math.min(120, Math.max(12, shift / 45));

  return (
    <div ref={outerRef} style={{
      background: 'var(--t-bg2)', borderBottom: '1px solid var(--t-border)',
      padding: '6px 20px', flexShrink: 0, overflow: 'hidden',
    }}>
      <div
        className={overflow ? 'ticker-marquee' : undefined}
        style={{
          display: 'flex', alignItems: 'center', gap: GAP, width: 'max-content',
          ...(overflow ? { ['--ticker-shift' as string]: `${shift}px`, animationDuration: `${duration}s` } : {}),
        } as React.CSSProperties}
      >
        <div ref={copyRef} style={{ display: 'flex', alignItems: 'center', gap: GAP }}>{cards}</div>
        {overflow && <div aria-hidden style={{ display: 'flex', alignItems: 'center', gap: GAP }}>{cards}</div>}
      </div>
    </div>
  );
}
