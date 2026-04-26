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
import { PanelBoundary } from '../components/PanelBoundary';

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

function TabBtn({ label, active, onClick }: { label: string; active: boolean; onClick: () => void }) {
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
      <PanelBoundary title="ARROW ALERT">
        <ArrowAlert underlying={selectedUnderlying} />
      </PanelBoundary>

      <div style={header}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 14, flexWrap: 'wrap' }}>
          <div>
            <span style={{ fontSize: 20, fontWeight: 700, letterSpacing: 2, color: '#e0e0e0' }}>STERLING</span>
            <span style={{ fontSize: 11, color: '#444', marginLeft: 12, letterSpacing: 1 }}>
              v{sysInfo?.version ?? '0.4'} · {sysInfo?.paper_trading !== false ? 'PAPER' : 'LIVE'} · {(sysInfo?.active_data_source ?? 'deribit').toUpperCase()}
            </span>
          </div>
          <PanelBoundary><StreamBadge underlying={selectedUnderlying} /></PanelBoundary>
          <PanelBoundary><ExchangeBadge /></PanelBoundary>
          <PanelBoundary><AlertBadge /></PanelBoundary>
        </div>
        <InstrumentSelector />
      </div>

      <div style={TAB_BAR}>
        {TABS.map(([tab, label]) => (
          <TabBtn key={tab} label={label} active={activeTab === tab} onClick={() => setActiveTab(tab)} />
        ))}
      </div>

      {activeTab === 'analysis' && (
        <>
          <PanelBoundary title="SESSION"><SessionStatsPanel /></PanelBoundary>
          <PanelBoundary title="SNAPSHOT"><SnapshotPanel underlying={selectedUnderlying} /></PanelBoundary>
          <PanelBoundary title="MARKET"><MarketSnapshot underlying={selectedUnderlying} /></PanelBoundary>
          <PanelBoundary title="ARROWS"><ArrowHistoryPanel underlying={selectedUnderlying} /></PanelBoundary>
          <PanelBoundary title="PREVIEW"><PreviewCandidates underlying={selectedUnderlying} /></PanelBoundary>
          <PanelBoundary title="RUN-ONCE"><RunOnceResult underlying={selectedUnderlying} /></PanelBoundary>
          <PanelBoundary title="EVAL HISTORY"><EvalHistoryPanel underlying={selectedUnderlying} /></PanelBoundary>
        </>
      )}
      {activeTab === 'chain' && (
        <>
          <PanelBoundary title="OPTION CHAIN"><OptionChainViewer underlying={selectedUnderlying} /></PanelBoundary>
          <PanelBoundary title="VOL SCAN"><VolatilityScanPanel underlying={selectedUnderlying} /></PanelBoundary>
        </>
      )}
      {activeTab === 'account' && (
        <>
          <PanelBoundary title="ACCOUNT"><AccountPanel underlying={selectedUnderlying} /></PanelBoundary>
          <PanelBoundary title="EXCHANGES"><ExchangeManager /></PanelBoundary>
        </>
      )}
      {activeTab === 'alerts' && (
        <PanelBoundary title="ALERTS"><AlertManager /></PanelBoundary>
      )}
      {activeTab === 'backtest' && (
        <PanelBoundary title="BACKTEST"><BacktestPanel underlying={selectedUnderlying} /></PanelBoundary>
      )}
      {activeTab === 'positions' && (
        <>
          <PanelBoundary title="PORTFOLIO"><PortfolioSummary /></PanelBoundary>
          <PanelBoundary title="GREEKS"><GreeksPanel /></PanelBoundary>
          <PanelBoundary title="ANALYTICS"><AnalyticsPanel /></PanelBoundary>
          <PanelBoundary title="POSITIONS"><PositionsPanel underlying={selectedUnderlying} /></PanelBoundary>
        </>
      )}
      {activeTab === 'watchlist' && (
        <PanelBoundary title="WATCHLIST"><WatchlistPanel /></PanelBoundary>
      )}
      {activeTab === 'config' && (
        <>
          <PanelBoundary title="SYSTEM"><SystemInfoPanel /></PanelBoundary>
          <PanelBoundary title="SIZING"><PositionSizingCalc /></PanelBoundary>
          <PanelBoundary title="RISK CONFIG"><RiskConfigPanel /></PanelBoundary>
          <PanelBoundary title="WEBHOOKS"><WebhookManager /></PanelBoundary>
          <SessionExport />
        </>
      )}
    </div>
  );
}
