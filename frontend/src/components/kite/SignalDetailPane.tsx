import React, { useState } from 'react';
import { k, tint, Icons } from '../../styles/kiteUI';
import { useEngineDetail, useEnginePlaceOrder } from '../../hooks/useTripleSupertrend';
import type { DepthLevel, OptionDetail } from '../../types/kiteEngine';
import { parseTradingsymbol } from '../../utils/fmt';
import { InstrumentLabel, parseInstrument } from './InstrumentLabel';
import { useKiteQuote } from '../../hooks/useKite';
import { QuoteDetail } from './MarketWatchPane';
import { AlignmentChips } from './TripleSupertrendPane';

function OrderEntryPanel({ leg, exchange, onTradeSubmit }: { leg: OptionDetail, exchange: string, onTradeSubmit: (leg: OptionDetail, side: 'BUY'|'SELL', qty: number, price: number, type: 'MARKET'|'LIMIT') => void }) {
  const [side, setSide] = useState<'BUY' | 'SELL'>('BUY');
  const [qty, setQty] = useState(leg.lot_size ?? 0);
  const [price, setPrice] = useState(leg.last_price ?? 0);
  const [type, setType] = useState<'MARKET'|'LIMIT'>('MARKET');

  const accent = side === 'BUY' ? '#4184f3' : '#ff5722';

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
      {/* Tab Header */}
      <div style={{ display: 'flex', background: '#f9f9f9', borderBottom: `1px solid ${k.border}` }}>
        <button 
          onClick={() => setSide('BUY')}
          style={{ flex: 1, padding: '12px 0', border: 'none', background: side === 'BUY' ? '#4184f3' : 'transparent', color: side === 'BUY' ? '#fff' : k.text, fontWeight: 500, cursor: 'pointer', fontSize: 12, transition: 'all 0.2s' }}
        >
          BUY
        </button>
        <button 
          onClick={() => setSide('SELL')}
          style={{ flex: 1, padding: '12px 0', border: 'none', background: side === 'SELL' ? '#ff5722' : 'transparent', color: side === 'SELL' ? '#fff' : k.text, fontWeight: 500, cursor: 'pointer', fontSize: 12, transition: 'all 0.2s' }}
        >
          SELL
        </button>
      </div>

      <div style={{ padding: 16, display: 'flex', flexDirection: 'column', gap: 16, flex: 1 }}>
        <div style={{ display: 'flex', gap: 16 }}>
          <label style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: 6, fontSize: 12, color: k.dim }}>
            Qty.
            <input type="number" value={qty} onChange={e => setQty(Number(e.target.value))} style={{ padding: '8px 12px', border: `1px solid ${k.border}`, borderRadius: 3, fontSize: 14, outline: 'none' }} />
          </label>
          <label style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: 6, fontSize: 12, color: k.dim }}>
            Price
            <input type="number" step="0.05" value={price} disabled={type === 'MARKET'} onChange={e => setPrice(Number(e.target.value))} style={{ padding: '8px 12px', border: `1px solid ${k.border}`, borderRadius: 3, fontSize: 14, outline: 'none', background: type === 'MARKET' ? '#f5f5f5' : '#fff', color: type === 'MARKET' ? k.dim : k.text }} />
          </label>
        </div>

        <div style={{ display: 'flex', gap: 16, fontSize: 12, color: k.text }}>
          <label style={{ display: 'flex', alignItems: 'center', gap: 6, cursor: 'pointer' }}>
            <input type="radio" checked={type === 'MARKET'} onChange={() => setType('MARKET')} /> Market
          </label>
          <label style={{ display: 'flex', alignItems: 'center', gap: 6, cursor: 'pointer' }}>
            <input type="radio" checked={type === 'LIMIT'} onChange={() => setType('LIMIT')} /> Limit
          </label>
        </div>
      </div>

      {/* Footer */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '12px 16px', borderTop: `1px solid ${k.border}`, background: '#f9f9f9' }}>
        <div style={{ display: 'flex', flexDirection: 'column' }}>
          <span style={{ fontSize: 11, color: k.dim }}>Margin req.</span>
          <span style={{ fontSize: 14, color: k.text }}>₹{(qty * price).toLocaleString('en-IN', { maximumFractionDigits: 2 })}</span>
        </div>
        <button 
          onClick={() => onTradeSubmit(leg, side, qty, type === 'MARKET' ? 0 : price, type)}
          style={{ background: accent, color: '#fff', border: 'none', borderRadius: 3, padding: '8px 24px', fontSize: 13, fontWeight: 500, cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 8 }}
        >
          {side} <Icons.ArrowUp /> 
        </button>
      </div>
    </div>
  );
}

