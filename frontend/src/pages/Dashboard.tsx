import React, { useState } from 'react';
import { useStore } from '../store/useStore';
import { useConfigInfo } from '../hooks/useConfigInfo';
import { InstrumentSelector } from '../components/InstrumentSelector';
import { SnapshotPanel } from '../components/SnapshotPanel';
import { MarketSnapshot } from '../components/MarketSnapshot';
import { PreviewCandidates } from '../components/PreviewCandidates';
import { RunOnceResult } from '../components/RunOnceResult';
import { PositionsPanel } from '../components/PositionsPanel';
import { WatchlistPanel } from '../components/WatchlistPanel';
import { StreamBadge } from '../components/StreamBadge';
import { RiskConfigPanel } from '../components/RiskConfigPanel';
import { EvalHistoryPanel } from '../components/EvalHistoryPanel';
import { BacktestPanel } from '../components/BacktestPanel';
import { PortfolioSummary } from '../components/PortfolioSummary';
import { ArrowAlert } from '../components/ArrowAlert';
import { ArrowHistoryPanel } from '../components/ArrowHistoryPanel';
import { SystemInfoPanel } from '../components/SystemInfoPanel';
import { AnalyticsPanel } from '../components/AnalyticsPanel';
import { ExchangeManager } from '../components/ExchangeManager';
import { AccountPanel } from '../components/AccountPanel';
import { ExchangeBadge } from '../components/ExchangeBadge';
import { AlertManager } from '../components/AlertManager';
import { AlertBadge } from '../components/AlertBadge';
import { PositionSizingCalc } from '../components/PositionSizingCalc';
import { GreeksPanel } from '../components/GreeksPanel';
import { OptionChainViewer } from '../components/OptionChainViewer';
import { VolatilityScanPanel } from '../components/VolatilityScanPanel';
import { WebhookManager } from '../components/WebhookManager';
import { SessionExport } from '../components/SessionExport';
import { SessionStatsPanel } from '../components/SessionStatsPanel';

type Tab = 'analysis' | 'chain' | 'account' | 'alerts' | 'backtest' | 'positions' | 'watchlist' | 'config';

const page: React.CSSProperties = { maxWidth: 1200, margin: '0 auto', padding: '0 20px 40px' };

const header: React.CSSProperties = {
  borderBottom: '1px solid #1e1e1e', padding: '14px 0', marginBottom: 20,
  display: 'flex', alignItems: 'center', justifyContent: 'space-between',
  flexWrap: 'wrap', gap: 10,
};

const TAB_BAR: React.CSSProperties = {
  display: 'flex', gap: 4, marginBottom: 20,
  borderBottom: '1px solid #1e1e1e', paddingBottom: 0,
};

function Tab({ label, active, onClick }: { label: string; active: boolean; onClick: () => void }) {
  return (
    <button onClick={onClick} style={{
      background: 'none', border: 'none', cursor: 'pointer',
      fontFamily: 'inherit', fontSize: 12, letterSpacing: 1,
      color: active ? '#e0e0e0' : '#555',
      padding: '8px 14px',
      borderBottom: active ? '2px solid #44cc88' : '2px solid transparent',
      marginBottom: -1,
    }}>
      {label}
    </button>
  );
}

const TABS: [Tab, string][] = [
  ['analysis', 'ANALYSIS'],
  ['chain', 'OPTION CHAIN'],
  ['account', 'ACCOUNT'],
  ['alerts', 'ALERTS'],
  ['backtest', 'BACKTEST'],
  ['positions', 'POSITIONS'],
  ['watchlist', 'WATCHLIST'],
  ['config', 'CONFIG'],
];

export function Dashboard() {
  const { selectedUnderlying } = useStore();
  const [activeTab, setActiveTab] = useState<Tab>('analysis');
  const { data: sysInfo } = useConfigInfo();

  return (
    <div style={page}>
      <ArrowAlert underlying={selectedUnderlying} />

      <div style={header}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 14, flexWrap: 'wrap' }}>
          <div>
            <span style={{ fontSize: 20, fontWeight: 700, letterSpacing: 2, color: '#e0e0e0' }}>STERLING</span>
            <span style={{ fontSize: 11, color: '#444', marginLeft: 12, letterSpacing: 1 }}>
              v{sysInfo?.version ?? '0.4'} · {sysInfo?.paper_trading !== false ? 'PAPER' : 'LIVE'} · {(sysInfo?.active_data_source ?? 'deribit').toUpperCase()}
            </span>
          </div>
          <StreamBadge underlying={selectedUnderlying} />
          <ExchangeBadge />
          <AlertBadge />
        </div>
        <InstrumentSelector />
      </div>

      <div style={TAB_BAR}>
        {TABS.map(([tab, label]) => (
          <Tab key={tab} label={label} active={activeTab === tab} onClick={() => setActiveTab(tab)} />
        ))}
      </div>

      {activeTab === 'analysis' && (
        <>
          <SessionStatsPanel />
          <SnapshotPanel underlying={selectedUnderlying} />
          <MarketSnapshot underlying={selectedUnderlying} />
          <ArrowHistoryPanel underlying={selectedUnderlying} />
          <PreviewCandidates underlying={selectedUnderlying} />
          <RunOnceResult underlying={selectedUnderlying} />
          <EvalHistoryPanel underlying={selectedUnderlying} />
        </>
      )}
      {activeTab === 'chain' && (
        <>
          <OptionChainViewer underlying={selectedUnderlying} />
          <VolatilityScanPanel underlying={selectedUnderlying} />
        </>
      )}
      {activeTab === 'account' && (
        <>
          <AccountPanel underlying={selectedUnderlying} />
          <ExchangeManager />
        </>
      )}
      {activeTab === 'alerts' && <AlertManager />}
      {activeTab === 'backtest' && <BacktestPanel underlying={selectedUnderlying} />}
      {activeTab === 'positions' && (
        <>
          <PortfolioSummary />
          <GreeksPanel />
          <AnalyticsPanel />
          <PositionsPanel underlying={selectedUnderlying} />
        </>
      )}
      {activeTab === 'watchlist' && <WatchlistPanel />}
      {activeTab === 'config' && (
        <>
          <SystemInfoPanel />
          <PositionSizingCalc />
          <RiskConfigPanel />
          <WebhookManager />
          <SessionExport />
        </>
      )}
    </div>
  );
}
