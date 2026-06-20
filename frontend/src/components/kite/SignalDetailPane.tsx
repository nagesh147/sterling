import React, { useState } from 'react';
import { k, tint, Icons } from '../../styles/kiteUI';
import { useEngineDetail, useEnginePlaceOrder } from '../../hooks/useTripleSupertrend';
import type { DepthLevel, OptionDetail } from '../../types/kiteEngine';
import { parseTradingsymbol } from '../../utils/fmt';
import { InstrumentLabel, parseInstrument } from './InstrumentLabel';
import { useKiteQuote } from '../../hooks/useKite';
import { QuoteDetail } from './MarketWatchPane';
import { AlignmentChips } from './TripleSupertrendPane';
import { KiteActionButtons } from './KiteActionButtons';
import { useKiteSettings } from '../../store/useKiteSettings';
import { SignalImpactCalculator } from './SignalImpactCalculator';

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
  return `${d.toLocaleDateString('en-US', { weekday: 'short' })} ${d.toLocaleDateString('en-US', { month: 'short' }).toUpperCase()} ${d.toLocaleDateString('en-US', { day: '2-digit' })} ${d.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit', hour12: false })}`;
}

function Stat({ label, value, color }: { label: string; value: string; color?: string }) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
      <span style={{ fontSize: 10, color: k.dim, textTransform: 'uppercase' }}>{label}</span>
      <span style={{ fontSize: 14, fontWeight: 600, color: color ?? k.text }}>{value}</span>
    </div>
  );
}

function LegCard({ leg, exchange, underlying, spotPx }: {
  leg: OptionDetail; exchange: string;
  underlying: string;
  spotPx?: number;
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
          <span style={{ fontSize: 13, color: color, fontWeight: 400, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}><InstrumentLabel symbol={`${exchange}:${leg.option_symbol}`} /></span>
          <span style={{ fontSize: 9, color: k.dim, flexShrink: 0 }}>{exchange}</span>
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
              onDepth={(e) => { e.stopPropagation(); setShowDepth(!showDepth); }}
              onChart={(e) => { e.stopPropagation(); }}
              onMore={(e) => { e.stopPropagation(); }}
            />
          </div>
        )}
      </div>

      {showDepth && (
        <div style={{ display: 'flex', flexDirection: 'column', borderTop: `1px solid ${k.border}`, background: k.surface }}>
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

export function SignalDetailPane({ token, underlying, timestamp_ms, onClose, onShowSetup, onShowOptionChain }: Props) {
  const { data, isLoading, isError } = useEngineDetail(token, timestamp_ms, true);
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

  const uExch = data?.exchange === 'BFO' ? 'BSE' : 'NSE';
  const { data: quotes } = useKiteQuote(data ? [`${uExch}:${underlying}`] : [], false);
  const uQ = data ? quotes?.[`${uExch}:${underlying}`] : undefined;

  const bull = data?.regime === 'BULL';
  const move = data ? data.spot_now - data.spot_at_trigger : 0;

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%', background: k.bg, fontFamily: k.fontFamily, overflow: 'auto' }}>
      <style>{`
        .sd-leg-row {
          position: relative;
          display: flex;
          justify-content: space-between;
          align-items: center;
          padding: 6px 16px;
          height: 44px;
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
          
          {uQ && (
            <div style={{ display: 'flex', alignItems: 'baseline', gap: 4, fontSize: 13 }}>
              <span style={{ fontWeight: 500, color: uQ.net_change && uQ.net_change >= 0 ? k.green : k.red }}>{uQ.last_price?.toLocaleString('en-IN', {minimumFractionDigits: 2, maximumFractionDigits: 2}) ?? data?.spot_now.toFixed(2)}</span>
              {uQ.net_change != null && <span style={{ fontSize: 12, color: k.dim, marginLeft: 2 }}>{uQ.net_change.toFixed(2)}</span>}
              {uQ.pct_change != null && <span style={{ fontSize: 12, color: k.dim }}>{uQ.pct_change.toFixed(2)}%</span>}
            </div>
          )}
          
          {data && (
            <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginLeft: 8 }}>
              {data.alignment && <AlignmentChips a={data.alignment} />}
              <span style={{ fontSize: 12, color: k.dim, marginLeft: 4 }}>SL {data.stop_loss.toFixed(1)}</span>
              <span style={{ color: k.dim, fontSize: 12, fontWeight: 600 }}>· {data.option_type}</span>
            </div>
          )}
        </div>

        <div style={{ marginLeft: 'auto', display: 'flex', gap: 8 }}>
          <button onClick={onShowSetup} style={{ fontSize: 12, color: k.text, background: 'none', border: `1px solid ${k.border}`, borderRadius: 4, padding: '4px 10px', cursor: 'pointer' }}>📈 Setup chart</button>
          <button onClick={() => onShowOptionChain(underlying)} style={{ fontSize: 12, color: k.text, background: 'none', border: `1px solid ${k.border}`, borderRadius: 4, padding: '4px 10px', cursor: 'pointer' }}>Option chain</button>
        </div>
      </div>

      {isLoading && <div style={{ padding: 32, color: k.dim }}>Loading detail…</div>}
      {isError && <div style={{ padding: 32, color: k.red }}>No live detail (signal may have aged out of the latest scan, or market is closed).</div>}

      {data && (
        <div style={{ padding: 16 }}>
          {/* trigger context */}
          <div style={{ display: 'flex', gap: 24, flexWrap: 'wrap', padding: '12px 16px', background: k.surface, borderRadius: 6, marginBottom: 16 }}>
            <Stat label="Triggered at" value={ist(data.triggered_ms)} />
            <Stat label="Spot @ trigger" value={data.spot_at_trigger.toFixed(2)} />
            <Stat label="Spot now" value={data.spot_now ? data.spot_now.toFixed(2) : '—'} color={move >= 0 ? k.green : k.red} />
            <Stat label="Move since" value={`${move >= 0 ? '+' : ''}${move.toFixed(2)}`} color={move >= 0 ? k.green : k.red} />
            <Stat label="SL" value={data.stop_loss.toFixed(2)} color={k.amber} />
          </div>

          {/* Trade impact calculator — pick the best strike with live greeks */}
          <SignalImpactCalculator
            data={data}
            onBuy={(leg) => openOrderWindow({
              symbol: leg.option_symbol,
              exchange: data.exchange,
              initialSide: 'BUY',
              lotSize: leg.lot_size || 1,
              lastPrice: leg.last_price || 0,
            })}
          />

          {/* option legs */}
          {data.options.length === 0 ? (
            <div style={{ color: k.dim, fontSize: 12 }}>No option legs resolved (no liquid ATM/ITM contract).</div>
          ) : (
            data.options.map((leg) => (
              <LegCard key={leg.option_symbol} leg={leg} exchange={data.exchange} underlying={underlying} spotPx={data.spot_now || undefined} />
            ))
          )}
          <div style={{ fontSize: 10, color: k.dim, marginTop: 8 }}>
            Greeks are Black-Scholes from live IV (or backed out of last price when the market is closed). BUY/SELL place real MARKET orders on your Kite account.
          </div>
        </div>
      )}
    </div>
  );
}

export default SignalDetailPane;
