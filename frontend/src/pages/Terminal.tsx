import React, { useState, useEffect } from 'react';
import { Panel, PanelGroup, PanelResizeHandle } from 'react-resizable-panels';
import { TickerStrip } from '../components/TickerStrip';
import { SignalPane } from '../components/SignalPane';
import { ChartPane } from '../components/ChartPane';
import { RiskPane } from '../components/RiskPane';
import { BottomPanel } from '../components/BottomPanel';
import { StatusBar } from '../components/StatusBar';
import { InstrumentSelector } from '../components/InstrumentSelector';
import { PaperLiveToggle } from '../components/PaperLiveToggle';
import { DataSourceSelector } from '../components/DataSourceSelector';
import { DrawdownBreakerBadge } from '../components/DrawdownBreakerBadge';
import { V4AnalyticsDashboard } from '../components/V4AnalyticsDashboard';
import { GrokSettingsPane } from '../components/GrokSettingsPane';
import { GrokSignalPane } from '../components/GrokSignalPane';
import { GrokLogsPane } from '../components/GrokLogsPane';
import { useSelectedUnderlying, useAppMode, useSetAppMode, useTheme, useToggleTheme, useEngineMode, useSetEngineMode } from '../store/useStore';

import '../styles/terminal.css';

type NavTab = 'TERMINAL' | 'POSITIONS' | 'ANALYTICS' | 'CFG';

const NAV_TABS: NavTab[] = ['TERMINAL', 'POSITIONS', 'ANALYTICS', 'CFG'];

const PANEL_STORAGE_KEY = 'sterling-panel-sizes';

function loadPanelSizes(): number[] {
  try {
    const raw = localStorage.getItem(PANEL_STORAGE_KEY);
    if (raw) {
      const parsed = JSON.parse(raw);
      if (Array.isArray(parsed) && parsed.length === 3) return parsed;
    }
  } catch { /* ignore */ }
  return [22, 55, 23];
}

