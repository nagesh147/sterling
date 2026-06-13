import React, { useState } from 'react';
import { c as t, tint } from '../../styles/terminalUI';
import {
  useCancelKiteOrder, useKiteOrderHistory, useKiteOrderTrades,
  useKiteOrders, useKiteTrades, useModifyKiteOrder, usePlaceKiteOrder,
} from '../../hooks/useKite';
import type { PlaceOrderBody } from '../../types/kite';
import { GttPane } from './GttPane';

const S: Record<string, React.CSSProperties> = {
  card: { background: t.raised, border: `1px solid ${t.border}`, borderRadius: 10, padding: 14, marginBottom: 14 },
  title: { color: t.dim, fontSize: 11, letterSpacing: 2, marginBottom: 10, fontWeight: 700 },
  grid: { display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(120px, 1fr))', gap: 8 },
  label: { color: t.dim, fontSize: 10, letterSpacing: 1, marginBottom: 3, display: 'block' },
  input: { background: t.bg, color: t.bright, border: `1px solid ${t.border}`, borderRadius: 6, padding: '7px 9px', fontFamily: 'inherit', fontSize: 12, width: '100%', boxSizing: 'border-box' as const },
  inSm: { background: t.bg, color: t.bright, border: `1px solid ${t.border}`, borderRadius: 6, padding: '4px 6px', fontFamily: 'inherit', fontSize: 11, width: 70 },
  th: { textAlign: 'left' as const, color: t.dim, fontSize: 10, fontWeight: 600, padding: '4px 8px', borderBottom: `1px solid ${t.border}` },
  td: { padding: '6px 8px', fontSize: 12, color: t.bright, borderBottom: `1px solid ${tint(t.border, 50)}` },
  hint: { color: t.dim, fontSize: 11 },
  link: { cursor: 'pointer', fontSize: 11 },
  btnBuy: { background: tint(t.green, 12), color: t.green, border: `1px solid ${t.green}`, padding: '8px 18px', borderRadius: 6, cursor: 'pointer', fontFamily: 'inherit', fontSize: 12, fontWeight: 700 },
  btnSell: { background: tint(t.red, 12), color: t.red, border: `1px solid ${t.red}`, padding: '8px 18px', borderRadius: 6, cursor: 'pointer', fontFamily: 'inherit', fontSize: 12, fontWeight: 700 },
};

const sel = (val: string, set: (v: string) => void, opts: string[]) => (
  <select style={S.input} value={val} onChange={(e) => set(e.target.value)}>
    {opts.map((o) => <option key={o} value={o}>{o}</option>)}
  </select>
);

const OPEN = ['OPEN', 'TRIGGER PENDING', 'AMO REQ RECEIVED', 'MODIFY PENDING'];

