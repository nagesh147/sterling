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
  emptyTitle: { fontSize: 16, color: 'var(--k-dim)', marginBottom: 20 },
  emptySubtitle: { fontSize: 14, color: 'var(--k-dim)', marginBottom: 24, textAlign: 'center', lineHeight: '20px', maxWidth: 400 },
  primaryBtn: { background: 'var(--k-blue-kite)', color: 'var(--k-on-accent)', padding: '10px 20px', borderRadius: 3, border: 'none', cursor: 'pointer', fontSize: 14, fontWeight: 500 },
  linkBlue: { color: 'var(--k-blue-kite)', textDecoration: 'none', fontSize: 13, display: 'flex', alignItems: 'center', gap: 6 },
  th: { textAlign: 'left', color: 'var(--k-dim)', fontSize: 12, fontWeight: 400, padding: '12px 16px', borderBottom: '1px solid var(--k-surface-hover)' },
  td: { padding: '12px 16px', fontSize: 13, color: 'var(--k-text)', borderBottom: '1px solid var(--k-surface-hover)' },
};

const STATUS_COLOR: Record<string, { fg: string; bg: string }> = {
  COMPLETE: { fg: 'var(--k-green)', bg: 'rgba(76, 175, 80, 0.1)' },
  OPEN: { fg: 'var(--k-amber-2)', bg: 'rgba(255, 152, 0, 0.1)' },
  'TRIGGER PENDING': { fg: 'var(--k-amber-2)', bg: 'rgba(255, 152, 0, 0.1)' },
  CANCELLED: { fg: 'var(--k-red)', bg: 'rgba(223, 81, 76, 0.1)' },
  REJECTED: { fg: 'var(--k-red)', bg: 'rgba(223, 81, 76, 0.1)' },
};

function statusStyle(status: string): React.CSSProperties {
  const c = STATUS_COLOR[status] ?? { fg: 'var(--k-dim)', bg: 'rgba(155, 155, 155, 0.1)' };
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
        <div style={{ marginBottom: 24, color: 'var(--k-border-strong)' }}>
          <svg width="84" height="84" viewBox="0 0 24 24" fill="none">
            <rect x="5" y="3" width="14" height="18" rx="1" fill="var(--k-surface-hover)" stroke="var(--k-border-strong)" strokeWidth="1" />
            <path d="M5 6h2M5 10h2M5 14h2M5 18h2" stroke="var(--k-border-strong)" strokeWidth="1" />
            <rect x="9" y="7" width="6" height="1" fill="var(--k-border-strong)" />
            <rect x="9" y="11" width="8" height="1" fill="var(--k-border-strong)" />
            <rect x="9" y="15" width="7" height="1" fill="var(--k-border-strong)" />
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
              <td style={{ ...S.td, color: o.transaction_type === 'BUY' ? 'var(--k-green)' : 'var(--k-red-strong)' }}>
                <span style={{ padding: '2px 6px', background: o.transaction_type === 'BUY' ? 'rgba(76, 175, 80, 0.1)' : 'rgba(229, 57, 53, 0.1)', borderRadius: 3, fontSize: 11 }}>{o.transaction_type}</span>
              </td>
              <td style={{...S.td, whiteSpace: 'nowrap'}}>
                <span style={{ color: 'var(--k-text)', marginRight: 8 }}><InstrumentLabel symbol={o.tradingsymbol} /></span>
                <span style={{ fontSize: 9, color: 'var(--k-dim)', background: 'var(--k-surface-hover)', padding: '1px 4px', borderRadius: 2 }}>{o.exchange || 'NSE'}</span>
              </td>
              <td style={S.td}>{o.product}</td>
              <td style={S.td}>{o.filled_quantity ?? 0}/{o.quantity}</td>
              <td style={S.td}>{Number(o.average_price ?? 0).toFixed(2)}</td>
              <td style={S.td}>
                <span style={statusStyle(o.status)}>{o.status}</span>
                {o.variety && o.variety !== 'regular' && (
                  <span style={{ marginLeft: 6, padding: '1px 5px', background: 'var(--k-surface-hover)', color: 'var(--k-dim)', borderRadius: 2, fontSize: 9, fontWeight: 600, textTransform: 'uppercase' }}>{o.variety}</span>
                )}
              </td>
              <td style={{ ...S.td, textAlign: 'right' }}>
                {MODIFIABLE_STATUSES.has(o.status) && (
                  <>
                    <span onClick={(e) => { e.stopPropagation(); setModifyOrder(o); }} style={{ cursor: 'pointer', color: 'var(--k-blue-kite)', fontSize: 12, marginRight: 12 }}>Modify</span>
                    <span
                      onClick={(e) => {
                        e.stopPropagation();
                        if (cancelOrder.isPending) return;
                        if (window.confirm(`Cancel this ${o.transaction_type} ${o.quantity} ${o.tradingsymbol} order?`)) {
                          cancelOrder.mutate({ id: o.order_id, variety: o.variety });
                        }
                      }}
                      style={{ cursor: cancelOrder.isPending ? 'not-allowed' : 'pointer', color: 'var(--k-red)', fontSize: 12, opacity: cancelOrder.isPending ? 0.6 : 1 }}
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
            <path d="M4 8l2 12h12l2-12H4z" fill="#f8f8f8" stroke="var(--k-border-strong)" strokeWidth="1" strokeLinejoin="round" />
            <path d="M8 8V6a4 4 0 018 0v2" stroke="var(--k-border-strong)" strokeWidth="1" strokeLinecap="round" />
            <path d="M6 11h12M7 14h10M8 17h8" stroke="var(--k-border-strong)" strokeWidth="1" strokeLinecap="round" strokeDasharray="1 2" />
            <text x="12" y="15" fill="var(--k-border-strong)" fontSize="5" fontWeight="bold" textAnchor="middle" style={{ letterSpacing: 1 }}>000</text>
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
          <rect x="4" y="5" width="16" height="15" rx="2" fill="#f8f8f8" stroke="var(--k-border-strong)" strokeWidth="1" />
          <path d="M4 9h16" stroke="var(--k-border-strong)" strokeWidth="1" />
          <path d="M8 3v4M16 3v4" stroke="var(--k-border-strong)" strokeWidth="1" strokeLinecap="round" />
          <text x="12" y="16" fill="var(--k-border-strong)" fontSize="6" fontWeight="bold" textAnchor="middle">SIP</text>
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
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%', background: 'var(--k-bg)', color: 'var(--k-text)' }}>
      <div style={{ padding: '0 32px', borderBottom: '1px solid var(--k-surface-hover)', marginTop: 12 }}>
        <h2 style={{ fontSize: 24, fontWeight: 400, color: 'var(--k-text)', margin: '0 0 24px 0' }}>Orders</h2>
        <div style={{ display: 'flex', gap: 32, marginBottom: -1 }}>
          {tabs.map(tName => (
            <div
              key={tName}
              onClick={() => setTab(tName)}
              style={{
                padding: '0 0 12px 0',
                cursor: 'pointer',
                color: tab === tName ? 'var(--k-orange)' : 'var(--k-text)',
                borderBottom: tab === tName ? '2px solid var(--k-orange)' : '2px solid transparent',
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
