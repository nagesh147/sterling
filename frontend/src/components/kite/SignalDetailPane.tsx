import React, { useState } from 'react';
import { k, tint } from '../../styles/kiteUI';
import { useEngineDetail, useEnginePlaceOrder } from '../../hooks/useTripleSupertrend';
import type { DepthLevel, OptionDetail } from '../../types/kiteEngine';
import { parseTradingsymbol } from '../../utils/fmt';
import { useKiteQuote } from '../../hooks/useKite';
import { QuoteDetail } from './MarketWatchPane';
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
  onTrade: (leg: OptionDetail, side: 'BUY' | 'SELL') => void;
  underlying: string;
}) {
  const [showDepth, setShowDepth] = useState(false);
  const sym = `${exchange}:${leg.option_symbol}`;
  const { data: quotes } = useKiteQuote([sym], showDepth);
  const q = quotes?.[sym];
  const displayName = parseTradingsymbol(leg.option_symbol);

  return (
    <div style={{ border: `1px solid ${k.border}`, borderRadius: 6, padding: 12, marginBottom: 10 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <span style={{ fontSize: 10, fontWeight: 700, color: k.orange, background: tint(k.orange, 10), padding: '2px 6px', borderRadius: 3 }}>{leg.moneyness}</span>
          <span style={{ fontSize: 13, fontWeight: 600, color: k.text }}>{displayName}</span>
        </div>
        <span style={{ fontSize: 14, fontWeight: 700, color: k.text }}>₹{leg.last_price.toFixed(2)}</span>
      </div>

      <div style={{ display: 'flex', gap: 18, marginTop: 10, flexWrap: 'wrap' }}>
        <Stat label="Strike" value={`${leg.strike}`} />
        <Stat label="Expiry" value={`${leg.expiry} (${leg.dte}d)`} />
        <Stat label="IV" value={`${(leg.iv * 100).toFixed(1)}%`} />
        <Stat label="Δ delta" value={leg.delta.toFixed(3)} />
        <Stat label="Γ gamma" value={leg.gamma.toFixed(5)} />
        <Stat label="Θ theta/day" value={leg.theta.toFixed(1)} color={k.red} />
        <Stat label="V vega" value={leg.vega.toFixed(1)} />
        <Stat label="Lot" value={`${leg.lot_size ?? '—'}`} />
      </div>

      <div style={{ display: 'flex', gap: 8, marginTop: 12, alignItems: 'center' }}>
        <button onClick={() => onTrade(leg, 'BUY')} style={{ flex: 1, background: k.green, color: '#fff', border: 'none', borderRadius: 4, padding: '8px 0', fontSize: 13, fontWeight: 600, cursor: 'pointer' }}>BUY</button>
        <button onClick={() => onTrade(leg, 'SELL')} style={{ flex: 1, background: k.red, color: '#fff', border: 'none', borderRadius: 4, padding: '8px 0', fontSize: 13, fontWeight: 600, cursor: 'pointer' }}>SELL</button>
        <button onClick={() => setShowDepth((s) => !s)} style={{ background: 'none', color: k.dim, border: `1px solid ${k.border}`, borderRadius: 4, padding: '8px 12px', fontSize: 12, cursor: 'pointer' }}>
          {showDepth ? 'Hide depth' : 'Market depth'}
        </button>
      </div>
      {showDepth && (
        <div style={{ marginTop: 12, borderTop: `1px solid ${k.border}` }}>
          {q ? <QuoteDetail sym={sym} q={q} expiry={leg.expiry} spotName={underlying} instrumentName={displayName} /> : <div style={{ padding: 12, color: k.dim, fontSize: 12 }}>Loading market depth...</div>}
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

  const onTrade = (leg: OptionDetail, side: 'BUY' | 'SELL') => {
    if (!data) return;
    const qty = leg.lot_size ?? 0;
    if (qty <= 0) { alert('No lot size resolved for this contract.'); return; }
    const ok = window.confirm(
      `${side} ${qty} ${parseTradingsymbol(leg.option_symbol)} @ MARKET on ${data.exchange}?\n` +
      `(${underlying} ${data.regime} · last ₹${leg.last_price.toFixed(2)})`);
    if (!ok) return;
    placeOrder.mutate({
      option_symbol: leg.option_symbol, exchange: data.exchange, side,
      quantity: qty, order_type: 'MARKET', product: 'NRML',
    });
  };

  const bull = data?.regime === 'BULL';
  const accent = bull ? k.green : k.red;
  const move = data ? data.spot_now - data.spot_at_trigger : 0;

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%', background: k.bg, fontFamily: k.fontFamily, overflow: 'auto' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 14, padding: '12px 16px', borderBottom: `1px solid ${k.border}`, position: 'sticky', top: 0, background: k.bg, zIndex: 1 }}>
        <button onClick={onClose} style={{ fontSize: 12, color: k.dim, background: 'none', border: `1px solid ${k.border}`, borderRadius: 4, padding: '4px 10px', cursor: 'pointer' }}>← Back</button>
        <span style={{ fontSize: 15, fontWeight: 600, color: k.text }}>{underlying}</span>
        {data && <span style={{ fontSize: 11, fontWeight: 700, color: accent, background: tint(accent, 10), padding: '2px 8px', borderRadius: 3 }}>{data.regime} · {data.option_type}</span>}
        <div style={{ marginLeft: 'auto', display: 'flex', gap: 8 }}>
          <button onClick={onShowSetup} style={{ fontSize: 12, color: k.text, background: 'none', border: `1px solid ${k.border}`, borderRadius: 4, padding: '4px 10px', cursor: 'pointer' }}>📈 Setup chart</button>
          <button onClick={() => onShowOptionChain(underlying)} style={{ fontSize: 12, color: k.text, background: 'none', border: `1px solid ${k.border}`, borderRadius: 4, padding: '4px 10px', cursor: 'pointer' }}>Option chain</button>
          <button onClick={togglePin} style={{ fontSize: 12, color: pinned ? k.orange : k.dim, background: pinned ? tint(k.orange, 10) : 'none', border: `1px solid ${pinned ? k.orange : k.border}`, borderRadius: 4, padding: '4px 10px', cursor: 'pointer' }}>{pinned ? '📌 Pinned' : 'Pin'}</button>
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
            <Stat label="Trail stop" value={data.stop_loss.toFixed(2)} color={k.amber} />
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
              <LegCard key={leg.option_symbol} leg={leg} exchange={data.exchange} onTrade={onTrade} underlying={underlying} />
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
