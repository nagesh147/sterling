import React, { useState } from 'react';
import { ThreeColumnLayout, RightSection } from '../ThreeColumnLayout';
import { c as t } from '../../styles/terminalUI';
import { useKiteStatus } from '../../hooks/useKite';
import { ConnectPane } from './ConnectPane';
import { MarketWatchPane } from './MarketWatchPane';
import { PortfolioPane } from './PortfolioPane';
import { OrdersPane } from './OrdersPane';
import { GttPane } from './GttPane';
import { FundsPane } from './FundsPane';
import { MutualFundsPane } from './MutualFundsPane';

type Section = 'connect' | 'watch' | 'portfolio' | 'orders' | 'gtt' | 'funds' | 'mf';

const NAV: { id: Section; label: string; color: string }[] = [
  { id: 'connect', label: 'Connect & Keys', color: 'var(--t-blue)' },
  { id: 'watch', label: 'Market Watch', color: 'var(--t-cyan)' },
  { id: 'portfolio', label: 'Holdings & Positions', color: 'var(--t-green)' },
  { id: 'orders', label: 'Orders & Trades', color: 'var(--t-purple)' },
  { id: 'gtt', label: 'GTT', color: 'var(--t-amber)' },
  { id: 'funds', label: 'Funds & Profile', color: 'var(--t-green)' },
  { id: 'mf', label: 'Mutual Funds', color: 'var(--t-cyan)' },
];

const HEADERS: Record<Section, { title: string; sub: string }> = {
  connect: { title: 'Connect Zerodha Kite', sub: 'Manage API keys, daily login & funds' },
  watch: { title: 'Market Watch', sub: 'Search instruments & live quotes (NSE/NFO/BSE/MCX)' },
  portfolio: { title: 'Holdings & Positions', sub: 'Equity holdings + F&O positions with P&L' },
  orders: { title: 'Orders & Trades', sub: 'Place, modify, cancel orders + today’s tradebook' },
  gtt: { title: 'GTT Triggers', sub: 'Good-Till-Triggered orders' },
  funds: { title: 'Funds & Profile', sub: 'Segment-wise margins, balances & account profile' },
  mf: { title: 'Mutual Funds', sub: 'MF holdings, orders & SIPs' },
};

function StatusSidebar() {
  const { data: s } = useKiteStatus();
  const col = !s ? t.dim : s.connected ? (s.is_paper ? t.amber : t.green) : t.red;
  return (
    <RightSection label="Kite Session">
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 6 }}>
        <span style={{ width: 9, height: 9, borderRadius: 5, background: col, display: 'inline-block' }} />
        <span style={{ color: t.bright, fontWeight: 700, fontSize: 12 }}>
          {!s ? '…' : s.connected ? (s.is_paper ? 'Paper · live data' : 'Live') : 'Disconnected'}
        </span>
      </div>
      <div style={{ color: t.dim, fontSize: 11, lineHeight: 1.6 }}>
        {s?.message}
        {s?.user_name ? <><br />User: {s.user_name}</> : null}
      </div>
      {s && !s.connected && (
        <div style={{ color: t.amber, fontSize: 10, marginTop: 8, lineHeight: 1.6 }}>
          Kite tokens reset ~6 AM IST daily. Reconnect from Connect &amp; Keys to refresh your data.
        </div>
      )}
      <div style={{ color: t.dim, fontSize: 10, marginTop: 12, lineHeight: 1.7 }}>
        Indian markets are a standalone manual console — no Sterling/Grok strategy auto-trades Kite.
        Multi-user ready; credentials encrypted at rest.
      </div>
    </RightSection>
  );
}

export function KiteTab() {
  const [section, setSection] = useState<Section>('connect');
  const h = HEADERS[section];
  return (
    <ThreeColumnLayout
      leftNav={NAV}
      activeNav={section}
      onNavClick={(id) => setSection(id as Section)}
      centerHeader={<>
        <div>
          <div style={{ fontSize: 17, fontWeight: 800, letterSpacing: '0.04em', color: t.bright }}>{h.title}</div>
          <div style={{ fontSize: 10, color: t.dim, marginTop: 1 }}>{h.sub}</div>
        </div>
      </>}
      centerContent={
        <div>
          {section === 'connect' && <ConnectPane />}
          {section === 'watch' && <MarketWatchPane />}
          {section === 'portfolio' && <PortfolioPane />}
          {section === 'orders' && <OrdersPane />}
          {section === 'gtt' && <GttPane />}
          {section === 'funds' && <FundsPane />}
          {section === 'mf' && <MutualFundsPane />}
        </div>
      }
      rightSidebar={<StatusSidebar />}
    />
  );
}

export default KiteTab;
