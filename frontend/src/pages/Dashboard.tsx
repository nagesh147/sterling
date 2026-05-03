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
import { TradingModeSelector } from '../components/TradingModeSelector';
import { MultiPaneChart } from '../components/charts/MultiPaneChart';
import { PositionHeatmap } from '../components/PositionHeatmap';
import { EquityCurve } from '../components/EquityCurve';
import { useTradingMode } from '../hooks/useTradingMode';
import { usePositions } from '../hooks/usePositions';

type Tab = 'analysis' | 'charts' | 'chain' | 'account' | 'alerts' | 'backtest' | 'positions' | 'watchlist' | 'config';

const page: React.CSSProperties = { maxWidth: 1200, margin: '0 auto', padding: '0 20px 40px' };

const header: React.CSSProperties = {
  borderBottom: '1px solid #1e1e1e', padding: '14px 0', marginBottom: 20,
  display: 'flex', alignItems: 'center', justifyContent: 'space-between',
  flexWrap: 'wrap', gap: 10,
};

const TAB_BAR: React.CSSProperties = {
  display: 'flex', gap: 4, marginBottom: 20,
  borderBottom: '1px solid #1e1e1e', paddingBottom: 0,
  flexWrap: 'wrap',
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
  ['charts',    'CHARTS',       '2'],
  ['chain',     'OPTION CHAIN', '3'],
  ['account',   'ACCOUNT',      '4'],
  ['alerts',    'ALERTS',       '5'],
  ['backtest',  'BACKTEST',     '6'],
  ['positions', 'POSITIONS',    '7'],
  ['watchlist', 'WATCHLIST',    '8'],
  ['config',    'CONFIG',       '9'],
];

const TAB_KEYS: Record<string, Tab> = {
  '1': 'analysis', '2': 'charts', '3': 'chain', '4': 'account',
  '5': 'alerts', '6': 'backtest', '7': 'positions', '8': 'watchlist', '9': 'config',
};

export function Dashboard() {
  const selectedUnderlying = useSelectedUnderlying();
  const [activeTab, setActiveTab] = useState<Tab>('analysis');
  const { data: sysInfo } = useConfigInfo();
  const { data: modeData } = useTradingMode();
  const { data: posData } = usePositions();

  const defaultTf = modeData?.config?.execution_tf ?? '15m';

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
          <PanelBoundary><TradingModeSelector /></PanelBoundary>
        </div>
        <InstrumentSelector />
      </div>

      <div style={TAB_BAR}>
        {TABS.map(([tab, label, key]) => (
          <TabBtn
            key={tab}
            label={label}
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
      {activeTab === 'charts' && (
        <PanelBoundary title="CHARTS">
          <MultiPaneChart underlying={selectedUnderlying} tf={defaultTf} />
        </PanelBoundary>
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
          <PanelBoundary title="EQUITY CURVE">
            <EquityCurve />
          </PanelBoundary>
          <PanelBoundary title="PORTFOLIO">
            <PositionHeatmap
              positions={posData?.positions ?? []}
            />
            <PortfolioSummary />
          </PanelBoundary>
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
          <PanelBoundary title="TRADING MODE">
            <TradingModeCard />
          </PanelBoundary>
          <PanelBoundary title="CIRCUIT BREAKER">
            <CircuitBreakerCard />
          </PanelBoundary>
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

function TradingModeCard() {
  const { data: modeData } = useTradingMode();
  const cfg = modeData?.config;
  return (
    <div>
      <div style={{ marginBottom: 12 }}><TradingModeSelector /></div>
      {cfg && (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3,1fr)', gap: 8, fontSize: 11, color: '#888' }}>
          {[
            ['Macro TF', cfg.macro_tf], ['Signal TF', cfg.signal_tf], ['Exec TF', cfg.execution_tf],
            ['DTE range', `${cfg.dte_min}–${cfg.dte_max}d`], ['Position %', `${(cfg.position_pct * 100).toFixed(1)}%`],
            ['Max positions', String(cfg.max_concurrent)], ['Stop mult', `${cfg.stop_atr_mult}×ATR`],
            ['Trail mode', cfg.trail_mode], ['Poll', `${cfg.poll_interval_s}s`],
          ].map(([k, v]) => (
            <div key={k as string}>
              <div style={{ color: '#444', fontSize: 10 }}>{k}</div>
              <div style={{ color: '#ccc' }}>{v}</div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function CircuitBreakerCard() {
  const [data, setData] = React.useState<{ state: string; halted: boolean; size_multiplier: number } | null>(null);
  const { api: _api } = { api: null as any };

  React.useEffect(() => {
    fetch('/api/v1/config/circuit-breaker')
      .then((r) => r.json())
      .then(setData)
      .catch(() => {});
  }, []);

  const reset = () => {
    fetch('/api/v1/config/circuit-breaker/reset', { method: 'POST' })
      .then((r) => r.json())
      .then(setData)
      .catch(() => {});
  };

  if (!data) return <div style={{ color: '#444', fontSize: 11 }}>Loading…</div>;

  const stateColor = data.halted ? '#cc4444' : '#44cc88';
  return (
    <div style={{ fontSize: 11 }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 8 }}>
        <span style={{
          background: `${stateColor}22`, color: stateColor,
          border: `1px solid ${stateColor}55`,
          borderRadius: 3, padding: '2px 10px', fontWeight: 700, letterSpacing: 1,
        }}>
          {data.state.toUpperCase()}
        </span>
        <span style={{ color: '#666' }}>Size: {(data.size_multiplier * 100).toFixed(0)}%</span>
        {data.halted && (
          <button
            onClick={reset}
            style={{
              background: '#1a1a2a', color: '#4499cc', border: '1px solid #4499cc',
              borderRadius: 3, padding: '3px 12px', cursor: 'pointer',
              fontFamily: 'inherit', fontSize: 11,
            }}
          >
            Reset
          </button>
        )}
      </div>
    </div>
  );
}
