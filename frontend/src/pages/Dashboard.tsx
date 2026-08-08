import React, { useState, useEffect, lazy, Suspense } from 'react';
import { Terminal } from './Terminal';
import { SimpleTerminal } from './SimpleTerminal';
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
import { MassiveBacktestDashboard } from '../components/MassiveBacktestDashboard';
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
import { TelegramConfigPanel } from '../components/TelegramConfigPanel';
import { useTradingMode } from '../hooks/useTradingMode';
import { usePositions } from '../hooks/usePositions';
import { useTheme, useToggleTheme, useAppMode, useSetAppMode } from '../store/useStore';
import { InstrumentDetailCard } from '../components/InstrumentDetailCard';
import { TradingTicket } from '../components/TradingTicket';
import { PositionsStrip } from '../components/PositionsStrip';
import { WalkForwardPanel } from '../components/WalkForwardPanel';
import { SensitivityPanel } from '../components/SensitivityPanel';
import { CorrelationHeatmap } from '../components/CorrelationHeatmap';

import { DrawdownBreakerBadge } from '../components/DrawdownBreakerBadge';
import { CalibrationPanel } from '../components/CalibrationPanel';
import { AlertsPanel } from '../components/AlertsPanel';
import { GoLivePanel } from '../components/GoLivePanel';
import { PaperLiveToggle } from '../components/PaperLiveToggle';
import { SimpleSettingsDrawer, SimpleStatusDots } from '../components/SimpleSettings';
import { V4AnalyticsDashboard } from '../components/V4AnalyticsDashboard';
import { useScalpMode } from '../hooks/useSignalAlerts';

type Tab = 'analysis' | 'charts' | 'chain' | 'account' | 'alerts' | 'backtest' | 'positions' | 'watchlist' | 'config';

const page: React.CSSProperties = { maxWidth: 1280, margin: '0 auto', padding: '0 24px 48px' };

const header: React.CSSProperties = {
  borderBottom: '1px solid var(--border)',
  padding: '12px 0',
  marginBottom: 24,
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'space-between',
  flexWrap: 'wrap',
  gap: 12,
};

const TAB_BAR: React.CSSProperties = {
  display: 'flex',
  gap: 2,
  marginBottom: 24,
  borderBottom: '1px solid var(--border)',
  paddingBottom: 0,
  flexWrap: 'wrap',
};