interface Props {
  token: number;
  underlying: string;
  onClose: () => void;
  onShowSetup: () => void;
  onShowOptionChain: (underlying: string) => void;
}

function ist(ms: number): string {
  return new Date(ms).toLocaleString('en-IN', { hour12: false });
}

function Stat({ label, value, color }: { label: string; value: string; color?: string }) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
      <span style={{ fontSize: 10, color: k.dim, textTransform: 'uppercase' }}>{label}</span>
      <span style={{ fontSize: 14, fontWeight: 600, color: color ?? k.text }}>{value}</span>
    </div>
  );
}

function LegCard({ leg, exchange, onTrade, underlying }: {
  leg: OptionDetail; exchange: string;
  onTrade: (leg: OptionDetail, side: 'BUY' | 'SELL', qty: number, price: number, order_type: 'MARKET' | 'LIMIT') => void;
  underlying: string;
}) {
  const [showDepth, setShowDepth] = useState(false);
  const sym = `${exchange}:${leg.option_symbol}`;
  const { data: quotes } = useKiteQuote([sym]);
  const q = quotes?.[sym];

  const netChange = q?.net_change || 0;
  const pctChange = q?.pct_change || 0;
  const color = netChange > 0 ? k.green : netChange < 0 ? k.red : k.dim;

  const [hovered, setHovered] = useState(false);

  return (
    <div 
      style={{ borderBottom: `1px solid ${k.border}`, background: hovered ? k.surface : k.bg }}
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
    >
      <div 
        style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '0 16px', height: 44, cursor: 'pointer' }}
        onClick={() => setShowDepth(!showDepth)}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          <span style={{ fontSize: 10, padding: '2px 6px', background: tint(k.orange, 10), color: k.orange, borderRadius: 2 }}>{leg.moneyness}</span>
          <span style={{ fontSize: 13, color: k.text, fontWeight: 400 }}><InstrumentLabel symbol={`${exchange}:${leg.option_symbol}`} /></span>
        </div>
        
        <div style={{ display: 'flex', alignItems: 'center', gap: 24 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 16 }}>
            {q && (
              <div style={{ display: 'flex', alignItems: 'center', gap: 4, fontSize: 12 }}>
                <span style={{ color: k.dim }}>{netChange.toFixed(2)}</span>
                <span style={{ color: k.text }}>{pctChange.toFixed(2)}%</span>
                <span style={{ color: color, display: 'flex', alignItems: 'center', margin: '0 2px' }}>
                  {netChange !== 0 ? (netChange > 0 ? <Icons.ChevronUp /> : <Icons.ChevronDown />) : <span style={{fontSize:14, padding:'0 2px', lineHeight:1}}>∘</span>}
                </span>
              </div>
            )}
            <span style={{ fontSize: 13, color: q ? color : k.text, fontWeight: 500 }}>{leg.last_price.toFixed(2)}</span>
          </div>
          
          <div style={{ display: 'flex', gap: 4 }}>
            <button onClick={(e) => { e.stopPropagation(); setShowDepth(!showDepth); }} style={{ background: '#4184f3', color: '#fff', border: 'none', borderRadius: 3, padding: '0 12px', height: 28, fontSize: 11, fontWeight: 500, cursor: 'pointer' }}>B</button>
            <button onClick={(e) => { e.stopPropagation(); setShowDepth(!showDepth); }} style={{ background: '#ff5722', color: '#fff', border: 'none', borderRadius: 3, padding: '0 12px', height: 28, fontSize: 11, fontWeight: 500, cursor: 'pointer' }}>S</button>
            <button onClick={(e) => { e.stopPropagation(); setShowDepth(!showDepth); }} style={{ background: 'transparent', color: k.dim, border: `1px solid ${k.border}`, borderRadius: 3, width: 28, height: 28, cursor: 'pointer', display: 'flex', alignItems: 'center', justifyContent: 'center' }} title="Market Depth"><Icons.Depth /></button>
            <button onClick={(e) => e.stopPropagation()} style={{ background: 'transparent', color: k.dim, border: `1px solid ${k.border}`, borderRadius: 3, width: 28, height: 28, cursor: 'pointer', display: 'flex', alignItems: 'center', justifyContent: 'center' }} title="Chart"><Icons.Chart /></button>
            <button onClick={(e) => e.stopPropagation()} style={{ background: 'transparent', color: k.dim, border: `1px solid ${k.border}`, borderRadius: 3, width: 28, height: 28, cursor: 'pointer', display: 'flex', alignItems: 'center', justifyContent: 'center' }} title="More"><Icons.More /></button>
          </div>
        </div>
      </div>



      {showDepth && (
        <div style={{ display: 'flex', flexDirection: 'column', borderTop: `1px solid ${k.border}`, background: k.surface }}>
          <div style={{ display: 'flex' }}>
            {/* LEFT: Market Depth (with native BUY/SELL buttons at top) */}
            <div style={{ flex: 1, minWidth: 0 }}>
              {q ? (
                <QuoteDetail 
                  sym={sym} 
                  q={q} 
                  expiry={parseInstrument(leg.option_symbol) ? `${parseInstrument(leg.option_symbol)!.day ? parseInstrument(leg.option_symbol)!.day + ' ' : ''}${parseInstrument(leg.option_symbol)!.month} 20${parseInstrument(leg.option_symbol)!.year}` : ''}
                  spotName={underlying} 
                  instrumentName={<InstrumentLabel symbol={leg.option_symbol} />} 
                  hideHeaderAndActions={true} 
                  onBuy={() => {}}
                  onSell={() => {}}
                  greeks={leg}
                />
              ) : (
                <div style={{ padding: 16, color: k.dim, fontSize: 12 }}>Loading market depth...</div>
              )}
            </div>
            
            <div style={{ width: 1, background: k.border }} />
            
            {/* RIGHT: Order Panel */}
            <div style={{ flex: 1, minWidth: 0 }}>
              <OrderEntryPanel leg={leg} exchange={exchange} onTradeSubmit={onTrade} />
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

export function SignalDetailPane({ token, underlying, onClose, onShowSetup, onShowOptionChain }: Props) {
  const { data, isLoading, isError } = useEngineDetail(token, true);
  const placeOrder = useEnginePlaceOrder();
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

  const onTradeSubmit = (leg: OptionDetail, side: 'BUY' | 'SELL', qty: number, price: number, order_type: 'MARKET' | 'LIMIT') => {
    if (!data) return;
    const ok = window.confirm(
      `${side} ${qty} ${parseTradingsymbol(leg.option_symbol)} @ ${order_type === 'MARKET' ? 'MARKET' : price} on ${data.exchange}?\n` +
      `(${underlying} ${data.regime} · last ₹${leg.last_price.toFixed(2)})`
    );
    if (!ok) return;
    placeOrder.mutate({
      option_symbol: leg.option_symbol,
      exchange: data.exchange,
      side,
      quantity: qty,
      order_type,
      limit_price: order_type === 'LIMIT' ? price : undefined,
      product: 'NRML',
    } as any);
  };

  const bull = data?.regime === 'BULL';
  const accent = bull ? k.green : k.red;
  const move = data ? data.spot_now - data.spot_at_trigger : 0;

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%', background: k.bg, fontFamily: k.fontFamily, overflow: 'auto' }}>
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

          {placeOrder.isPending && <div style={{ color: k.amber, fontSize: 12, marginBottom: 10 }}>Submitting order…</div>}
          {placeOrder.isSuccess && (
            <div style={{ color: k.green, fontSize: 12, marginBottom: 10 }}>
              ✓ {placeOrder.data.status === 'duplicate' ? 'Already submitted' : 'Order submitted'} — #{placeOrder.data.order_id}
            </div>
          )}
          {placeOrder.isError && <div style={{ color: k.red, fontSize: 12, marginBottom: 10 }}>Order failed: {(placeOrder.error as Error)?.message}</div>}

          {/* option legs */}
          {data.options.length === 0 ? (
            <div style={{ color: k.dim, fontSize: 12 }}>No option legs resolved (no liquid ATM/ITM contract).</div>
          ) : (
            data.options.map((leg) => (
              <LegCard key={leg.option_symbol} leg={leg} exchange={data.exchange} onTrade={onTradeSubmit} underlying={underlying} />
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
