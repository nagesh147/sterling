import React, { useState, useRef, useEffect } from 'react';
import { k, tint, Icons } from '../../styles/kiteUI';
import { useEngineDetail, useEnginePlaceOrder } from '../../hooks/useSterlingKiteEngine';
import type { DepthLevel, OptionDetail } from '../../types/kiteEngine';
import { parseTradingsymbol } from '../../utils/fmt';
import { InstrumentLabel, parseInstrument } from './InstrumentLabel';
import { useKiteQuote } from '../../hooks/useKite';
import { QuoteDetail } from './SterlingWatchList';
import { KiteActionButtons } from './KiteActionButtons';
import { useKiteSettings } from '../../store/useKiteSettings';
import { SignalImpactCalculator, PremiumBreakdown } from './SignalImpactCalculator';
import { stopDistance, computeLegRR, rrScore } from './impactMath';

import { useOrderWindowStore } from '../../store/useOrderWindowStore';

interface Props {
  token: number;
  underlying: string;
  timestamp_ms: number;
  onClose: () => void;
  onShowSetup: () => void;
  onShowOptionChain: (underlying: string) => void;
}

function ist(ms: number): string {
  const d = new Date(ms);
  const time = d.toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit', hour12: false });
  const day = d.toLocaleDateString('en-US', { weekday: 'short' });
  const date = d.toLocaleDateString('en-US', { day: '2-digit' });
  const month = d.toLocaleDateString('en-US', { month: 'short' });
  return `${time} · ${day} ${date} ${month}`;
}

// Compact stat used in the trigger-context strip; even spacing + thin dividers.
function StripStat({ label, value, color, title }: { label: string; value: string; color?: string; title?: string }) {
  return (
    <div title={title} style={{ flex: 1, minWidth: 0, display: 'flex', flexDirection: 'column', gap: 6, padding: '4px 22px', justifyContent: 'center', alignItems: 'flex-start', textAlign: 'left' }}>
      <span style={{ fontSize: 9, color: k.dim, textTransform: 'uppercase', letterSpacing: 0.6, fontWeight: 700 }}>{label}</span>
      <span style={{ fontSize: 14, fontWeight: 600, color: color ?? k.text, fontVariantNumeric: 'tabular-nums', whiteSpace: 'nowrap' }}>{value}</span>
    </div>
  );
}

function StripDiv() {
  return <div style={{ width: 1, alignSelf: 'center', height: 28, background: k.border, opacity: 0.7 }} />;
}