function TabBtn({ label, shortcut, active, onClick }: {
  label: string; shortcut: string; active: boolean; onClick: () => void;
}) {
  return (
    <button onClick={onClick} title={`Press ${shortcut} to switch`} style={{
      background: 'none',
      border: 'none',
      cursor: 'pointer',
      fontFamily: 'inherit',
      fontSize: 11,
      fontWeight: active ? 600 : 400,
      letterSpacing: '0.08em',
      color: active ? 'var(--text-primary)' : 'var(--text-dim)',
      padding: '10px 16px',
      borderBottom: active ? '2px solid var(--accent)' : '2px solid transparent',
      marginBottom: -1,
      display: 'flex',
      alignItems: 'center',
      gap: 6,
      transition: 'color 0.1s',
    }}>
      {label}
      <span style={{
        fontSize: 9,
        color: active ? 'var(--accent)' : 'var(--text-faint)',
        fontWeight: 400,
        background: active ? 'var(--accent)18' : 'transparent',
        borderRadius: 3,
        padding: active ? '1px 4px' : undefined,
        letterSpacing: 0,
      }}>{shortcut}</span>
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
  const { data: scalpData } = useScalpMode();
  const scalpOn = scalpData?.enabled ?? false;
  const { data: posData } = usePositions(scalpOn ? undefined : undefined);
  const theme = useTheme();
  const toggleTheme = useToggleTheme();
  const appMode = useAppMode();
  const setAppMode = useSetAppMode();
  /* These must be declared before any early returns to satisfy React hooks rules. */
  const [showSettings, setShowSettings] = useState(false);
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

  /* Route to dedicated Terminal views — use widened string to avoid TS narrowing
     appMode for the (now unreachable) legacy render paths below. */
  const _modeStr: string = appMode;
  if (_modeStr === 'basic') return <SimpleTerminal />;
  if (_modeStr === 'pro')   return <Terminal />;

  return (
    <div style={page}>
      <PanelBoundary><DrawdownBreakerBadge /></PanelBoundary>
      <PanelBoundary title="NEW SIGNAL ALERT">
        <ArrowAlert underlying={selectedUnderlying} />
      </PanelBoundary>
      <div style={{ marginBottom: 24 }}>
        <V4AnalyticsDashboard activeSymbol={selectedUnderlying} />
      </div>

      <div style={header}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 16, flexWrap: 'wrap' }}>
          {/* App wordmark */}
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <span style={{
              fontSize: 15,
              fontWeight: 800,
              letterSpacing: '0.12em',
              color: 'var(--text-primary)',
            }}>
              STERLING
            </span>
            <span style={{
              fontSize: 9,
              fontWeight: 600,
              letterSpacing: '0.1em',
              color: 'var(--accent)',
              background: 'var(--accent)14',
              border: '1px solid var(--accent)30',
              borderRadius: 4,
              padding: '2px 6px',
            }}>v3</span>
          </div>

          {/* Separator */}
          <div style={{ width: 1, height: 18, background: 'var(--border)' }} />

          {/* Pro mode: status badges */}
          {appMode === 'pro' && <>
            <PanelBoundary><StreamBadge underlying={selectedUnderlying} /></PanelBoundary>
            <PanelBoundary><ExchangeBadge /></PanelBoundary>
            <PanelBoundary><AlertBadge /></PanelBoundary>
          </>}
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
          {/* Pro mode: instrument selector */}
          {appMode === 'pro' && <InstrumentSelector />}

          {/* Paper / Live toggle — always visible */}
          <PaperLiveToggle />

          {/* Simple mode: status dots + settings gear */}
          {appMode === 'basic' && (
            <>
              <SimpleStatusDots />
              <button
                onClick={() => setShowSettings(true)}
                title="Settings"
                style={{
                  background: 'var(--bg-surface)',
                  border: '1px solid var(--border)',
                  borderRadius: 6,
                  color: 'var(--text-muted)',
                  cursor: 'pointer',
                  padding: '5px 9px',
                  fontFamily: 'inherit',
                  fontSize: 13,
                  lineHeight: 1,
                  transition: 'border-color 0.1s, color 0.1s',
                }}
              >
                ⚙
              </button>
            </>
          )}

          {/* Theme toggle — cycles dark → grey → light → dark */}
          <button
            onClick={toggleTheme}
            title={theme === 'dark' ? 'Switch to Grey' : theme === 'grey' ? 'Switch to Light' : 'Switch to Dark'}
            style={{
              background: 'var(--bg-surface)',
              border: '1px solid var(--border)',
              borderRadius: 6,
              color: 'var(--text-muted)',
              cursor: 'pointer',
              padding: '5px 9px',
              fontFamily: 'inherit',
              fontSize: 11,
              lineHeight: 1,
            }}
          >
            {theme === 'dark' ? '◑' : theme === 'grey' ? '☀' : '◐'}
          </button>

          {/* Simple / Advanced toggle */}
          <button
            onClick={() => setAppMode(appMode === 'basic' ? 'pro' : 'basic')}
            style={{
              background: appMode === 'pro' ? 'var(--accent)14' : 'var(--bg-surface)',
              border: `1px solid ${appMode === 'pro' ? 'var(--accent)40' : 'var(--border)'}`,
              borderRadius: 6,
              color: appMode === 'pro' ? 'var(--accent)' : 'var(--text-dim)',
              cursor: 'pointer',
              padding: '5px 12px',
              fontFamily: 'inherit',
              fontSize: 10,
              fontWeight: 600,
              letterSpacing: '0.08em',
            }}
          >
            {appMode === 'pro' ? 'ADVANCED' : 'SIMPLE'}
          </button>
        </div>
      </div>

      {appMode === 'basic' ? (
        // ── SIMPLE MODE ─────────────────────────────────────────────────────
        <>
          <SimpleSettingsDrawer open={showSettings} onClose={() => setShowSettings(false)} />
          <PanelBoundary title="MASSIVE VECTORIZED BACKTEST"><MassiveBacktestDashboard underlying={selectedUnderlying} /></PanelBoundary>
          <PanelBoundary title="POSITIONS"><PositionsStrip /></PanelBoundary>
        </>
      ) : (
        // ── PRO MODE ────────────────────────────────────────────────────────
        <>
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
              <PanelBoundary title="TRADING TICKET"><TradingTicket underlying={selectedUnderlying} /></PanelBoundary>
              <PanelBoundary title="TRADING ALERTS"><AlertsPanel /></PanelBoundary>
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
            <>
              <PanelBoundary title="MASSIVE VECTORIZED BACKTEST"><MassiveBacktestDashboard underlying={selectedUnderlying} /></PanelBoundary>
              <PanelBoundary title="BACKTEST"><BacktestPanel underlying={selectedUnderlying} /></PanelBoundary>
              <PanelBoundary title="WALK-FORWARD"><WalkForwardPanel /></PanelBoundary>
              <PanelBoundary title="SENSITIVITY"><SensitivityPanel /></PanelBoundary>
            </>
          )}
          {activeTab === 'positions' && (
            <>
              <PanelBoundary title="EQUITY CURVE"><EquityCurve /></PanelBoundary>
              <PanelBoundary title="PORTFOLIO">
                <PositionHeatmap positions={posData?.positions ?? []} />
                <PortfolioSummary />
              </PanelBoundary>
              <PanelBoundary title="GREEKS"><GreeksPanel /></PanelBoundary>
              <PanelBoundary title="CORRELATION"><CorrelationHeatmap /></PanelBoundary>

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
              <PanelBoundary title="LIVE TRADING"><GoLivePanel /></PanelBoundary>
              <PanelBoundary title="TRADING MODE"><TradingModeCard /></PanelBoundary>
              <PanelBoundary title="CIRCUIT BREAKER"><CircuitBreakerCard /></PanelBoundary>
              <PanelBoundary title="SIZING"><PositionSizingCalc /></PanelBoundary>
              <PanelBoundary title="RISK CONFIG"><RiskConfigPanel /></PanelBoundary>
              <PanelBoundary title="CALIBRATION"><CalibrationPanel /></PanelBoundary>
              <PanelBoundary title="SCORING WEIGHTS"><ScoringWeightsPanel /></PanelBoundary>
              <PanelBoundary title="TELEGRAM"><TelegramConfigPanel /></PanelBoundary>
              <PanelBoundary title="WEBHOOKS"><WebhookManager /></PanelBoundary>
              <SessionExport />
            </>
          )}
        </>
      )}
    </div>
  );
}