function OrderRow({ o }: { o: any }) {
  const cancel = useCancelKiteOrder();
  const modify = useModifyKiteOrder();
  const [edit, setEdit] = useState(false);
  const [qty, setQty] = useState(String(o.quantity ?? ''));
  const [price, setPrice] = useState(String(o.price ?? ''));
  const [detail, setDetail] = useState<'history' | 'trades' | null>(null);
  const isOpen = OPEN.includes(o.status);

  const history = useKiteOrderHistory(detail === 'history' ? o.order_id : null);
  const orderTrades = useKiteOrderTrades(detail === 'trades' ? o.order_id : null);

  return (
    <>
      <tr>
        <td style={S.td}>{o.tradingsymbol}</td>
        <td style={{ ...S.td, color: o.transaction_type === 'BUY' ? t.green : t.red }}>{o.transaction_type}</td>
        <td style={S.td}>{o.order_type}</td>
        <td style={{ ...S.td, textAlign: 'right' }}>{o.filled_quantity ?? 0}/{o.quantity}</td>
        <td style={{ ...S.td, textAlign: 'right' }}>{Number(o.price ?? 0).toFixed(2)}</td>
        <td style={{ ...S.td, color: t.dim }}>{o.status}{o.status_message ? ` · ${o.status_message}` : ''}</td>
        <td style={{ ...S.td, textAlign: 'right', whiteSpace: 'nowrap' }}>
          <span style={{ ...S.link, color: t.blue, marginRight: 8 }} onClick={() => setDetail(detail === 'history' ? null : 'history')}>hist</span>
          <span style={{ ...S.link, color: t.cyan, marginRight: 8 }} onClick={() => setDetail(detail === 'trades' ? null : 'trades')}>fills</span>
          {isOpen && <span style={{ ...S.link, color: t.blue, marginRight: 8 }} onClick={() => setEdit(!edit)}>{edit ? 'close' : 'modify'}</span>}
          {isOpen && <span style={{ ...S.link, color: t.red }} onClick={() => cancel.mutate({ id: o.order_id, variety: o.variety || 'regular' })}>cancel</span>}
        </td>
      </tr>
      {detail === 'history' && (
        <tr>
          <td colSpan={7} style={{ background: tint(t.blue, 5) }}>
            <div style={{ padding: 8, fontSize: 11 }}>
              <div style={{ ...S.label, marginBottom: 4 }}>STATUS HISTORY</div>
              {history.isLoading && <span style={S.hint}>Loading…</span>}
              {history.error && <span style={{ color: t.red }}>✗ {(history.error as Error).message}</span>}
              {history.data && (
                <table style={{ width: '100%', borderCollapse: 'collapse' }}>
                  <thead><tr>
                    <th style={{ ...S.th, fontSize: 9 }}>Time</th><th style={{ ...S.th, fontSize: 9 }}>Status</th><th style={{ ...S.th, fontSize: 9 }}>Message</th>
                  </tr></thead>
                  <tbody>
                    {history.data.map((h: any, i: number) => (
                      <tr key={i}>
                        <td style={{ ...S.td, fontSize: 10, color: t.dim }}>{h.order_timestamp}</td>
                        <td style={{ ...S.td, fontSize: 10 }}>{h.status}</td>
                        <td style={{ ...S.td, fontSize: 10, color: t.dim }}>{h.status_message || '—'}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </div>
          </td>
        </tr>
      )}
      {detail === 'trades' && (
        <tr>
          <td colSpan={7} style={{ background: tint(t.cyan, 5) }}>
            <div style={{ padding: 8, fontSize: 11 }}>
              <div style={{ ...S.label, marginBottom: 4 }}>FILLS FOR {o.order_id}</div>
              {orderTrades.isLoading && <span style={S.hint}>Loading…</span>}
              {orderTrades.error && <span style={{ color: t.red }}>✗ {(orderTrades.error as Error).message}</span>}
              {orderTrades.data && orderTrades.data.length > 0 && (
                <table style={{ width: '100%', borderCollapse: 'collapse' }}>
                  <thead><tr>
                    <th style={{ ...S.th, fontSize: 9 }}>Time</th><th style={{ ...S.th, fontSize: 9, textAlign: 'right' }}>Qty</th><th style={{ ...S.th, fontSize: 9, textAlign: 'right' }}>Price</th><th style={{ ...S.th, fontSize: 9 }}>Trade ID</th>
                  </tr></thead>
                  <tbody>
                    {orderTrades.data.map((tr: any, i: number) => (
                      <tr key={tr.trade_id || i}>
                        <td style={{ ...S.td, fontSize: 10, color: t.dim }}>{tr.fill_timestamp || tr.exchange_timestamp || ''}</td>
                        <td style={{ ...S.td, fontSize: 10, textAlign: 'right' }}>{tr.quantity}</td>
                        <td style={{ ...S.td, fontSize: 10, textAlign: 'right' }}>{Number(tr.average_price ?? tr.price ?? 0).toFixed(2)}</td>
                        <td style={{ ...S.td, fontSize: 10, color: t.dim }}>{tr.trade_id}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
              {orderTrades.data && orderTrades.data.length === 0 && <span style={S.hint}>No fills yet.</span>}
            </div>
          </td>
        </tr>
      )}
      {edit && (
        <tr>
          <td style={{ ...S.td, background: tint(t.blue, 5) }} colSpan={7}>
            <div style={{ display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap' }}>
              <span style={S.hint}>Qty</span>
              <input style={S.inSm} value={qty} onChange={(e) => setQty(e.target.value)} />
              <span style={S.hint}>Price</span>
              <input style={S.inSm} value={price} onChange={(e) => setPrice(e.target.value)} />
              <button
                style={{ ...S.link, color: t.green, border: `1px solid ${t.green}`, borderRadius: 6, padding: '4px 10px', background: tint(t.green, 10) }}
                disabled={modify.isPending}
                onClick={() => modify.mutate(
                  { id: o.order_id, variety: o.variety || 'regular', quantity: Number(qty) || undefined, price: price ? Number(price) : undefined, order_type: o.order_type },
                  { onSuccess: () => setEdit(false) },
                )}
              >{modify.isPending ? 'saving…' : 'save'}</button>
              {modify.error && <span style={{ color: t.red, fontSize: 11 }}>✗ {modify.error.message}</span>}
            </div>
          </td>
        </tr>
      )}
    </>
  );
}

export function OrdersPane() {
  const [tab, setTab] = useState('orders');

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
      <div style={{ display: 'flex', gap: 32, marginBottom: 24, borderBottom: `1px solid ${t.border}` }}>
        {['orders', 'gtt', 'baskets', 'sip', 'alerts', 'ipo', 'auctions'].map(tName => (
          <div
            key={tName}
            onClick={() => setTab(tName)}
            style={{
              paddingBottom: 12,
              cursor: 'pointer',
              color: tab === tName ? '#FF5722' : t.dim,
              borderBottom: tab === tName ? '2px solid #FF5722' : '2px solid transparent',
              textTransform: 'capitalize',
              fontSize: 13,
              fontWeight: tab === tName ? 500 : 400,
            }}
          >
            {tName.toUpperCase()}
          </div>
        ))}
      </div>
      <div style={{ flex: 1, overflow: 'auto' }}>
        {tab === 'orders' && <OrdersSubPane />}
        {tab === 'gtt' && <GttPane />}
        {tab === 'ipo' && <IpoPane />}
        {tab !== 'orders' && tab !== 'gtt' && tab !== 'ipo' && (
           <div style={{ padding: 48, textAlign: 'center', color: t.dim }}>
             <div style={{ fontSize: 24, marginBottom: 16 }}>🚧</div>
             <div>{tab.toUpperCase()} feature not implemented yet.</div>
           </div>
        )}
      </div>
    </div>
  );
}

function IpoPane() {
  return (
    <div style={{ padding: '24px 32px' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 24 }}>
        <h2 style={{ fontSize: 18, fontWeight: 400, color: t.bright, margin: 0 }}>IPO</h2>
        <a href="#" style={{ color: '#4184f3', fontSize: 13, textDecoration: 'none' }}>IPO history</a>
      </div>
      <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left', marginBottom: 48 }}>
        <thead><tr>
          <th style={{ color: t.dim, fontSize: 12, fontWeight: 500, padding: '8px 0', borderBottom: `1px solid ${t.border}` }}>Company</th>
          <th style={{ color: t.dim, fontSize: 12, fontWeight: 500, padding: '8px 0', borderBottom: `1px solid ${t.border}` }}>Open</th>
          <th style={{ color: t.dim, fontSize: 12, fontWeight: 500, padding: '8px 0', borderBottom: `1px solid ${t.border}` }}>Close</th>
          <th style={{ color: t.dim, fontSize: 12, fontWeight: 500, padding: '8px 0', borderBottom: `1px solid ${t.border}`, textAlign: 'right' }}>Min qty.</th>
          <th style={{ color: t.dim, fontSize: 12, fontWeight: 500, padding: '8px 0', borderBottom: `1px solid ${t.border}`, textAlign: 'right' }}>Price band</th>
          <th style={{ color: t.dim, fontSize: 12, fontWeight: 500, padding: '8px 0', borderBottom: `1px solid ${t.border}` }}></th>
        </tr></thead>
        <tbody>
          <tr>
            <td colSpan={6} style={{ textAlign: 'center', padding: '64px 0', color: t.dim }}>
              <div style={{ marginBottom: 16 }}>
                <svg width="64" height="64" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1" strokeLinecap="round" strokeLinejoin="round" style={{ opacity: 0.3 }}>
                  <rect x="3" y="3" width="18" height="18" rx="2" ry="2" />
                  <line x1="3" y1="9" x2="21" y2="9" />
                  <line x1="9" y1="21" x2="9" y2="9" />
                </svg>
              </div>
              <div style={{ fontSize: 16, marginBottom: 8, color: t.bright }}>No ongoing IPOs</div>
              <div style={{ fontSize: 13 }}>There are no active IPOs to apply for right now.</div>
            </td>
          </tr>
        </tbody>
      </table>
    </div>
  );
}

function OrdersSubPane() {
  const place = usePlaceKiteOrder();
  const { data: orders } = useKiteOrders(true);
  const { data: trades } = useKiteTrades(true);

  const [f, setF] = useState({
    tradingsymbol: '', exchange: 'NSE', quantity: '1', order_type: 'MARKET',
    product: 'MIS', variety: 'regular', price: '', trigger_price: '', validity: 'DAY',
  });
  const up = (k: string) => (v: string) => setF((s) => ({ ...s, [k]: v }));

  const submit = (side: 'BUY' | 'SELL') => {
    const body: PlaceOrderBody = {
      tradingsymbol: f.tradingsymbol.trim().toUpperCase(), exchange: f.exchange,
      transaction_type: side, quantity: Number(f.quantity) || 1,
      order_type: f.order_type as PlaceOrderBody['order_type'], product: f.product as PlaceOrderBody['product'],
      variety: f.variety, validity: f.validity,
      price: f.price ? Number(f.price) : null, trigger_price: f.trigger_price ? Number(f.trigger_price) : null,
    };
    place.mutate(body);
  };

  return (
    <div>
      <div style={S.card}>
        <div style={S.title}>PLACE ORDER</div>
        <div style={S.grid}>
          <div><label style={S.label}>SYMBOL</label><input style={S.input} value={f.tradingsymbol} onChange={(e) => up('tradingsymbol')(e.target.value)} placeholder="INFY" /></div>
          <div><label style={S.label}>EXCHANGE</label>{sel(f.exchange, up('exchange'), ['NSE', 'NFO', 'BSE', 'MCX', 'CDS'])}</div>
          <div><label style={S.label}>QTY</label><input style={S.input} value={f.quantity} onChange={(e) => up('quantity')(e.target.value)} /></div>
          <div><label style={S.label}>TYPE</label>{sel(f.order_type, up('order_type'), ['MARKET', 'LIMIT', 'SL', 'SL-M'])}</div>
          <div><label style={S.label}>PRODUCT</label>{sel(f.product, up('product'), ['MIS', 'CNC', 'NRML'])}</div>
          <div><label style={S.label}>VARIETY</label>{sel(f.variety, up('variety'), ['regular', 'amo', 'iceberg'])}</div>
          {(f.order_type === 'LIMIT' || f.order_type === 'SL') && (
            <div><label style={S.label}>PRICE</label><input style={S.input} value={f.price} onChange={(e) => up('price')(e.target.value)} /></div>
          )}
          {(f.order_type === 'SL' || f.order_type === 'SL-M') && (
            <div><label style={S.label}>TRIGGER</label><input style={S.input} value={f.trigger_price} onChange={(e) => up('trigger_price')(e.target.value)} /></div>
          )}
          <div><label style={S.label}>VALIDITY</label>{sel(f.validity, up('validity'), ['DAY', 'IOC'])}</div>
        </div>
        <div style={{ display: 'flex', gap: 10, marginTop: 12 }}>
          <button style={S.btnBuy} disabled={!f.tradingsymbol.trim() || place.isPending} onClick={() => submit('BUY')}>BUY</button>
          <button style={S.btnSell} disabled={!f.tradingsymbol.trim() || place.isPending} onClick={() => submit('SELL')}>SELL</button>
          {place.isSuccess && <span style={{ color: t.green, fontSize: 11, alignSelf: 'center' }}>✓ {place.data?.order_id}{place.data?.deduplicated ? ' (dedup)' : ''}</span>}
          {place.error && <span style={{ color: t.red, fontSize: 11, alignSelf: 'center' }}>✗ {place.error.message}</span>}
        </div>
      </div>

      <div style={S.card}>
        <div style={S.title}>ORDER BOOK</div>
        {(!orders || orders.length === 0) && <div style={S.hint}>No orders today.</div>}
        {orders && orders.length > 0 && (
          <table style={{ width: '100%', borderCollapse: 'collapse' }}>
            <thead><tr>
              <th style={S.th}>Symbol</th><th style={S.th}>Side</th><th style={S.th}>Type</th>
              <th style={{ ...S.th, textAlign: 'right' }}>Filled/Qty</th><th style={{ ...S.th, textAlign: 'right' }}>Price</th>
              <th style={S.th}>Status</th><th style={S.th} />
            </tr></thead>
            <tbody>
              {orders.map((o: any) => <OrderRow key={o.order_id} o={o} />)}
            </tbody>
          </table>
        )}
      </div>

      <div style={S.card}>
        <div style={S.title}>TODAY&apos;S TRADES</div>
        {(!trades || trades.length === 0) && <div style={S.hint}>No executed trades today.</div>}
        {trades && trades.length > 0 && (
          <table style={{ width: '100%', borderCollapse: 'collapse' }}>
            <thead><tr>
              <th style={S.th}>Symbol</th><th style={S.th}>Side</th>
              <th style={{ ...S.th, textAlign: 'right' }}>Qty</th><th style={{ ...S.th, textAlign: 'right' }}>Price</th>
              <th style={S.th}>Time</th>
            </tr></thead>
            <tbody>
              {trades.map((tr: any, i: number) => (
                <tr key={tr.trade_id || i}>
                  <td style={S.td}>{tr.tradingsymbol}</td>
                  <td style={{ ...S.td, color: tr.transaction_type === 'BUY' ? t.green : t.red }}>{tr.transaction_type}</td>
                  <td style={{ ...S.td, textAlign: 'right' }}>{tr.quantity}</td>
                  <td style={{ ...S.td, textAlign: 'right' }}>{Number(tr.average_price ?? tr.price ?? 0).toFixed(2)}</td>
                  <td style={{ ...S.td, color: t.dim }}>{tr.fill_timestamp || tr.exchange_timestamp || ''}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
