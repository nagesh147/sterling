import React, { useEffect, useRef, useState } from 'react';
import { k } from '../../styles/kiteUI';
import { usePlaceKiteOrder, useKiteBasketMargins } from '../../hooks/useKite';
import { useKiteBasketStore, type BasketEntry } from '../../store/useKiteBasketStore';
import { buildOrderBody, buildMarginOrder, parseMargin, needsPrice, needsTrigger, resolveVariety } from './orderTicket';
import { InstrumentLabel } from './InstrumentLabel';
import { useEngineActivity } from '../../hooks/useSterlingKiteEngine';

const inr = (n: number) => n.toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 });

const statusColor: Record<BasketEntry['status'], string> = {
  idle: k.dim, placing: k.blue, placed: k.green, failed: k.red,
};
const statusLabel: Record<BasketEntry['status'], string> = {
  idle: 'Pending', placing: 'Placing…', placed: 'Placed', failed: 'Failed',
};

export function BasketPane({ onClose }: { onClose: () => void }) {
  const { entries, remove, update, setStatus, clear } = useKiteBasketStore();
  const placeOrder = usePlaceKiteOrder();
  const marginCalc = useKiteBasketMargins();
  const { data: activity } = useEngineActivity();
  const variety = resolveVariety(activity?.market_open);
  const [margin, setMargin] = useState<{ total: number; charges: number } | null>(null);
  const [placingAll, setPlacingAll] = useState(false);

  const reqId = useRef(0);
  const runMargin = () => {
    if (entries.length === 0) { setMargin(null); return; }
    if (entries.some((e) => (needsPrice(e.orderType) && !(e.price > 0)) || (needsTrigger(e.orderType) && !(e.trigger > 0)))) return;
    const orders = entries.map((e) => buildMarginOrder({
      tradingsymbol: e.symbol, exchange: e.exchange, side: e.side, quantity: e.qty,
      product: e.product, orderType: e.orderType, price: e.price, trigger: e.trigger,
    }));
    const id = ++reqId.current;
    marginCalc.mutate({ orders }, {
      onSuccess: (resp) => { if (id === reqId.current) setMargin(parseMargin(Array.isArray(resp) ? resp[resp.length - 1] : resp)); },
      onError: () => { if (id === reqId.current) setMargin(null); },
    });
  };
  useEffect(() => {
    const t = setTimeout(runMargin, 350);
    return () => clearTimeout(t);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [entries.map((e) => `${e.symbol}|${e.qty}|${e.price}|${e.orderType}`).join(',')]);

  const placeAll = async () => {
    setPlacingAll(true);
    // Sequential, not Promise.all: a live order that already filled can't be
    // un-placed, so each must resolve before the next fires — mirrors how
    // real Kite Web places a basket one order at a time. Re-read entries from
    // the store's live getState() on every iteration (not the render-time
    // `entries` snapshot) so a row removed mid-run is skipped instead of
    // still getting placed.
    const ids = useKiteBasketStore.getState().entries.map((e) => e.id);
    for (const id of ids) {
      const current = useKiteBasketStore.getState().entries.find((e) => e.id === id);
      if (!current || current.status === 'placed') continue;
      setStatus(id, 'placing');
      try {
        const res = await placeOrder.mutateAsync(buildOrderBody({
          tradingsymbol: current.symbol, exchange: current.exchange, side: current.side, quantity: current.qty,
          product: current.product, orderType: current.orderType, price: current.price, trigger: current.trigger,
          variety,
        }));
        setStatus(id, 'placed', undefined, res?.order_id);
      } catch (err: any) {
        setStatus(id, 'failed', err?.message || 'Order failed');
      }
    }
    setPlacingAll(false);
  };

  const allPlaced = entries.length > 0 && entries.every((e) => e.status === 'placed');

  return (
    <>
      <div onClick={onClose} style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.06)', zIndex: 1100 }} />
      <div style={{ position: 'fixed', top: 60, left: '50%', transform: 'translateX(-50%)', width: 620, maxWidth: '92vw', maxHeight: '80vh', display: 'flex', flexDirection: 'column', background: k.bg, borderRadius: 4, boxShadow: '0 10px 44px rgba(0,0,0,0.28)', zIndex: 1101, fontFamily: k.fontFamily }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '16px 20px', borderBottom: '1px solid #f1f1f1' }}>
          <h3 style={{ margin: 0, fontSize: 16, fontWeight: 500, color: '#444' }}>Basket <span style={{ color: '#9b9b9b', fontWeight: 400 }}>({entries.length})</span></h3>
          <button onClick={onClose} style={{ background: 'none', border: 'none', fontSize: 18, color: '#9b9b9b', cursor: 'pointer' }}>✕</button>
        </div>

        {variety === 'amo' && (
          <div style={{ padding: '8px 20px', background: 'rgba(240,180,40,0.12)', color: '#8a6100', fontSize: 12 }}>
            Market is closed — all orders placed from this basket will queue as After Market Orders (AMO).
          </div>
        )}

        <div style={{ overflowY: 'auto', flex: 1 }}>
          {entries.length === 0 && <div style={{ padding: 24, color: '#9b9b9b', fontSize: 13 }}>Basket is empty. Add orders from the order ticket or a watchlist row.</div>}
          {entries.map((e) => (
            <div key={e.id} style={{ display: 'flex', alignItems: 'center', gap: 10, padding: '10px 20px', borderBottom: '1px solid #f9f9f9' }}>
              <span style={{ width: 44, fontSize: 11, fontWeight: 700, color: e.side === 'BUY' ? k.blue : k.orange }}>{e.side}</span>
              <span style={{ flex: 1, fontSize: 13, color: '#444' }}><InstrumentLabel symbol={`${e.exchange}:${e.symbol}`} /></span>
              <input type="number" min={1} value={e.qty} disabled={e.status === 'placed' || placingAll}
                onChange={(ev) => update(e.id, { qty: Number(ev.target.value) })}
                style={{ width: 60, padding: '4px 6px', border: '1px solid #e0e0e0', borderRadius: 3, fontSize: 12, textAlign: 'right' }} />
              {needsPrice(e.orderType) && (
                <input type="number" step={0.05} value={e.price} disabled={e.status === 'placed' || placingAll}
                  onChange={(ev) => update(e.id, { price: Number(ev.target.value) })}
                  style={{ width: 70, padding: '4px 6px', border: '1px solid #e0e0e0', borderRadius: 3, fontSize: 12, textAlign: 'right' }} />
              )}
              <span style={{ width: 90, fontSize: 11, color: statusColor[e.status], textAlign: 'right' }} title={e.error}>
                {statusLabel[e.status]}
              </span>
              <button onClick={() => remove(e.id)} title="Remove from basket" disabled={e.status === 'placing'}
                style={{ background: 'none', border: 'none', color: '#9b9b9b', cursor: 'pointer', fontSize: 14 }}>✕</button>
            </div>
          ))}
        </div>

        <div style={{ padding: '14px 20px', borderTop: '1px solid #f1f1f1', display: 'flex', alignItems: 'center', gap: 16 }}>
          <span style={{ fontSize: 12, color: k.dim }}>
            Est. margin <b style={{ color: '#444' }}>{margin ? inr(margin.total) : (marginCalc.isPending ? '…' : '—')}</b>
          </span>
          <div style={{ marginLeft: 'auto', display: 'flex', gap: 10 }}>
            <button onClick={clear} disabled={placingAll} style={{ background: '#fff', color: '#444', border: '1px solid #e0e0e0', borderRadius: 3, padding: '8px 16px', fontSize: 13, cursor: placingAll ? 'not-allowed' : 'pointer' }}>Clear</button>
            <button onClick={placeAll} disabled={entries.length === 0 || placingAll || allPlaced}
              style={{ background: k.blue, color: '#fff', border: 'none', borderRadius: 3, padding: '8px 20px', fontSize: 13, fontWeight: 600, cursor: (entries.length === 0 || placingAll || allPlaced) ? 'not-allowed' : 'pointer', opacity: (entries.length === 0 || placingAll || allPlaced) ? 0.55 : 1 }}>
              {placingAll ? 'Placing…' : allPlaced ? 'All placed' : 'Place Basket'}
            </button>
          </div>
        </div>
      </div>
    </>
  );
}
