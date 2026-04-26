import React, { useState } from 'react';
import {
  useAccountSummary, useAccountBalances,
  useAccountPositions, useAccountOrders, useAccountFills,
} from '../hooks/useAccount';
import { fmtN, fmtUSD } from '../utils/fmt';
import { downloadCSV } from '../hooks/useDownload';
import type { AccountPosition, AccountOrder, AccountFill, AssetBalance } from '../hooks/useAccount';

const S: Record<string, React.CSSProperties> = {
  card: { background: '#141414', border: '1px solid #222', borderRadius: 6, padding: 16, marginBottom: 16 },
  title: { color: '#888', fontSize: 11, letterSpacing: 2, marginBottom: 12 },
  tabs: { display: 'flex', gap: 2, marginBottom: 16, borderBottom: '1px solid #1e1e1e' },
  tab: { background: 'none', border: 'none', cursor: 'pointer', fontFamily: 'inherit', fontSize: 11, letterSpacing: 1, padding: '6px 14px', marginBottom: -1 },
  grid: { display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 12, marginBottom: 14 },
  cell: { display: 'flex', flexDirection: 'column', gap: 3 },
  key: { color: '#555', fontSize: 10, letterSpacing: 1 },
  val: { fontSize: 14, fontWeight: 600, color: '#e0e0e0' },
  table: { width: '100%', borderCollapse: 'collapse', fontSize: 11 },
  th: { color: '#444', textAlign: 'left', padding: '5px 8px', borderBottom: '1px solid #1e1e1e', letterSpacing: 1 },
  td: { padding: '6px 8px', borderBottom: '1px solid #141414', color: '#aaa' },
  noData: { color: '#444', fontSize: 12, textAlign: 'center', padding: 24 },
  paperWarn: {
    background: '#f0a500' + '11', border: '1px solid #f0a500' + '44',
    borderRadius: 4, padding: '6px 12px', fontSize: 11, color: '#f0a500', marginBottom: 12,
  },
};

function BalancesTab() {
  const { data } = useAccountBalances();
  if (!data) return <div style={S.noData}>Loading balances…</div>;
  return (
    <table style={S.table}>
      <thead><tr>{['ASSET', 'AVAILABLE', 'LOCKED', 'TOTAL'].map(h => <th key={h} style={S.th}>{h}</th>)}</tr></thead>
      <tbody>
        {data.balances.map((b, i) => (
          <tr key={i}>
            <td style={{ ...S.td, fontWeight: 700, color: '#e0e0e0' }}>{b.asset}</td>
            <td style={S.td}>{fmtN(b.available, 6)}</td>
            <td style={S.td}>{fmtN(b.locked, 6)}</td>
            <td style={S.td}>{fmtN(b.total, 6)}</td>
          </tr>
        ))}
        {data.balances.length === 0 && (
          <tr><td colSpan={4} style={{ ...S.td, textAlign: 'center', color: '#444' }}>No balances</td></tr>
        )}
      </tbody>
    </table>
  );
}

