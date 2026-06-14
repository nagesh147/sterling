import React, { useState } from 'react';
import { k, tint, Icons } from '../../styles/kiteUI';
import { useEngineDetail, useEnginePlaceOrder } from '../../hooks/useTripleSupertrend';
import type { DepthLevel, OptionDetail } from '../../types/kiteEngine';
import { parseTradingsymbol } from '../../utils/fmt';
import { InstrumentLabel, parseInstrument } from './InstrumentLabel';
import { useKiteQuote } from '../../hooks/useKite';
import { QuoteDetail } from './MarketWatchPane';
import { AlignmentChips } from './TripleSupertrendPane';
import { useKiteSettings } from '../../store/useKiteSettings';

function OrderEntryPanel({ leg, exchange, onTradeSubmit, side, onSideChange }: { leg: OptionDetail, exchange: string, onTradeSubmit: (leg: OptionDetail, side: 'BUY'|'SELL', qty: number, price: number, type: 'MARKET'|'LIMIT') => void, side: 'BUY'|'SELL', onSideChange: (s: 'BUY'|'SELL') => void }) {
  const [qty, setQty] = useState(leg.lot_size ?? 0);
  const [price, setPrice] = useState(leg.last_price ?? 0);
  const [type, setType] = useState<'MARKET'|'LIMIT'>('MARKET');

  const accent = side === 'BUY' ? '#4184f3' : '#ff5722';

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
      {/* Tab Header */}
      <div style={{ display: 'flex', background: '#f9f9f9', borderBottom: `1px solid ${k.border}` }}>
        <button 
          onClick={() => onSideChange('BUY')}
          style={{ flex: 1, padding: '12px 0', border: 'none', background: side === 'BUY' ? '#4184f3' : 'transparent', color: side === 'BUY' ? '#fff' : k.text, fontWeight: 500, cursor: 'pointer', fontSize: 12, transition: 'all 0.2s' }}
        >
          BUY
        </button>
        <button 
          onClick={() => onSideChange('SELL')}
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
  const [orderSide, setOrderSide] = useState<'BUY' | 'SELL'>('BUY');
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
      color = s.showPriceDirection ? (chgPct >= 0 ? k.green : k.red) : k.dim;
    }
  }

  const [hovered, setHovered] = useState(false);
  const btnAction = { display: 'flex', alignItems: 'center', justifyContent: 'center', width: 24, height: 24, borderRadius: 2, cursor: 'pointer', fontSize: 11, fontWeight: 600, border: 'none' };

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
            
            <div className="sd-actions" onClick={(e) => e.stopPropagation()}>
              <button style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', width: 25.5, height: 32, background: '#4184f3', color: '#fff', borderRadius: 3, padding: 0, fontWeight: 500, border: 'none', cursor: 'pointer', fontSize: 11 }} title="Buy" onClick={() => { setOrderSide('BUY'); setShowDepth(true); }}>B</button>
              <button style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', width: 25.5, height: 32, background: '#ff5722', color: '#fff', borderRadius: 3, padding: 0, fontWeight: 500, border: 'none', cursor: 'pointer', fontSize: 11 }} title="Sell" onClick={() => { setOrderSide('SELL'); setShowDepth(true); }}>S</button>
              <button style={{ ...btnAction, background: 'transparent', color: k.dim, padding: 4 }} onClick={() => setShowDepth(!showDepth)} title="Market Depth"><Icons.Depth /></button>
              <button style={{ ...btnAction, background: 'transparent', color: k.dim, padding: 4 }} title="Chart"><Icons.Chart /></button>
              <button style={{ ...btnAction, background: 'transparent', color: k.dim, padding: 4 }} title="More"><Icons.More /></button>
            </div>
          </div>
        )}
      </div>

      {showDepth && (
        <div style={{ display: 'flex', flexDirection: 'column', borderTop: `1px solid ${k.border}`, background: k.surface }}>
          <div style={{ display: 'flex' }}>
            {/* LEFT: Market Depth (with native BUY/SELL buttons at top) */}
            <div style={{ flex: 1, minWidth: 0 }} onClick={(e) => e.stopPropagation()}>
              {q ? (
                <QuoteDetail 
                  sym={sym} 
                  q={q} 
                  expiry={parseInstrument(leg.option_symbol) ? `${parseInstrument(leg.option_symbol)!.day ? parseInstrument(leg.option_symbol)!.day + ' ' : ''}${parseInstrument(leg.option_symbol)!.month} 20${parseInstrument(leg.option_symbol)!.year}` : ''}
                  spotName={underlying} 
                  instrumentName={<InstrumentLabel symbol={leg.option_symbol} />} 
                  hideHeaderAndActions={false} 
                  onBuy={() => setOrderSide('BUY')}
                  onSell={() => setOrderSide('SELL')}
                  greeks={leg}
                />
              ) : (
                <div style={{ padding: 16, color: k.dim, fontSize: 12 }}>Loading market depth...</div>
              )}
            </div>
            
            <div style={{ width: 1, background: k.border }} />
            
            {/* RIGHT: Order Panel */}
            <div style={{ flex: 1, minWidth: 0 }} onClick={(e) => e.stopPropagation()}>
              <OrderEntryPanel leg={leg} exchange={exchange} onTradeSubmit={onTrade} side={orderSide} onSideChange={setOrderSide} />
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
          gap: 4px;
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
