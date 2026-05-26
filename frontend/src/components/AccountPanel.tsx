import React, { useState } from 'react';
import {
  useAccountInfo, useAccountSummary, useAccountBalances,
  useAccountPositions, useAccountOrders, useAccountFills,
} from '../hooks/useAccount';
import { fmtN, fmtUSD } from '../utils/fmt';
import { downloadCSV } from '../hooks/useDownload';
import type { AccountPosition, AccountOrder, AccountFill, AssetBalance } from '../hooks/useAccount';
import { c as ui, tint } from '../styles/terminalUI';

const S: Record<string, React.CSSProperties> = {
  card: { background: ui.raised, border: `1px solid ${ui.border}`, borderRadius: 6, padding: 16, marginBottom: 16 },
  title: { color: ui.dim, fontSize: 11, letterSpacing: 2, marginBottom: 12 },
  tabs: { display: 'flex', gap: 2, marginBottom: 16, borderBottom: `1px solid ${ui.border}` },
  tab: { background: 'none', border: 'none', cursor: 'pointer', fontFamily: 'inherit', fontSize: 11, letterSpacing: 1, padding: '6px 14px', marginBottom: -1 },
  grid: { display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 12, marginBottom: 14 },
  cell: { display: 'flex', flexDirection: 'column', gap: 3 },
  key: { color: ui.dim, fontSize: 10, letterSpacing: 1 },
  val: { fontSize: 14, fontWeight: 600, color: ui.bright },
  table: { width: '100%', borderCollapse: 'collapse', fontSize: 11 },
  th: { color: ui.dim, textAlign: 'left', padding: '5px 8px', borderBottom: `1px solid ${ui.border}`, letterSpacing: 1 },
  td: { padding: '6px 8px', borderBottom: `1px solid ${ui.border}`, color: ui.text },
  noData: { color: ui.dim, fontSize: 12, textAlign: 'center', padding: 24 },
  paperWarn: {
    background: ui.amber + '11', border: `1px solid ${ui.amber}` + '44',
    borderRadius: 4, padding: '6px 12px', fontSize: 11, color: ui.amber, marginBottom: 12,
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
            <td style={{ ...S.td, fontWeight: 700, color: ui.bright }}>{b.asset}</td>
            <td style={S.td}>{fmtN(b.available, 6)}</td>
            <td style={S.td}>{fmtN(b.locked, 6)}</td>
            <td style={S.td}>{fmtN(b.total, 6)}</td>
          </tr>
        ))}
        {data.balances.length === 0 && (
          <tr><td colSpan={4} style={{ ...S.td, textAlign: 'center', color: ui.dim }}>No balances</td></tr>
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
            <td style={{ ...S.td, color: ui.blue }}>{p.symbol}</td>
            <td style={{ ...S.td, color: p.side === 'long' ? ui.green : ui.red }}>{p.side.toUpperCase()}</td>
            <td style={S.td}>{fmtN(Math.abs(p.size), 4)}</td>
            <td style={S.td}>${fmtN(p.entry_price, 2)}</td>
            <td style={S.td}>${fmtN(p.mark_price, 2)}</td>
            <td style={{ ...S.td, color: p.unrealized_pnl >= 0 ? ui.green : ui.red, fontWeight: 600 }}>
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
            <td style={{ ...S.td, color: ui.blue }}>{o.symbol}</td>
            <td style={{ ...S.td, color: o.side === 'buy' ? ui.green : ui.red }}>{o.side.toUpperCase()}</td>
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
            <td style={{ ...S.td, color: ui.blue }}>{f.symbol}</td>
            <td style={{ ...S.td, color: f.side === 'buy' ? ui.green : ui.red }}>{f.side.toUpperCase()}</td>
            <td style={S.td}>{fmtN(f.size, 4)}</td>
            <td style={S.td}>${fmtN(f.price, 2)}</td>
            <td style={S.td}>{fmtN(f.fee, 6)} {f.fee_asset}</td>
            <td style={{ ...S.td, color: f.pnl >= 0 ? ui.green : ui.red }}>
              {f.pnl >= 0 ? '+' : ''}{fmtN(f.pnl, 2)}
            </td>
            <td style={{ ...S.td, color: ui.dim }}>{new Date(f.created_at_ms).toLocaleTimeString()}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

type Tab = 'overview' | 'balances' | 'positions' | 'orders' | 'fills';

interface Props { underlying?: string }

export function AccountPanel({ underlying = '' }: Props) {
  const { data: info } = useAccountInfo();
  const { data: summary, isLoading, isError } = useAccountSummary();
  const [activeTab, setActiveTab] = useState<Tab>('overview');

  // No exchange configured at all
  if (info && !info.active) {
    return (
      <div style={S.card}>
        <div style={S.title}>ACCOUNT</div>
        <div style={{ color: ui.dim, fontSize: 12, lineHeight: 1.7 }}>
          No exchange account configured.<br />
          Go to <span style={{ color: ui.blue }}>Account → Exchanges</span> tab, click
          <strong style={{ color: ui.bright }}> + ADD EXCHANGE</strong>, then set it as active.
        </div>
      </div>
    );
  }

  if (isLoading) return <div style={S.card}><div style={{ color: ui.dim, fontSize: 12 }}>Loading account…</div></div>;

  if (isError || !summary) {
    return (
      <div style={S.card}>
        <div style={S.title}>ACCOUNT</div>
        <div style={{ color: ui.red, fontSize: 12 }}>
          Failed to load account data. Check exchange credentials in the Exchanges tab.
        </div>
      </div>
    );
  }

  const pf = summary.portfolio;
  const unrColor = (pf?.unrealized_pnl_usd ?? 0) >= 0 ? ui.green : ui.red;
  const tabStyle = (t: Tab): React.CSSProperties => ({
    ...S.tab,
    color: activeTab === t ? ui.bright : ui.dim,
    borderBottom: activeTab === t ? `2px solid ${ui.green}` : '2px solid transparent',
  });

  return (
    <div style={S.card}>
      <div style={S.title}>
        ACCOUNT · {summary.display_name}
        {summary.is_paper && <span style={{ color: ui.amber, marginLeft: 8, fontSize: 10 }}>PAPER</span>}
        {!summary.is_connected && <span style={{ color: ui.red, marginLeft: 8, fontSize: 10 }}>DISCONNECTED</span>}
      </div>

      {summary.is_paper && (
        <div style={S.paperWarn}>
          Paper mode — mock data. Update API key/secret in Exchange Accounts to enable live data.
        </div>
      )}

      {summary.error && !summary.is_paper && (
        <div style={{ color: ui.red, fontSize: 12, marginBottom: 12 }}>{summary.error}</div>
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
            <span style={{ ...S.val, color: ui.green }}>${fmtN(pf.margin_available, 2)}</span>
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
                <td style={{ ...S.td, fontWeight: 700, color: ui.bright, width: 80 }}>{b.asset}</td>
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
      <div style={{ display: 'flex', gap: 8, marginTop: 12, borderTop: `1px solid ${ui.border}`, paddingTop: 12 }}>
        <button
          style={{ background: ui.raised, color: ui.blue, border: `1px solid ${ui.border}`, padding: '4px 12px', borderRadius: 3, cursor: 'pointer', fontFamily: 'inherit', fontSize: 11 }}
          onClick={() => downloadCSV('/api/v1/account/fills/export', 'sterling_fills.csv')}
        >
          ↓ FILLS CSV
        </button>
        <button
          style={{ background: ui.raised, color: ui.blue, border: `1px solid ${ui.border}`, padding: '4px 12px', borderRadius: 3, cursor: 'pointer', fontFamily: 'inherit', fontSize: 11 }}
          onClick={() => downloadCSV('/api/v1/account/positions/export', 'sterling_positions.csv')}
        >
          ↓ POSITIONS CSV
        </button>
      </div>
    </div>
  );
}
