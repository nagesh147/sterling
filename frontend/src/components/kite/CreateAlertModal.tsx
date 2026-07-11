import React, { useState } from 'react';
import { k } from '../../styles/kiteUI';
import { useCreateKiteAlert } from '../../hooks/useKite';

const OPERATORS = ['>=', '<=', '>', '<', '=='] as const;

export function CreateAlertModal({ onClose }: { onClose: () => void }) {
  const create = useCreateKiteAlert();
  const [name, setName] = useState('');
  const [symbol, setSymbol] = useState('');
  const [exchange, setExchange] = useState('NSE');
  const [operator, setOperator] = useState<(typeof OPERATORS)[number]>('>=');
  const [threshold, setThreshold] = useState(0);
  const [error, setError] = useState<string | null>(null);

  const submit = () => {
    setError(null);
    if (!name.trim()) { setError('Enter a name for this alert'); return; }
    if (!symbol.trim()) { setError('Enter a symbol'); return; }
    if (!(threshold > 0)) { setError('Enter a threshold value'); return; }
    create.mutate(
      {
        name: name.trim(), lhs_exchange: exchange, lhs_tradingsymbol: symbol.trim().toUpperCase(),
        lhs_attribute: 'LastTradedPrice', operator, rhs_constant: threshold,
      },
      { onSuccess: onClose, onError: (err: any) => setError(err?.message || 'Create alert failed') },
    );
  };

  const field = (label: string, value: string | number, onChange: (v: string) => void, type: 'text' | 'number' = 'text') => (
    <label style={{ fontSize: 12, color: '#9b9b9b' }}>{label}
      <input type={type} step={type === 'number' ? 0.05 : undefined} value={value} onChange={(e) => onChange(e.target.value)}
        style={{ display: 'block', width: '100%', marginTop: 4, padding: '8px 10px', border: `1px solid ${k.border}`, borderRadius: 3, fontSize: 14 }} />
    </label>
  );

  return (
    <>
      <div onClick={onClose} style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.06)', zIndex: 1100 }} />
      <div style={{ position: 'fixed', top: 80, left: '50%', transform: 'translateX(-50%)', width: 400, background: k.bg, borderRadius: 4, boxShadow: '0 10px 44px rgba(0,0,0,0.28)', zIndex: 1101, fontFamily: k.fontFamily }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '14px 18px', borderBottom: `1px solid ${k.border}` }}>
          <h3 style={{ margin: 0, fontSize: 15, fontWeight: 500, color: '#444' }}>New alert</h3>
          <button onClick={onClose} style={{ background: 'none', border: 'none', fontSize: 18, color: '#9b9b9b', cursor: 'pointer' }}>✕</button>
        </div>
        <div style={{ padding: 18, display: 'flex', flexDirection: 'column', gap: 14 }}>
          {field('Name', name, setName)}
          <div style={{ display: 'flex', gap: 10 }}>
            <div style={{ flex: 2 }}>{field('Symbol', symbol, setSymbol)}</div>
            <div style={{ flex: 1 }}>{field('Exchange', exchange, setExchange)}</div>
          </div>
          <label style={{ fontSize: 12, color: '#9b9b9b' }}>Condition
            <select value={operator} onChange={(e) => setOperator(e.target.value as (typeof OPERATORS)[number])}
              style={{ display: 'block', width: '100%', marginTop: 4, padding: '8px 10px', border: `1px solid ${k.border}`, borderRadius: 3, fontSize: 14 }}>
              {OPERATORS.map((op) => <option key={op} value={op}>Last price {op}</option>)}
            </select>
          </label>
          {field('Threshold', threshold, (v) => setThreshold(Number(v)), 'number')}
          {error && <div style={{ color: k.red, fontSize: 12 }}>{error}</div>}
        </div>
        <div style={{ display: 'flex', gap: 10, padding: '14px 18px', borderTop: `1px solid ${k.border}` }}>
          <button onClick={onClose} style={{ flex: 1, background: '#fff', color: '#444', border: `1px solid ${k.border}`, borderRadius: 3, padding: '9px', fontSize: 13, cursor: 'pointer' }}>Cancel</button>
          <button onClick={submit} disabled={create.isPending} style={{ flex: 1, background: k.blue, color: '#fff', border: 'none', borderRadius: 3, padding: '9px', fontSize: 13, fontWeight: 600, cursor: create.isPending ? 'not-allowed' : 'pointer', opacity: create.isPending ? 0.6 : 1 }}>
            {create.isPending ? '…' : 'Create alert'}
          </button>
        </div>
      </div>
    </>
  );
}