export function Terminal() {
  const underlying = useSelectedUnderlying();
  const [navTab, setNavTab] = useState<NavTab>('TERMINAL');
  const [bottomCollapsed, setBottomCollapsed] = useState(false);
  const appMode = useAppMode();
  const setAppMode = useSetAppMode();
  const theme = useTheme();
  const toggleTheme = useToggleTheme();
  const engineMode = useEngineMode();
  const setEngineMode = useSetEngineMode();

  /* Keep panel sizes in localStorage */
  const handlePanelResize = (sizes: number[]) => {
    try { localStorage.setItem(PANEL_STORAGE_KEY, JSON.stringify(sizes)); } catch { /* ignore */ }
  };

  /* keyboard shortcut T to toggle terminal */
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      const tag = (e.target as HTMLElement)?.tagName;
      if (tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT') return;
      if (e.key === 'Escape') setNavTab('TERMINAL');
      if (e.key === 'b' || e.key === 'B') setBottomCollapsed((p) => !p);
    };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, []);

  return (
    <div className="term-root">
      {/* Drawdown breaker alert overlaid at top */}
      <DrawdownBreakerBadge />

      {/* Ticker strip */}
      <TickerStrip />

      {/* NavBar */}
      <div style={{
        height: 36,
        background: 'var(--t-bg2)',
        borderBottom: '1px solid var(--t-border)',
        display: 'flex',
        alignItems: 'center',
        gap: 0,
        flexShrink: 0,
        paddingLeft: 12,
      }}>
        {/* Brand & Engine Toggle */}
        <div style={{ display: 'flex', alignItems: 'center', marginRight: 16, background: 'var(--t-bg)', borderRadius: 4, overflow: 'hidden', border: '1px solid var(--t-border)' }}>
          <button
            onClick={() => setEngineMode('sterling')}
            style={{
              padding: '4px 12px',
              border: 'none',
              background: engineMode === 'sterling' ? 'var(--t-blue)' : 'transparent',
              color: engineMode === 'sterling' ? '#fff' : 'var(--t-dim)',
              fontSize: 10,
              fontWeight: 700,
              letterSpacing: 1,
              cursor: 'pointer',
            }}
          >
            STERLING ENGINE
          </button>
          <button
            onClick={() => setEngineMode('grok')}
            style={{
              padding: '4px 12px',
              border: 'none',
              background: engineMode === 'grok' ? 'var(--t-green)' : 'transparent',
              color: engineMode === 'grok' ? '#fff' : 'var(--t-dim)',
              fontSize: 10,
              fontWeight: 700,
              letterSpacing: 1,
              cursor: 'pointer',
              borderLeft: '1px solid var(--t-border)',
            }}
          >
            GROK ENGINE
          </button>
        </div>

        {/* Nav tabs */}
        {NAV_TABS.map((tab) => (
          <button
            key={tab}
            onClick={() => setNavTab(tab)}
            style={{
              background: navTab === tab ? 'var(--t-bg3)' : 'none',
              color: navTab === tab ? 'var(--t-bright)' : 'var(--t-dim)',
              border: 'none',
              borderBottom: `2px solid ${navTab === tab ? 'var(--t-blue)' : 'transparent'}`,
              padding: '0 14px',
              height: '100%',
              cursor: 'pointer',
              fontFamily: 'inherit',
              fontSize: 11,
              letterSpacing: 1,
            }}
          >
            {tab}
          </button>
        ))}

        {/* Right side */}
        <div style={{ marginLeft: 'auto', display: 'flex', alignItems: 'center', gap: 8, paddingRight: 12 }}>
          <DataSourceSelector />
          <InstrumentSelector compact />
          <PaperLiveToggle />
          <button
            onClick={toggleTheme}
            title={theme === 'dark' ? 'Switch to Grey' : theme === 'grey' ? 'Switch to Light' : 'Switch to Dark'}
            style={{
              background: 'none', border: '1px solid var(--t-border)', borderRadius: 3,
              color: 'var(--t-dim)', cursor: 'pointer', padding: '2px 7px',
              fontFamily: 'inherit', fontSize: 12, lineHeight: 1,
            }}
          >
            {theme === 'dark' ? '◑' : theme === 'grey' ? '☀' : '◐'}
          </button>
          <button
            onClick={() => setAppMode(appMode === 'pro' ? 'basic' : 'pro')}
            title="Switch to simple mode"
            style={{
              background: 'none', border: '1px solid var(--t-border)',
              color: 'var(--t-dim)', cursor: 'pointer', padding: '2px 8px',
              fontFamily: 'inherit', fontSize: 10, borderRadius: 3,
            }}
          >
            SIMPLE
          </button>
        </div>
      </div>


      {/* Main workspace */}
      <div style={{ flex: 1, minHeight: 0, display: 'flex', flexDirection: 'column' }}>
        <div style={{ padding: '6px 12px', background: 'var(--t-bg2)', borderBottom: '1px solid var(--t-border)' }}>
          <V4AnalyticsDashboard activeSymbol={underlying} />
        </div>
        {/* Three-pane area */}
        <div style={{ flex: bottomCollapsed ? 1 : '1 1 auto', minHeight: 0 }}>
          <PanelGroup
            direction="horizontal"
            autoSaveId={PANEL_STORAGE_KEY}
            onLayout={handlePanelResize}
            style={{ height: '100%' }}
          >
            {/* Left: Signal pane or Grok Settings */}
            <Panel defaultSize={22} minSize={15} style={{ overflow: 'hidden' }}>
              <div style={{ height: '100%', borderRight: '1px solid var(--t-border)', background: 'var(--t-bg)' }}>
                {engineMode === 'sterling' ? <SignalPane underlying={underlying} /> : <GrokSettingsPane />}
              </div>
            </Panel>

            <PanelResizeHandle className="t-resize-handle" />

            {/* Center: Chart pane or Grok Signals */}
            <Panel defaultSize={55} minSize={30} style={{ overflow: 'hidden' }}>
              <div style={{ height: '100%', background: 'var(--t-bg)' }}>
                {engineMode === 'sterling' ? <ChartPane underlying={underlying} /> : <GrokSignalPane />}
              </div>
            </Panel>

            <PanelResizeHandle className="t-resize-handle" />

            {/* Right: Risk pane or Grok Logs */}
            <Panel defaultSize={23} minSize={15} style={{ overflow: 'hidden' }}>
              <div style={{ height: '100%', borderLeft: '1px solid var(--t-border)', background: 'var(--t-bg)' }}>
                {engineMode === 'sterling' ? <RiskPane /> : <GrokLogsPane />}
              </div>
            </Panel>
          </PanelGroup>
        </div>

        {/* Bottom panel (collapsible) */}
        {!bottomCollapsed && (
          <>
            <div
              className="t-resize-handle-h"
              onClick={() => setBottomCollapsed(true)}
              title="Click or press B to collapse bottom panel"
            />
            <div style={{ height: 220, flexShrink: 0, borderTop: '1px solid var(--t-border)', background: 'var(--t-bg)' }}>
              <BottomPanel />
            </div>
          </>
        )}

        {/* Bottom expand button when collapsed */}
        {bottomCollapsed && (
          <button
            onClick={() => setBottomCollapsed(false)}
            style={{
              height: 18, background: 'var(--t-bg2)', border: 'none',
              borderTop: '1px solid var(--t-border)', color: 'var(--t-dim)',
              cursor: 'pointer', fontFamily: 'inherit', fontSize: 9, letterSpacing: 1,
              flexShrink: 0,
            }}
          >
            ▲ SCANNER / CHAIN / WATCHLIST / ANALYTICS / CONFIG
          </button>
        )}
      </div>

      {/* Status bar */}
      <StatusBar />
    </div>
  );
}
