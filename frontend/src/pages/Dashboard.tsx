import React, { useState, useEffect } from 'react';
import { useSelectedUnderlying } from '../store/useStore';
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
import { ScoringWeightsPanel } from '../components/ScoringWeightsPanel';
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

function TabBtn({ label, shortcut, active, onClick }: {
  label: string; shortcut: string; active: boolean; onClick: () => void;
}) {
  return (
    <button onClick={onClick} title={`Press ${shortcut} to switch`} style={{
      background: 'none', border: 'none', cursor: 'pointer',
      fontFamily: 'inherit', fontSize: 12, letterSpacing: 1,
      color: active ? '#e0e0e0' : '#555',
      padding: '8px 14px',
      borderBottom: active ? '2px solid #44cc88' : '2px solid transparent',
      marginBottom: -1,
      display: 'flex', alignItems: 'center', gap: 5,
    }}>
      {label}
      <span style={{ fontSize: 9, color: active ? '#44cc8866' : '#333', fontWeight: 400 }}>{shortcut}</span>
    </button>
  );
}

const TABS: [Tab, string, string][] = [
  ['analysis',  'ANALYSIS',     '1'],
  ['chain',     'OPTION CHAIN', '2'],
  ['account',   'ACCOUNT',      '3'],
  ['alerts',    'ALERTS',       '4'],
  ['backtest',  'BACKTEST',     '5'],
  ['positions', 'POSITIONS',    '6'],
  ['watchlist', 'WATCHLIST',    '7'],
  ['config',    'CONFIG',       '8'],
];

const TAB_KEYS: Record<string, Tab> = {
  '1': 'analysis', '2': 'chain', '3': 'account', '4': 'alerts',
  '5': 'backtest', '6': 'positions', '7': 'watchlist', '8': 'config',
};

export function Dashboard() {
  const selectedUnderlying = useSelectedUnderlying();
  const [activeTab, setActiveTab] = useState<Tab>('analysis');
  const { data: sysInfo } = useConfigInfo();

  // Keyboard shortcuts: 1-8 switch tabs, skip if typing in an input
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      const tag = (e.target as HTMLElement)?.tagName;
      if (tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT') return;
      if (e.metaKey || e.ctrlKey || e.altKey) return;
      const tab = TAB_KEYS[e.key];
      if (tab) setActiveTab(tab);
    };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, []);

  return (
    <div style={page}>
      <PanelBoundary title="NEW SIGNAL ALERT">
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
        {TABS.map(([tab, label, key]) => (
          <TabBtn
            key={tab}
            label={`${label}`}
            shortcut={key}
            active={activeTab === tab}
            onClick={() => setActiveTab(tab)}
          />
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
          <PanelBoundary title="SIGNAL HISTORY"><EvalHistoryPanel underlying={selectedUnderlying} /></PanelBoundary>
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
          <PanelBoundary title="SCORING WEIGHTS"><ScoringWeightsPanel /></PanelBoundary>
          <PanelBoundary title="WEBHOOKS"><WebhookManager /></PanelBoundary>
          <SessionExport />
        </>
      )}
    </div>
  );
}
