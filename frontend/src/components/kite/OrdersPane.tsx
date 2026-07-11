import React, { useState, useEffect } from 'react';
import { useKiteOrders, useCancelKiteOrder } from '../../hooks/useKite';
import { useKiteBasketStore } from '../../store/useKiteBasketStore';
import { GttPane } from './GttPane';
import { AlertsPane } from './AlertsPane';
import { InstrumentLabel } from './InstrumentLabel';
import { ModifyOrderModal } from './ModifyOrderModal';
import { OrderHistoryRow } from './OrderHistoryRow';

const S: Record<string, React.CSSProperties> = {
  emptyContainer: { display: 'flex', flexDirection: 'column', alignItems: 'center', marginTop: 100 },
  emptyTitle: { fontSize: 16, color: '#9b9b9b', marginBottom: 20 },
  emptySubtitle: { fontSize: 14, color: '#9b9b9b', marginBottom: 24, textAlign: 'center', lineHeight: '20px', maxWidth: 400 },
  primaryBtn: { background: '#387ed1', color: 'white', padding: '10px 20px', borderRadius: 3, border: 'none', cursor: 'pointer', fontSize: 14, fontWeight: 500 },
  linkBlue: { color: '#387ed1', textDecoration: 'none', fontSize: 13, display: 'flex', alignItems: 'center', gap: 6 },
  th: { textAlign: 'left', color: '#9b9b9b', fontSize: 12, fontWeight: 400, padding: '12px 16px', borderBottom: '1px solid #f1f1f1' },
  td: { padding: '12px 16px', fontSize: 13, color: '#444', borderBottom: '1px solid #f1f1f1' },
};

const STATUS_COLOR: Record<string, { fg: string; bg: string }> = {
  COMPLETE: { fg: '#4caf50', bg: 'rgba(76, 175, 80, 0.1)' },
  OPEN: { fg: '#ff9800', bg: 'rgba(255, 152, 0, 0.1)' },
  'TRIGGER PENDING': { fg: '#ff9800', bg: 'rgba(255, 152, 0, 0.1)' },
  CANCELLED: { fg: '#df514c', bg: 'rgba(223, 81, 76, 0.1)' },
  REJECTED: { fg: '#df514c', bg: 'rgba(223, 81, 76, 0.1)' },
};

function statusStyle(status: string): React.CSSProperties {
  const c = STATUS_COLOR[status] ?? { fg: '#9b9b9b', bg: 'rgba(155, 155, 155, 0.1)' };
  return { padding: '2px 6px', background: c.bg, color: c.fg, borderRadius: 3, fontSize: 11 };
}

const MODIFIABLE_STATUSES = new Set(['OPEN', 'TRIGGER PENDING']);