function PositionsTab({ underlying }: { underlying: string }) {
  const { data } = useAccountPositions(underlying);
  if (!data) return <div style={S.noData}>Loading positions…</div>;
  if (data.count === 0) return <div style={S.noData}>No open positions{underlying ? ` for ${underlying}` : ''}.</div>;
  return (
    <table style={S.table}>
      <thead><tr>{['SYMBOL', 'SIDE', 'SIZE', 'ENTRY', 'MARK', 'UNR PNL', 'MARGIN'].map(h => <th key={h} style={S.th}>{h}</th>)}</tr></thead>
      <tbody>
        {data.positions.map((p, i) => (
          <tr key={i}>
            <td style={{ ...S.td, color: '#aaddff' }}>{p.symbol}</td>
            <td style={{ ...S.td, color: p.side === 'long' ? '#44cc88' : '#cc4444' }}>{p.side.toUpperCase()}</td>
            <td style={S.td}>{fmtN(Math.abs(p.size), 4)}</td>
            <td style={S.td}>${fmtN(p.entry_price, 2)}</td>
            <td style={S.td}>${fmtN(p.mark_price, 2)}</td>
            <td style={{ ...S.td, color: p.unrealized_pnl >= 0 ? '#44cc88' : '#cc4444', fontWeight: 600 }}>
              {p.unrealized_pnl >= 0 ? '+' : ''}{fmtN(p.unrealized_pnl, 2)}
            </td>
            <td style={S.td}>{fmtN(p.margin, 4)}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

function OrdersTab({ underlying }: { underlying: string }) {
  const { data } = useAccountOrders(underlying);
  if (!data) return <div style={S.noData}>Loading orders…</div>;
  if (data.count === 0) return <div style={S.noData}>No open orders.</div>;
  return (
    <table style={S.table}>
      <thead><tr>{['SYMBOL', 'SIDE', 'TYPE', 'SIZE', 'PRICE', 'FILLED', 'STATUS'].map(h => <th key={h} style={S.th}>{h}</th>)}</tr></thead>
      <tbody>
        {data.orders.map((o, i) => (
          <tr key={i}>
            <td style={{ ...S.td, color: '#aaddff' }}>{o.symbol}</td>
            <td style={{ ...S.td, color: o.side === 'buy' ? '#44cc88' : '#cc4444' }}>{o.side.toUpperCase()}</td>
            <td style={S.td}>{o.order_type}</td>
            <td style={S.td}>{fmtN(o.size, 4)}</td>
            <td style={S.td}>${fmtN(o.price, 2)}</td>
            <td style={S.td}>{fmtN(o.filled_size, 4)}</td>
            <td style={S.td}>{o.status}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

function FillsTab() {
  const { data } = useAccountFills(50);
  if (!data) return <div style={S.noData}>Loading fills…</div>;
  if (data.count === 0) return <div style={S.noData}>No recent fills.</div>;
  return (
    <table style={S.table}>
      <thead><tr>{['SYMBOL', 'SIDE', 'SIZE', 'PRICE', 'FEE', 'PNL', 'TIME'].map(h => <th key={h} style={S.th}>{h}</th>)}</tr></thead>
      <tbody>
        {data.fills.map((f, i) => (
          <tr key={i}>
            <td style={{ ...S.td, color: '#aaddff' }}>{f.symbol}</td>
            <td style={{ ...S.td, color: f.side === 'buy' ? '#44cc88' : '#cc4444' }}>{f.side.toUpperCase()}</td>
            <td style={S.td}>{fmtN(f.size, 4)}</td>
            <td style={S.td}>${fmtN(f.price, 2)}</td>
            <td style={S.td}>{fmtN(f.fee, 6)} {f.fee_asset}</td>
            <td style={{ ...S.td, color: f.pnl >= 0 ? '#44cc88' : '#cc4444' }}>
              {f.pnl >= 0 ? '+' : ''}{fmtN(f.pnl, 2)}
            </td>
            <td style={{ ...S.td, color: '#555' }}>{new Date(f.created_at_ms).toLocaleTimeString()}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

type Tab = 'overview' | 'balances' | 'positions' | 'orders' | 'fills';

interface Props { underlying?: string }

export function AccountPanel({ underlying = '' }: Props) {
  const { data: summary, isLoading } = useAccountSummary();
  const [activeTab, setActiveTab] = useState<Tab>('overview');

  if (isLoading) return <div style={S.card}><div style={{ color: '#444', fontSize: 12 }}>Loading account…</div></div>;
  if (!summary) return null;

  const pf = summary.portfolio;
  const unrColor = (pf?.unrealized_pnl_usd ?? 0) >= 0 ? '#44cc88' : '#cc4444';
  const tabStyle = (t: Tab): React.CSSProperties => ({
    ...S.tab,
    color: activeTab === t ? '#e0e0e0' : '#555',
    borderBottom: activeTab === t ? '2px solid #44cc88' : '2px solid transparent',
  });

  return (
    <div style={S.card}>
      <div style={S.title}>
        ACCOUNT · {summary.display_name}
        {summary.is_paper && <span style={{ color: '#f0a500', marginLeft: 8, fontSize: 10 }}>PAPER</span>}
        {!summary.is_connected && <span style={{ color: '#cc4444', marginLeft: 8, fontSize: 10 }}>DISCONNECTED</span>}
      </div>

      {summary.is_paper && (
        <div style={S.paperWarn}>
          Paper mode — mock data. Update API key/secret in Exchange Accounts to enable live data.
        </div>
      )}

      {summary.error && !summary.is_paper && (
        <div style={{ color: '#cc4444', fontSize: 12, marginBottom: 12 }}>{summary.error}</div>
      )}

      {pf && (
        <div style={S.grid}>
          <div style={S.cell}>
            <span style={S.key}>TOTAL BALANCE</span>
            <span style={S.val}>${fmtUSD(pf.total_balance_usd)}</span>
          </div>
          <div style={S.cell}>
            <span style={S.key}>UNREALIZED P&L</span>
            <span style={{ ...S.val, color: unrColor }}>
              {(pf.unrealized_pnl_usd ?? 0) >= 0 ? '+' : ''}${fmtN(pf.unrealized_pnl_usd, 2)}
            </span>
          </div>
          <div style={S.cell}>
            <span style={S.key}>MARGIN USED</span>
            <span style={S.val}>${fmtN(pf.margin_used, 2)}</span>
          </div>
          <div style={S.cell}>
            <span style={S.key}>MARGIN FREE</span>
            <span style={{ ...S.val, color: '#44cc88' }}>${fmtN(pf.margin_available, 2)}</span>
          </div>
          <div style={S.cell}>
            <span style={S.key}>OPEN POSITIONS</span>
            <span style={S.val}>{pf.positions_count}</span>
          </div>
          <div style={S.cell}>
            <span style={S.key}>OPEN ORDERS</span>
            <span style={S.val}>{pf.open_orders_count}</span>
          </div>
        </div>
      )}

      <div style={S.tabs}>
        {(['overview', 'balances', 'positions', 'orders', 'fills'] as Tab[]).map(t => (
          <button key={t} style={tabStyle(t)} onClick={() => setActiveTab(t)}>
            {t.toUpperCase()}
          </button>
        ))}
      </div>

      {activeTab === 'overview' && pf && (
        <table style={S.table}>
          <tbody>
            {pf.balances.slice(0, 5).map((b, i) => (
              <tr key={i}>
                <td style={{ ...S.td, fontWeight: 700, color: '#e0e0e0', width: 80 }}>{b.asset}</td>
                <td style={S.td}>Available: {fmtN(b.available, 6)}</td>
                <td style={S.td}>Locked: {fmtN(b.locked, 6)}</td>
                <td style={S.td}>Total: {fmtN(b.total, 6)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
      {activeTab === 'balances' && <BalancesTab />}
      {activeTab === 'positions' && <PositionsTab underlying={underlying} />}
      {activeTab === 'orders' && <OrdersTab underlying={underlying} />}
      {activeTab === 'fills' && <FillsTab />}

      {/* CSV export buttons */}
      <div style={{ display: 'flex', gap: 8, marginTop: 12, borderTop: '1px solid #1e1e1e', paddingTop: 12 }}>
        <button
          style={{ background: '#1a1a2a', color: '#88aaff', border: '1px solid #334', padding: '4px 12px', borderRadius: 3, cursor: 'pointer', fontFamily: 'inherit', fontSize: 11 }}
          onClick={() => downloadCSV('/api/v1/account/fills/export', 'sterling_fills.csv')}
        >
          ↓ FILLS CSV
        </button>
        <button
          style={{ background: '#1a1a2a', color: '#88aaff', border: '1px solid #334', padding: '4px 12px', borderRadius: 3, cursor: 'pointer', fontFamily: 'inherit', fontSize: 11 }}
          onClick={() => downloadCSV('/api/v1/account/positions/export', 'sterling_positions.csv')}
        >
          ↓ POSITIONS CSV
        </button>
      </div>
    </div>
  );
}
