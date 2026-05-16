import React, { useState, useEffect } from 'react';
import { Panel, PanelGroup, PanelResizeHandle } from 'react-resizable-panels';
import { TickerStrip } from '../components/TickerStrip';
import { AllSymbolsTicker } from '../components/AllSymbolsTicker';
import { SignalPane } from '../components/SignalPane';
import { ChartPane } from '../components/ChartPane';
import { RiskPane } from '../components/RiskPane';
import { BottomPanel } from '../components/BottomPanel';
import { StatusBar } from '../components/StatusBar';
import { InstrumentSelector } from '../components/InstrumentSelector';
import { PaperLiveToggle } from '../components/PaperLiveToggle';
import { DataSourceSelector } from '../components/DataSourceSelector';
import { DrawdownBreakerBadge } from '../components/DrawdownBreakerBadge';
import { useSelectedUnderlying, useAppMode, useSetAppMode, useTheme, useToggleTheme } from '../store/useStore';

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
        {/* Brand */}
        <span style={{
          color: 'var(--t-bright)', fontWeight: 700, letterSpacing: 2, fontSize: 13,
          marginRight: 16, fontFamily: 'JetBrains Mono, monospace',
        }}>
          STERLING ◆
        </span>

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
            title={`Switch to ${theme === 'dark' ? 'light' : 'dark'} mode`}
            style={{
              background: 'none', border: '1px solid var(--t-border)', borderRadius: 3,
              color: 'var(--t-dim)', cursor: 'pointer', padding: '2px 7px',
              fontFamily: 'inherit', fontSize: 12, lineHeight: 1,
            }}
          >
            {theme === 'dark' ? '☀' : '◑'}
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

      {/* All-symbols context ticker (regime, score, live prices) */}
      <AllSymbolsTicker />

      {/* Main workspace */}
      <div style={{ flex: 1, minHeight: 0, display: 'flex', flexDirection: 'column' }}>
        {/* Three-pane area */}
        <div style={{ flex: bottomCollapsed ? 1 : '1 1 auto', minHeight: 0 }}>
          <PanelGroup
            direction="horizontal"
            autoSaveId={PANEL_STORAGE_KEY}
            onLayout={handlePanelResize}
            style={{ height: '100%' }}
          >
            {/* Left: Signal pane */}
            <Panel defaultSize={22} minSize={15} style={{ overflow: 'hidden' }}>
              <div style={{ height: '100%', borderRight: '1px solid var(--t-border)', background: 'var(--t-bg)' }}>
                <SignalPane underlying={underlying} />
              </div>
            </Panel>

            <PanelResizeHandle className="t-resize-handle" />

            {/* Center: Chart pane */}
            <Panel defaultSize={55} minSize={30} style={{ overflow: 'hidden' }}>
              <div style={{ height: '100%', background: 'var(--t-bg)' }}>
                <ChartPane underlying={underlying} />
              </div>
            </Panel>

            <PanelResizeHandle className="t-resize-handle" />

            {/* Right: Risk pane */}
            <Panel defaultSize={23} minSize={15} style={{ overflow: 'hidden' }}>
              <div style={{ height: '100%', borderLeft: '1px solid var(--t-border)', background: 'var(--t-bg)' }}>
                <RiskPane />
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