function OrdersSubPane() {
  const { data: orders } = useKiteOrders(true);
  const cancelOrder = useCancelKiteOrder();
  const [modifyOrder, setModifyOrder] = useState<any | null>(null);
  const [expandedId, setExpandedId] = useState<string | null>(null);

  useEffect(() => {
    if (!modifyOrder || !orders) return;
    const current = orders.find((o: any) => o.order_id === modifyOrder.order_id);
    if (!current || !MODIFIABLE_STATUSES.has(current.status)) {
      setModifyOrder(null);
    }
  }, [orders, modifyOrder]);

  if (!orders || orders.length === 0) {
    return (
      <div style={S.emptyContainer}>
        <div style={{ marginBottom: 24, color: '#dfe1e4' }}>
          <svg width="84" height="84" viewBox="0 0 24 24" fill="none">
            <rect x="5" y="3" width="14" height="18" rx="1" fill="#f1f1f1" stroke="#dfe1e4" strokeWidth="1" />
            <path d="M5 6h2M5 10h2M5 14h2M5 18h2" stroke="#dfe1e4" strokeWidth="1" />
            <rect x="9" y="7" width="6" height="1" fill="#dfe1e4" />
            <rect x="9" y="11" width="8" height="1" fill="#dfe1e4" />
            <rect x="9" y="15" width="7" height="1" fill="#dfe1e4" />
          </svg>
        </div>
        <div style={S.emptyTitle}>You haven't placed any orders today</div>
        <button style={S.primaryBtn}>Get started</button>
        <div style={{ marginTop: 24 }}>
          <a href="#" style={S.linkBlue}>
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <circle cx="12" cy="12" r="10"></circle>
              <polygon points="10 8 16 12 10 16 10 8"></polygon>
            </svg>
            View history
          </a>
        </div>
      </div>
    );
  }

  // Fallback to table if there are orders
  return (
    <div style={{ padding: '0 16px' }}>
      <table style={{ width: '100%', borderCollapse: 'collapse' }}>
        <thead><tr>
          <th style={S.th}>Time</th><th style={S.th}>Type</th><th style={S.th}>Instrument</th>
          <th style={S.th}>Product</th><th style={S.th}>Qty.</th><th style={S.th}>Avg. price</th>
          <th style={S.th}>Status</th><th style={S.th} />
        </tr></thead>
        <tbody>
          {orders.map((o: any) => (
            <React.Fragment key={o.order_id}>
            <tr onClick={() => setExpandedId(expandedId === o.order_id ? null : o.order_id)} style={{ cursor: 'pointer' }}>
              <td style={S.td}>{o.order_timestamp}</td>
              <td style={{ ...S.td, color: o.transaction_type === 'BUY' ? '#4caf50' : '#e53935' }}>
                <span style={{ padding: '2px 6px', background: o.transaction_type === 'BUY' ? 'rgba(76, 175, 80, 0.1)' : 'rgba(229, 57, 53, 0.1)', borderRadius: 3, fontSize: 11 }}>{o.transaction_type}</span>
              </td>
              <td style={{...S.td, whiteSpace: 'nowrap'}}>
                <span style={{ color: '#444', marginRight: 8 }}><InstrumentLabel symbol={o.tradingsymbol} /></span>
                <span style={{ fontSize: 9, color: '#9b9b9b', background: '#f1f1f1', padding: '1px 4px', borderRadius: 2 }}>{o.exchange || 'NSE'}</span>
              </td>
              <td style={S.td}>{o.product}</td>
              <td style={S.td}>{o.filled_quantity ?? 0}/{o.quantity}</td>
              <td style={S.td}>{Number(o.average_price ?? 0).toFixed(2)}</td>
              <td style={S.td}>
                <span style={statusStyle(o.status)}>{o.status}</span>
                {o.variety && o.variety !== 'regular' && (
                  <span style={{ marginLeft: 6, padding: '1px 5px', background: '#f1f1f1', color: '#9b9b9b', borderRadius: 2, fontSize: 9, fontWeight: 600, textTransform: 'uppercase' }}>{o.variety}</span>
                )}
              </td>
              <td style={{ ...S.td, textAlign: 'right' }}>
                {MODIFIABLE_STATUSES.has(o.status) && (
                  <>
                    <span onClick={(e) => { e.stopPropagation(); setModifyOrder(o); }} style={{ cursor: 'pointer', color: '#387ed1', fontSize: 12, marginRight: 12 }}>Modify</span>
                    <span
                      onClick={(e) => {
                        e.stopPropagation();
                        if (cancelOrder.isPending) return;
                        if (window.confirm(`Cancel this ${o.transaction_type} ${o.quantity} ${o.tradingsymbol} order?`)) {
                          cancelOrder.mutate({ id: o.order_id, variety: o.variety });
                        }
                      }}
                      style={{ cursor: cancelOrder.isPending ? 'not-allowed' : 'pointer', color: '#df514c', fontSize: 12, opacity: cancelOrder.isPending ? 0.6 : 1 }}
                    >
                      Cancel
                    </span>
                  </>
                )}
              </td>
            </tr>
            {expandedId === o.order_id && <OrderHistoryRow orderId={o.order_id} colSpan={8} />}
            </React.Fragment>
          ))}
        </tbody>
      </table>
      {modifyOrder && <ModifyOrderModal order={modifyOrder} onClose={() => setModifyOrder(null)} />}
    </div>
  );
}