function TradingModeCard() {
  const { data: modeData } = useTradingMode();
  const cfg = modeData?.config;
  const [kiteCfg, setKiteCfg] = React.useState<any>(null);
  React.useEffect(() => {
    fetch('/api/v1/kite/engine/config').then(r => r.json()).then(setKiteCfg).catch(() => {});
  }, []);
  return (
    <div>
      <div style={{ marginBottom: 12 }}><TradingModeSelector /></div>
      {cfg && (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3,1fr)', gap: 8, fontSize: 11, color: 'var(--text-muted)' }}>
          {[
            ['Macro TF', cfg.macro_tf], ['Signal TF', cfg.signal_tf], ['Exec TF', cfg.execution_tf],
            ['DTE range', `${cfg.dte_min}–${cfg.dte_max}d`], ['Position %', `${(cfg.position_pct * 100).toFixed(1)}%`],
            ['Max positions', String(cfg.max_concurrent)], ['Stop mult', `${cfg.stop_atr_mult}×ATR`],
            ['Trail mode', cfg.trail_mode], ['Poll', `${cfg.poll_interval_s}s`],
            ['Hybrid ST weight', (cfg.hybrid_st_weight ?? 0.5).toFixed(1)],
            ['Exit mode (unified)', kiteCfg?.exit_mode || 'two_red'],
          ].map(([k, v]) => (
            <div key={k as string}>
              <div style={{ color: 'var(--text-faint)', fontSize: 10 }}>{k}</div>
              <div style={{ color: 'var(--text-primary)' }}>{v}</div>
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

  if (!data) return <div style={{ color: 'var(--text-faint)', fontSize: 11 }}>Loading…</div>;

  const stateColor = data.halted ? 'var(--danger)' : 'var(--accent)';
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
        <span style={{ color: 'var(--text-dim)' }}>Size: {(data.size_multiplier * 100).toFixed(0)}%</span>
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