function LegCard({ leg, exchange, underlying, spotPx, isBest, isBestDelta }: {
  leg: OptionDetail; exchange: string;
  underlying: string;
  spotPx?: number;
  isBest?: boolean;
  isBestDelta?: boolean;
}) {
  const [showDepth, setShowDepth] = useState(false);
  const openOrderWindow = useOrderWindowStore((s) => s.openOrderWindow);
  const sym = `${exchange}:${leg.option_symbol}`;
  const { data: quotes } = useKiteQuote([sym]);
  const q = quotes?.[sym];
  const s = useKiteSettings();

  let chgAbs: number | null = null;
  let chgPct: number | null = null;
  let lastPx: number | null = null;
  let color = k.dim;

  if (q) {
    lastPx = q.last_price;
    const base = s.chgType === 'close' ? q.ohlc?.close : q.ohlc?.open;
    if (base) {
      chgAbs = q.last_price - base;
      chgPct = (chgAbs / base) * 100;
      color = s.showPriceDirection ? (chgAbs >= 0 ? k.green : k.red) : k.dim;
    } else if (q.net_change != null) {
      chgPct = q.net_change;
      color = s.showPriceDirection ? (chgPct! >= 0 ? k.green : k.red) : k.dim;
    }
  }

  const [hovered, setHovered] = useState(false);

  const handleAction = (e: React.MouseEvent, type: 'BUY' | 'SELL') => {
    e.stopPropagation();
    openOrderWindow({
      symbol: leg.option_symbol,
      exchange: exchange,
      initialSide: type,
      lotSize: leg.lot_size || 1,
      lastPrice: lastPx || 0,
    });
  };

  return (
    <div 
      style={{ borderBottom: `1px solid ${k.border}`, background: hovered || showDepth ? k.surfaceHover : 'transparent' }}
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
    >
      <div 
        className="sd-leg-row"
        onClick={() => setShowDepth(!showDepth)}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: 12, minWidth: 0, paddingRight: 8, flex: 1 }}>
          <span style={{ fontSize: 10, padding: '2px 6px', background: tint(k.orange, 10), color: k.orange, borderRadius: 2, fontWeight: 700 }}>{leg.moneyness}</span>
          <span style={{ fontSize: 12, color: color, fontWeight: 400, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}><InstrumentLabel symbol={`${exchange}:${leg.option_symbol}`} /></span>
          {isBest && (
            <span title="Best reward-to-risk among these strikes for a 1R move"
              style={{ fontSize: 13, fontWeight: 700, color: k.blue, flexShrink: 0 }}>
              ✝
            </span>
          )}
          {isBestDelta && (
            <span title="Highest delta — most responsive to the underlying (moves nearest 1:1 with spot)"
              style={{ fontSize: 13, fontWeight: 700, color: k.blue, flexShrink: 0 }}>
              ▲
            </span>
          )}
        </div>
        
        {!showDepth && (
          <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
            <div className="sd-prices">
              {s.showPriceChange && <span style={{ color: k.dim, fontSize: 11 }}>{chgAbs != null ? chgAbs.toFixed(2) : '—'}</span>}
              {s.showPriceChangePct && <span style={{ color: k.text, fontSize: 11, marginLeft: 4 }}>{chgPct != null ? `${chgPct.toFixed(2)}%` : '—'}</span>}
              {s.showPriceDirection && (
                <span style={{ color: color, display: 'flex', alignItems: 'center', marginTop: 1, margin: '0 2px' }}>
                  {chgAbs != null && chgAbs !== 0 ? (chgAbs > 0 ? <Icons.ChevronUp /> : <Icons.ChevronDown />) : null}
                  {chgAbs === 0 && <span style={{fontSize:14, padding:'0 2px', lineHeight:1}}>∘</span>}
                </span>
              )}
              <span style={{ color: color, fontWeight: 500, fontSize: 13, minWidth: 50, textAlign: 'right' }}>
                {lastPx != null ? lastPx.toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 }) : '—'}
              </span>
            </div>
            
            <KiteActionButtons
              className="sd-actions"
              variant="long"
              onBuy={(e) => handleAction(e, 'BUY')}
              onSell={(e) => handleAction(e, 'SELL')}
              onChart={(e) => { e.stopPropagation(); }}
              onMore={(e) => { e.stopPropagation(); }}
            />
          </div>
        )}
      </div>

      {showDepth && (
        <div style={{ display: 'flex', flexDirection: 'column', borderTop: `1px solid ${k.border}`, background: k.bg }}>
          <div style={{ display: 'flex' }}>
            <div style={{ flex: 1, minWidth: 0 }} onClick={(e) => e.stopPropagation()}>
              <QuoteDetail 
                  sym={sym} 
                  q={q} 
                  expiry={parseInstrument(leg.option_symbol) ? `${parseInstrument(leg.option_symbol)!.day ? parseInstrument(leg.option_symbol)!.day + ' ' : ''}${parseInstrument(leg.option_symbol)!.month} 20${parseInstrument(leg.option_symbol)!.year}` : ''}
                  spotName={underlying}
                  spotPx={spotPx}
                  instrumentName={<InstrumentLabel symbol={leg.option_symbol} />} 
                  hideHeaderAndActions={false} 
                  onBuy={() => handleAction({ stopPropagation: () => {} } as React.MouseEvent, 'BUY')}
                  onSell={() => handleAction({ stopPropagation: () => {} } as React.MouseEvent, 'SELL')}
                  greeks={leg}
                />
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

// A detail section that can be collapsed (click the header) and reordered
// (press-and-drag the header). Dragging is handled by the parent via pointer
// events so the lifted card stays pinned to the cursor and the list auto-scrolls;
// a small movement threshold lets a plain click still toggle collapse.
function CollapsibleCard({ id, title, collapsed, dragging, dragOffset, onHeaderPointerDown, children }: {
  id: string;
  title: string;
  collapsed: boolean;
  dragging: boolean;
  dragOffset: { x: number; y: number };
  onHeaderPointerDown: (e: React.PointerEvent) => void;
  children: React.ReactNode;
}) {
  return (
    <div
      data-sec={id}
      style={{
        marginTop: 12,
        border: `1px solid ${dragging ? k.text : k.border}`,
        borderRadius: 10,
        overflow: 'hidden',
        background: k.bg,
        position: 'relative',
        transform: dragging ? `translate(${dragOffset.x}px, ${dragOffset.y}px)` : undefined,
        boxShadow: dragging ? '0 14px 34px rgba(0,0,0,0.5)' : undefined,
        opacity: dragging ? 0.97 : 1,
        zIndex: dragging ? 50 : undefined,
        transition: dragging ? 'none' : 'box-shadow .15s',
        willChange: dragging ? 'transform' : undefined,
      }}
    >
      <div
        onPointerDown={onHeaderPointerDown}
        title={collapsed ? 'Expand · drag to reorder' : 'Collapse · drag to reorder'}
        style={{ display: 'flex', alignItems: 'center', gap: 10, padding: '12px 16px', cursor: dragging ? 'grabbing' : 'grab', userSelect: 'none', touchAction: 'none', background: k.bg, borderBottom: collapsed ? 'none' : `1px solid ${k.border}` }}
      >
        <span style={{ fontSize: 11, fontWeight: 700, color: k.dim, letterSpacing: 0.5, textTransform: 'uppercase' }}>{title}</span>
      </div>
      {!collapsed && children}
    </div>
  );
}

export function SignalDetailPane({ token, underlying, timestamp_ms, onClose, onShowSetup, onShowOptionChain }: Props) {
  const { data, isLoading, isError, dataUpdatedAt } = useEngineDetail(token, timestamp_ms, true);
  const openOrderWindow = useOrderWindowStore((s) => s.openOrderWindow);
  const [pinned, setPinned] = useState<boolean>(() => {
    try { return JSON.parse(localStorage.getItem('kite_engine_pins') || '[]').includes(token); } catch { return false; }
  });

  const togglePin = () => {
    try {
      const cur: number[] = JSON.parse(localStorage.getItem('kite_engine_pins') || '[]');
      const next = pinned ? cur.filter((t) => t !== token) : [...cur, token];
      localStorage.setItem('kite_engine_pins', JSON.stringify(next));
      setPinned(!pinned);
    } catch { /* ignore */ }
  };

  // Collapsible + reorderable detail sections (order + collapsed state persisted).
  const [sectionOrder, setSectionOrder] = useState<string[]>(() => {
    try {
      const saved = JSON.parse(localStorage.getItem('kite_detail_section_order') || 'null');
      if (Array.isArray(saved) && saved.length === 3 && ['calculator', 'breakdown', 'legs'].every((x) => saved.includes(x))) return saved;
    } catch { /* ignore */ }
    return ['calculator', 'breakdown', 'legs'];
  });
  const [sectionCollapsed, setSectionCollapsed] = useState<Record<string, boolean>>(() => {
    try { return JSON.parse(localStorage.getItem('kite_detail_section_collapsed') || '{}'); } catch { return {}; }
  });
  useEffect(() => { localStorage.setItem('kite_detail_section_order', JSON.stringify(sectionOrder)); }, [sectionOrder]);
  useEffect(() => { localStorage.setItem('kite_detail_section_collapsed', JSON.stringify(sectionCollapsed)); }, [sectionCollapsed]);
  const toggleSection = (id: string) => setSectionCollapsed((c) => ({ ...c, [id]: !c[id] }));

  // Pointer-driven reorder: the picked-up card lifts and tracks the cursor
  // (up/down + sideways), the list auto-scrolls when the cursor nears an edge so
  // off-screen sections come into reach, and a thin guide marks where it will land.
  const scrollRef = useRef<HTMLDivElement>(null);
  const [dragId, setDragId] = useState<string | null>(null);
  const [dragOffset, setDragOffset] = useState<{ x: number; y: number }>({ x: 0, y: 0 });
  const [dropIndex, setDropIndex] = useState<number | null>(null);
  const drag = useRef<
    { id: string; px0: number; py0: number; px: number; py: number; sTop0: number; moved: boolean; raf: number | null; dropIndex: number | null } | null
  >(null);

  // Where the dragged card would land, based on the cursor vs each slot midpoint.
  const computeDropIndex = (clientY: number): number => {
    const sc = scrollRef.current;
    if (!sc) return 0;
    const els = Array.from(sc.querySelectorAll('[data-sec]')) as HTMLElement[];
    for (let i = 0; i < els.length; i++) {
      const r = els[i].getBoundingClientRect();
      if (clientY < r.top + r.height / 2) return i;
    }
    return els.length;
  };

  // Per-frame loop while dragging: auto-scroll near edges, keep the card pinned to
  // the cursor (compensating for any scroll), and refresh the drop guide.
  const tick = () => {
    const d = drag.current;
    const sc = scrollRef.current;
    if (!d || !sc) return;
    const r = sc.getBoundingClientRect();
    const EDGE = 56, SPEED = 14;
    if (d.py < r.top + EDGE) sc.scrollTop = Math.max(0, sc.scrollTop - SPEED);
    else if (d.py > r.bottom - EDGE) sc.scrollTop = Math.min(sc.scrollHeight - sc.clientHeight, sc.scrollTop + SPEED);
    const di = computeDropIndex(d.py);
    d.dropIndex = di;
    setDragOffset({ x: d.px - d.px0, y: (d.py - d.py0) + (sc.scrollTop - d.sTop0) });
    setDropIndex(di);
    d.raf = requestAnimationFrame(tick);
  };

  const endDrag = () => {
    const d = drag.current;
    if (!d) return;
    if (d.raf) cancelAnimationFrame(d.raf);
    if (!d.moved) {
      toggleSection(d.id); // never crossed the threshold → treat as a click
    } else if (d.dropIndex != null) {
      const di = d.dropIndex;
      setSectionOrder((order) => {
        const without = order.filter((x) => x !== d.id);
        const origIdx = order.indexOf(d.id);
        let insert = di > origIdx ? di - 1 : di;
        insert = Math.max(0, Math.min(without.length, insert));
        without.splice(insert, 0, d.id);
        return without;
      });
    }
    drag.current = null;
    setDragId(null);
    setDragOffset({ x: 0, y: 0 });
    setDropIndex(null);
  };

  const startDrag = (id: string) => (e: React.PointerEvent) => {
    if (e.button !== 0) return;
    const sc = scrollRef.current;
    const ac = new AbortController();
    drag.current = { id, px0: e.clientX, py0: e.clientY, px: e.clientX, py: e.clientY, sTop0: sc ? sc.scrollTop : 0, moved: false, raf: null, dropIndex: null };
    const onMove = (ev: PointerEvent) => {
      const d = drag.current;
      if (!d) return;
      d.px = ev.clientX;
      d.py = ev.clientY;
      if (!d.moved && Math.abs(ev.clientX - d.px0) + Math.abs(ev.clientY - d.py0) > 4) {
        d.moved = true;
        setDragId(d.id);
        d.raf = requestAnimationFrame(tick);
      }
      if (d.moved) ev.preventDefault();
    };
    const onUp = () => { ac.abort(); endDrag(); };
    window.addEventListener('pointermove', onMove, { signal: ac.signal });
    window.addEventListener('pointerup', onUp, { signal: ac.signal });
  };

  const uExch = data?.exchange === 'BFO' ? 'BSE' : 'NSE';
  const { data: quotes } = useKiteQuote(data ? [`${uExch}:${underlying}`] : [], !!data);
  const uQ = data ? quotes?.[`${uExch}:${underlying}`] : undefined;

  const bull = data?.regime === 'BULL';
  const move = (data && data.spot_at_trigger > 0 && data.spot_now > 0) ? data.spot_now - data.spot_at_trigger : null;

  return (
    <div ref={scrollRef} style={{ display: 'flex', flexDirection: 'column', height: '100%', background: k.bg, fontFamily: k.fontFamily, overflow: 'auto', scrollbarGutter: 'stable' }}>
      <style>{`
        .sd-leg-row {
          position: relative;
          display: flex;
          justify-content: space-between;
          align-items: center;
          padding: 0 18px;
          height: 41px;
          cursor: pointer;
          box-sizing: border-box;
        }
        .sd-actions {
          display: flex;
          gap: 8px;
          align-items: center;
        }
        .sd-prices {
          display: flex;
          align-items: center;
          gap: 2px;
          flex-shrink: 0;
          justify-content: flex-end;
        }
      `}</style>
      <div style={{ display: 'flex', alignItems: 'center', gap: 14, padding: '12px 16px', borderBottom: `1px solid ${k.border}`, position: 'sticky', top: 0, background: k.bg, zIndex: 1 }}>
        <button onClick={onClose} style={{ border: 'none', background: 'transparent', cursor: 'pointer', padding: 4, display: 'flex', alignItems: 'center', color: k.text }}>
          <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><line x1="19" y1="12" x2="5" y2="12"></line><polyline points="12 19 5 12 12 5"></polyline></svg>
        </button>
        
        <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
          <span style={{ fontSize: 15, fontWeight: 600, color: k.text }}>{underlying}</span>

          {(() => {
            const last = uQ?.last_price ?? (data?.spot_now || null);
            if (last == null) return null;
            const base = uQ?.ohlc?.close;
            const abs = uQ?.net_change ?? (base ? last - base : null);
            const pct = uQ?.pct_change ?? (abs != null && base ? (abs / base) * 100 : null);
            const col = abs == null ? k.text : abs >= 0 ? k.green : k.red;
            return (
              <div style={{ display: 'flex', alignItems: 'baseline', gap: 5, fontSize: 13 }}>
                <span style={{ fontWeight: 500, color: col }}>{last.toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}</span>
                {abs != null && <span style={{ fontSize: 12, color: col }}>{abs >= 0 ? '+' : ''}{abs.toFixed(2)}</span>}
                {pct != null && <span style={{ fontSize: 12, color: col }}>({pct >= 0 ? '+' : ''}{pct.toFixed(2)}%)</span>}
              </div>
            );
          })()}

        </div>

        <div style={{ marginLeft: 'auto', display: 'flex', gap: 8 }}>
          <button onClick={onShowSetup} style={{ fontSize: 12, color: k.text, background: 'none', border: `1px solid ${k.border}`, borderRadius: 4, padding: '4px 10px', cursor: 'pointer' }}>📈 Setup chart</button>
          <button onClick={() => onShowOptionChain(underlying)} style={{ fontSize: 12, color: k.text, background: 'none', border: `1px solid ${k.border}`, borderRadius: 4, padding: '4px 10px', cursor: 'pointer' }}>Option chain</button>
        </div>
      </div>

      {isLoading && <div style={{ padding: 32, color: k.dim }}>Loading detail…</div>}
      {isError && <div style={{ padding: 32, color: k.red }}>No live detail (signal may have aged out of the latest scan, or market is closed).</div>}

      {data && (
        <div style={{ padding: 20 }}>
          {/* trigger context — compact inline strip with separators */}
          {(() => {
            const trigSpot = data.spot_at_trigger > 0 ? data.spot_at_trigger : null;
            // Move is only meaningful when we have both prices; if trigger spot
            // was never captured don't compute a misleading delta.
            const realMove = (trigSpot != null && data.spot_now > 0) ? data.spot_now - trigSpot : null;
            const movePct  = (trigSpot != null && realMove != null && trigSpot > 0) ? (realMove / trigSpot) * 100 : null;
            const moveColor = realMove != null ? (realMove >= 0 ? k.green : k.red) : k.dim;
            const moveLabel = realMove != null
              ? `${realMove >= 0 ? '+' : ''}${realMove.toFixed(2)}${movePct != null ? `  (${realMove >= 0 ? '+' : ''}${movePct.toFixed(2)}%)` : ''}`
              : 'n/a';
            return (
              <div style={{ display: 'flex', alignItems: 'stretch', flexWrap: 'wrap', gap: 0, padding: '16px 8px', background: k.bg, borderRadius: 10, marginBottom: 16, border: `1px solid ${k.border}` }}>
                <StripStat label="Triggered" value={ist(data.triggered_ms)} />
                <StripDiv />
                <StripStat label="Spot @ trigger"
                  value={trigSpot != null ? trigSpot.toFixed(2) : 'not captured'}
                  title={trigSpot == null ? 'Trigger-time spot was not recorded for this signal' : undefined} />
                <StripDiv />
                <StripStat label="Spot now" value={data.spot_now ? data.spot_now.toFixed(2) : '—'} color={moveColor} />
                <StripDiv />
                <StripStat label="Move since" value={moveLabel} color={moveColor} />
                {data?.alignment && (
                  <>
                    <StripDiv />
                    <StripStat label="ST align F/M/S" value={`${data.alignment.fast}/${data.alignment.mid}/${data.alignment.slow}`} title="Current SuperTrend alignment at trigger (+1 green / -1 red)" />
                  </>
                )}
              </div>
            );
          })()}

          {/* Collapsible + reorderable detail sections (press-drag a header to reorder). */}
          {sectionOrder.map((id, i) => {
            const cardProps = {
              id,
              collapsed: !!sectionCollapsed[id],
              dragging: dragId === id,
              dragOffset,
              onHeaderPointerDown: startDrag(id),
            };
            const guide = dragId && dropIndex === i
              ? <div key={`guide-${id}`} style={{ height: 2, background: k.green, borderRadius: 2, marginTop: 12 }} />
              : null;
            let card: React.ReactNode;
            if (id === 'calculator') {
              card = (
                <CollapsibleCard key={id} title="Trade Impact Calculator" {...cardProps}>
                  <SignalImpactCalculator
                    headless
                    data={data}
                    updatedAt={dataUpdatedAt}
                    onBuy={(leg) => openOrderWindow({
                      symbol: leg.option_symbol,
                      exchange: data.exchange,
                      initialSide: 'BUY',
                      lotSize: leg.lot_size || 1,
                      lastPrice: leg.last_price || 0,
                    })}
                  />
                </CollapsibleCard>
              );
            } else if (id === 'breakdown') {
              card = (
                <CollapsibleCard key={id} title="Premium breakdown" {...cardProps}>
                  <PremiumBreakdown headless data={data} />
                </CollapsibleCard>
              );
            } else {
              card = (
                <CollapsibleCard key={id} title="Option legs" {...cardProps}>
                {data.options.length === 0 ? (
                  <div style={{ color: k.dim, fontSize: 12, padding: '14px 16px' }}>
                    {data.resolution_reason || 'No option contract matched the selected strike/expiry settings.'}
                  </div>
                ) : (
                  (() => {
                    // ✝ BEST R:R — same logic as the impact calculator, applied to the leg list.
                    const sd = stopDistance(data.spot_now || data.spot_at_trigger, data.stop_loss);
                    let bestSym: string | null = null;
                    let bestVal = -Infinity;
                    let bestDeltaSym: string | null = null;
                    let bestDeltaVal = -Infinity;
                    for (const leg of data.options) {
                      const premium = leg.last_price || 0;
                      if (premium <= 0) continue;
                      const { rr, effPct } = computeLegRR(leg.delta, leg.gamma, premium, sd);
                      const v = rrScore(rr, effPct);
                      if (v > bestVal) { bestVal = v; bestSym = leg.option_symbol; }
                      const ad = Math.abs(leg.delta);
                      if (ad > bestDeltaVal) { bestDeltaVal = ad; bestDeltaSym = leg.option_symbol; }
                    }
                    return data.options.map((leg) => (
                      <LegCard key={leg.option_symbol} leg={leg} exchange={data.exchange} underlying={underlying} spotPx={data.spot_now || undefined} isBest={leg.option_symbol === bestSym} isBestDelta={leg.option_symbol === bestDeltaSym} />
                    ));
                  })()
                )}
                </CollapsibleCard>
              );
            }
            return <React.Fragment key={id}>{guide}{card}</React.Fragment>;
          })}
          {dragId && dropIndex === sectionOrder.length && (
            <div style={{ height: 2, background: k.green, borderRadius: 2, marginTop: 12 }} />
          )}
          <div style={{ fontSize: 10, color: k.dim, marginTop: 18, lineHeight: 1.7 }}>
            Greeks are Black-Scholes from live IV (or backed out of last price when the market is closed). BUY/SELL place real MARKET orders on your Kite account.
          </div>
        </div>
      )}
    </div>
  );
}

export default SignalDetailPane;