function BasketsPane({ onOpenBasket }: { onOpenBasket: () => void }) {
  const count = useKiteBasketStore((s) => s.entries.length);
  if (count === 0) {
    return (
      <div style={S.emptyContainer}>
        <div style={{ marginBottom: 24 }}>
          <svg width="84" height="84" viewBox="0 0 24 24" fill="none">
            <path d="M4 8l2 12h12l2-12H4z" fill="#f8f8f8" stroke="#dfe1e4" strokeWidth="1" strokeLinejoin="round" />
            <path d="M8 8V6a4 4 0 018 0v2" stroke="#dfe1e4" strokeWidth="1" strokeLinecap="round" />
            <path d="M6 11h12M7 14h10M8 17h8" stroke="#dfe1e4" strokeWidth="1" strokeLinecap="round" strokeDasharray="1 2" />
            <text x="12" y="15" fill="#dfe1e4" fontSize="5" fontWeight="bold" textAnchor="middle" style={{ letterSpacing: 1 }}>000</text>
          </svg>
        </div>
        <div style={S.emptyTitle}>Basket is empty.</div>
        <button style={S.primaryBtn} onClick={onOpenBasket}>Open basket</button>
      </div>
    );
  }
  return (
    <div style={S.emptyContainer}>
      <div style={{ ...S.emptyTitle, marginBottom: 0 }}>{count} order{count !== 1 ? 's' : ''} staged in your basket.</div>
      <button style={{ ...S.primaryBtn, marginTop: 20 }} onClick={onOpenBasket}>Open basket</button>
    </div>
  );
}

function SipPane() {
  return (
    <div style={S.emptyContainer}>
      <div style={{ marginBottom: 24 }}>
        <svg width="84" height="84" viewBox="0 0 24 24" fill="none">
          <rect x="4" y="5" width="16" height="15" rx="2" fill="#f8f8f8" stroke="#dfe1e4" strokeWidth="1" />
          <path d="M4 9h16" stroke="#dfe1e4" strokeWidth="1" />
          <path d="M8 3v4M16 3v4" stroke="#dfe1e4" strokeWidth="1" strokeLinecap="round" />
          <text x="12" y="16" fill="#dfe1e4" fontSize="6" fontWeight="bold" textAnchor="middle">SIP</text>
        </svg>
      </div>
      <div style={S.emptyTitle}>You haven't created any SIPs.</div>
      <button style={S.primaryBtn}>New SIP</button>
    </div>
  );
}

export function OrdersPane({ onOpenBasket }: { onOpenBasket?: () => void }) {
  const [tab, setTab] = useState('orders');
  const tabs = ['orders', 'gtt', 'baskets', 'sip', 'alerts'];

  const tabLabels: Record<string, string> = {
    orders: 'Orders', gtt: 'GTT', baskets: 'Baskets', sip: 'SIP', alerts: 'Alerts'
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%', background: '#fff', color: '#444' }}>
      <div style={{ padding: '0 32px', borderBottom: '1px solid #f1f1f1', marginTop: 12 }}>
        <h2 style={{ fontSize: 24, fontWeight: 400, color: '#444', margin: '0 0 24px 0' }}>Orders</h2>
        <div style={{ display: 'flex', gap: 32, marginBottom: -1 }}>
          {tabs.map(tName => (
            <div
              key={tName}
              onClick={() => setTab(tName)}
              style={{
                padding: '0 0 12px 0',
                cursor: 'pointer',
                color: tab === tName ? '#ff5722' : '#444',
                borderBottom: tab === tName ? '2px solid #ff5722' : '2px solid transparent',
                fontSize: 14,
                fontWeight: 400,
                transition: 'color 0.2s',
              }}
            >
              {tabLabels[tName]}
            </div>
          ))}
        </div>
      </div>
      <div style={{ flex: 1, overflow: 'auto', padding: '24px 32px' }}>
        {tab === 'orders' && <OrdersSubPane />}
        {tab === 'gtt' && <GttPane />}
        {tab === 'baskets' && <BasketsPane onOpenBasket={onOpenBasket ?? (() => {})} />}
        {tab === 'sip' && <SipPane />}
        {tab === 'alerts' && <AlertsPane />}
      </div>
    </div>
  );
}
