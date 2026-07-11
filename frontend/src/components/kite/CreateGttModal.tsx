import React, { useState } from 'react';
import { k } from '../../styles/kiteUI';
import { usePlaceKiteGtt } from '../../hooks/useKite';

export function CreateGttModal({ onClose }: { onClose: () => void }) {
  const place = usePlaceKiteGtt() as any;
  const [symbol, setSymbol] = useState('');
  const [exchange, setExchange] = useState('NSE');
  const [side, setSide] = useState<'BUY' | 'SELL'>('SELL');
  const [product, setProduct] = useState<'CNC' | 'NRML'>('CNC');
  const [lastPrice, setLastPrice] = useState(0);
  const [triggerPrice, setTriggerPrice] = useState(0);
  const [orderPrice, setOrderPrice] = useState(0);
  const [quantity, setQuantity] = useState(1);
  const [error, setError] = useState<string | null>(null);

  const submit = () => {
    setError(null);
    if (!(triggerPrice > 0)) { setError('Enter a valid trigger value'); return; }
    if (!symbol.trim()) { setError('Enter a symbol'); return; }
    if (!(lastPrice > 0)) { setError('Enter the current last price'); return; }
    if (!(orderPrice > 0)) { setError('Enter a valid order price'); return; }
    if (!(quantity > 0)) { setError('Enter a quantity greater than 0'); return; }
    place.mutate(
      {
        trigger_type: 'single', tradingsymbol: symbol.trim().toUpperCase(), exchange,
        last_price: lastPrice, trigger_values: [triggerPrice],
        orders: [{ tradingsymbol: symbol.trim().toUpperCase(), exchange, transaction_type: side, quantity, order_type: 'LIMIT', product, price: orderPrice }],
      },
      { onSuccess: onClose, onError: (err: any) => setError(err?.message || 'Create GTT failed') },
    );
  };

  const field = (label: string, value: number | string, onChange: (v: string) => void, type: 'text' | 'number' = 'number') => (
    <label style={{ fontSize: 12, color: '#9b9b9b' }}>{label}
      <input type={type} step={type === 'number' ? 0.05 : undefined} value={value} onChange={(e) => onChange(e.target.value)}
        style={{ display: 'block', width: '100%', marginTop: 4, padding: '8px 10px', border: `1px solid ${k.border}`, borderRadius: 3, fontSize: 14 }} />
    </label>
  );

  return (
    <>
      <div onClick={onClose} style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.06)', zIndex: 1100 }} />
      <div style={{ position: 'fixed', top: 80, left: '50%', transform: 'translateX(-50%)', width: 420, maxHeight: '80vh', overflowY: 'auto', background: k.bg, borderRadius: 4, boxShadow: '0 10px 44px rgba(0,0,0,0.28)', zIndex: 1101, fontFamily: k.fontFamily }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '14px 18px', borderBottom: `1px solid ${k.border}` }}>
          <h3 style={{ margin: 0, fontSize: 15, fontWeight: 500, color: '#444' }}>New GTT trigger</h3>
          <button onClick={onClose} style={{ background: 'none', border: 'none', fontSize: 18, color: '#9b9b9b', cursor: 'pointer' }}>✕</button>
        </div>
        <div style={{ padding: 18, display: 'flex', flexDirection: 'column', gap: 14 }}>
          <div style={{ display: 'flex', gap: 10 }}>
            <div style={{ flex: 2 }}>{field('Symbol', symbol, (v) => setSymbol(v), 'text')}</div>
            <div style={{ flex: 1 }}>{field('Exchange', exchange, (v) => setExchange(v), 'text')}</div>
          </div>
          <div style={{ display: 'flex', gap: 8 }}>
            <label style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 13 }}><input type="radio" checked={side === 'BUY'} onChange={() => setSide('BUY')} /> Buy</label>
            <label style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 13 }}><input type="radio" checked={side === 'SELL'} onChange={() => setSide('SELL')} /> Sell</label>
            <label style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 13, marginLeft: 16 }}><input type="radio" checked={product === 'CNC'} onChange={() => setProduct('CNC')} /> CNC</label>
            <label style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 13 }}><input type="radio" checked={product === 'NRML'} onChange={() => setProduct('NRML')} /> NRML</label>
          </div>
          {field('Last price', lastPrice, (v) => setLastPrice(Number(v)))}
          {field('Trigger price', triggerPrice, (v) => setTriggerPrice(Number(v)))}
          {field('Order price', orderPrice, (v) => setOrderPrice(Number(v)))}
          {field('Quantity', quantity, (v) => setQuantity(Number(v)))}
          {error && <div style={{ color: k.red, fontSize: 12 }}>{error}</div>}
        </div>
        <div style={{ display: 'flex', gap: 10, padding: '14px 18px', borderTop: `1px solid ${k.border}` }}>
          <button onClick={onClose} style={{ flex: 1, background: '#fff', color: '#444', border: `1px solid ${k.border}`, borderRadius: 3, padding: '9px', fontSize: 13, cursor: 'pointer' }}>Cancel</button>
          <button onClick={submit} disabled={place.isPending} style={{ flex: 1, background: k.blue, color: '#fff', border: 'none', borderRadius: 3, padding: '9px', fontSize: 13, fontWeight: 600, cursor: place.isPending ? 'not-allowed' : 'pointer', opacity: place.isPending ? 0.6 : 1 }}>
            {place.isPending ? '…' : 'Create GTT'}
          </button>
        </div>
      </div>
    </>
  );
}
