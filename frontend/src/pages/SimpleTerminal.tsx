import React, { useState, useEffect, useRef } from 'react';
import { TickerStrip } from '../components/TickerStrip';
import { StatusBar } from '../components/StatusBar';
import { PositionsStrip } from '../components/PositionsStrip';
import { DrawdownBreakerBadge } from '../components/DrawdownBreakerBadge';
import { PaperLiveToggle } from '../components/PaperLiveToggle';
import { SimpleSettingsDrawer, AlgoToggle, AIGatekeeperToggle } from '../components/SimpleSettings';
import { DataSourceSelector } from '../components/DataSourceSelector';
import LiveControlPanel from '../components/LiveControlPanel';
import { useSetAppMode, useTheme, useToggleTheme, useSelectedUnderlying, useTabOrder, useSetTabOrder } from '../store/useStore';
import type { TabId } from '../store/useStore';
import { useScalpMode } from '../hooks/useSignalAlerts';
import { useDrawdownBreaker } from '../hooks/useDrawdownBreaker';
import { setCryptoEnabled } from '../hooks/useAppStream';
import { V4AnalyticsDashboard } from '../components/V4AnalyticsDashboard';
import { OHLCVChart } from '../components/OHLCVChart';
import { BacktestPanel } from '../components/BacktestPanel';

import { SterlingEngineTab } from '../components/sterling_engine/SterlingEngineTab';
import { MassiveBacktestDashboard } from '../components/MassiveBacktestDashboard';
import { GrokTab } from '../components/GrokTab';
import { SterlingV2Tab } from '../components/SterlingV2Tab';
import { PaperResearchTab } from '../components/paper/PaperResearchTab';
import { KiteTab } from '../components/kite/KiteTab';
import { useSterlingV2, useSetSterlingV2 } from '../store/useStore';
import { useKiteStatus } from '../hooks/useKite';
import type { NavItem } from '../components/kite/KiteLayout';
import { ThreeColumnLayout, RightSection } from '../components/ThreeColumnLayout';
import { SterlingLogo } from '../components/SterlingLogo';
import { card, cardBody, cardHead } from '../styles/terminalUI';
import '../styles/terminal.css';

function CbChip() {
  const { data: scalpData } = useScalpMode();
  if (!scalpData?.enabled) return null;
  const { data: cb } = useDrawdownBreaker();
  if (!cb || cb.state === 'clear') return null;
  const color = cb.state === 'warning' ? 'var(--t-amber)' : 'var(--t-red)';
  const ddPct = (Math.abs(cb.current_drawdown) * 100).toFixed(1);
  return (
    <div style={{
      padding: '2px 10px', borderRadius: 3,
      background: color + '18', border: `1px solid ${color}44`,
      fontSize: 10, color, fontWeight: 700,
      animation: cb.state !== 'warning' ? 't-blink 0.8s infinite' : undefined,
      fontFamily: 'JetBrains Mono, monospace',
    }}>
      CB {cb.state.toUpperCase()} {ddPct}%
    </div>
  );
}

function BacktestView() {
  const [showChart, setShowChart] = useState(true);
  const [symbol, setSymbol]       = useState('BTC');

  const headerBtn = (active: boolean): React.CSSProperties => ({
    padding: '3px 9px', borderRadius: 5, fontSize: 9, fontWeight: 600,
    cursor: 'pointer', fontFamily: 'inherit',
    border: active ? '1px solid var(--t-blue)44' : '1px solid var(--t-border)',
    background: active ? 'var(--t-bg3)' : 'transparent',
    color: active ? 'var(--t-blue)' : 'var(--t-dim)',
    transition: 'all 0.1s',
  });

  return (
    <div style={{ flex: 1, overflow: 'visible', display: 'flex', flexDirection: 'column', gap: 10, padding: 0 }}>
      <div style={{ ...card, flexShrink: 0 }}>
        <div style={{ ...cardHead, borderBottom: showChart ? '1px solid var(--t-border)' : 'none', gap: 10 }}>
          <span>HISTORICAL CANDLES</span>
          <span style={{ fontSize: 9, fontWeight: 400, letterSpacing: 0, color: 'var(--t-dim)' }}>Delta Exchange · 6m · 5m–4h</span>
          <div style={{ marginLeft: 'auto', display: 'flex', alignItems: 'center', gap: 6 }}>
            <div style={{ display: 'flex', gap: 3 }}>
              {['BTC', 'ETH', 'SOL', 'XRP'].map(s => (
                <button key={s} onClick={() => setSymbol(s)} style={headerBtn(symbol === s)}>{s}</button>
              ))}
            </div>
            <button
              onClick={() => setShowChart(v => !v)}
              title={showChart ? 'Hide chart' : 'Show chart'}
              style={{ ...headerBtn(showChart), color: showChart ? 'var(--t-green)' : 'var(--t-dim)', borderColor: showChart ? 'var(--t-green)44' : undefined }}
            >
              {showChart ? '◉ CHART ON' : '○ CHART OFF'}
            </button>
          </div>
        </div>
        {showChart && <OHLCVChart />}
      </div>
      <div style={card}>
        <div style={cardHead}>
          <span>MASSIVE VECTORIZED BACKTEST</span>
          <span style={{ fontSize: 9, fontWeight: 400, letterSpacing: 0, color: 'var(--t-dim)' }}>
            High-speed multi-year historical vector backtesting
          </span>
        </div>
        <div style={cardBody}>
          <MassiveBacktestDashboard underlying={symbol} />
        </div>
      </div>
      <div style={card}>
        <div style={cardHead}>
          <span>SIGNAL BACKTEST + SIMULATION</span>
          <span style={{ fontSize: 9, fontWeight: 400, letterSpacing: 0, color: 'var(--t-dim)' }}>
            Sterling regime · signal quality · capital simulation with fees, SL/TP, trail, Kelly
          </span>
        </div>
        <div style={cardBody}>
          <BacktestPanel underlying={symbol} />
        </div>
      </div>
    </div>
  );
}

const chip: React.CSSProperties = {
  display: 'inline-flex',
  alignItems: 'center',
  gap: 5,
  background: 'var(--t-bg3)',
  border: '1px solid var(--t-border)',
  borderRadius: 5,
  color: 'var(--t-dim)',
  cursor: 'pointer',
  padding: '4px 10px',
  fontFamily: 'inherit',
  fontSize: 10,
  fontWeight: 600,
  letterSpacing: '0.08em',
  lineHeight: 1,
  whiteSpace: 'nowrap' as const,
  transition: 'color 0.1s, border-color 0.1s',
};

const TOP_TAB = (active: boolean): React.CSSProperties => ({
  backgroundColor: 'transparent',
  backgroundImage: active ? 'var(--brand-grad)' : 'none',
  backgroundRepeat: 'no-repeat',
  backgroundSize: '100% 2.5px',
  backgroundPosition: '50% 100%',
  border: 'none',
  borderRadius: 3,
  color: active ? 'var(--t-bright)' : 'var(--t-dim)',
  padding: '9px 20px',
  cursor: 'pointer',
  fontFamily: 'inherit',
  fontSize: 12,
  fontWeight: active ? 700 : 400,
  letterSpacing: '0.10em',
  marginBottom: -1,
  transition: 'color .15s ease',
});

type TopTab = 'kite' | 'crypto';

const CRYPTO_TAB_VISIBILITY_KEY = 'sterling_show_crypto_tab';
function readCryptoTabVisible(): boolean {
  if (typeof window === 'undefined') return false;
  try {
    return window.localStorage.getItem(CRYPTO_TAB_VISIBILITY_KEY) === 'true';
  } catch {
    return false;
  }
}

const CRYPTO_TABS: TabId[] = ['sterlingEngine', 'grok', 'sterling_v2', 'positions', 'backtest', 'paper'];
const CRYPTO_LABELS: Record<TabId, string> = {
  sterlingEngine: 'STERLING',
  grok: 'GROK',
  sterling_v2: 'STERLING V2',
  positions: 'POSITIONS',
  backtest: 'BACKTEST',
  paper: 'PAPER RESEARCH',
  kite: 'KITE',
};

export function SimpleTerminal() {
  const setAppMode = useSetAppMode();
  const theme = useTheme();
  const toggleTheme = useToggleTheme();
  const underlying = useSelectedUnderlying();
  const { data: scalpData } = useScalpMode();
  const scalpOn = scalpData?.enabled ?? false;
  const [showSettings, setShowSettings] = useState(false);
  const [showLive, setShowLive] = useState(false);
  const sterlingV2 = useSterlingV2();
  const setSterlingV2 = useSetSterlingV2();
  const [activeTopTab, setActiveTopTab] = useState<TopTab>('kite');
  const [activeSection, setActiveSection] = useState<TabId>('sterlingEngine');
  const [kiteNav, setKiteNav] = useState<NavItem>('dashboard');
  const { data: kiteStatus } = useKiteStatus();

  const handleKiteNav = (nav: NavItem) => {
    setKiteNav(nav);
    window.dispatchEvent(new CustomEvent('kite-nav-click', { detail: nav }));
  };

  useEffect(() => {
    const onNav = (event: Event) => {
      const next = (event as CustomEvent<NavItem>).detail;
      if (typeof next === 'string') setKiteNav(next);
    };
    window.addEventListener('kite-nav-click', onNav);
    return () => window.removeEventListener('kite-nav-click', onNav);
  }, []);
  const [showCryptoTab, setShowCryptoTab] = useState(readCryptoTabVisible);

  useEffect(() => {
    const syncCryptoVisibility = () => setShowCryptoTab(readCryptoTabVisible());
    const onStorage = (e: StorageEvent) => {
      if (!e.key || e.key === CRYPTO_TAB_VISIBILITY_KEY) syncCryptoVisibility();
    };
    const interval = window.setInterval(syncCryptoVisibility, 250);
    window.addEventListener('storage', onStorage);
    window.addEventListener('focus', syncCryptoVisibility);
    return () => {
      window.clearInterval(interval);
      window.removeEventListener('storage', onStorage);
      window.removeEventListener('focus', syncCryptoVisibility);
    };
  }, []);

  useEffect(() => {
    if (!showCryptoTab && activeTopTab === 'crypto') {
      setActiveTopTab('kite');
    }
  }, [showCryptoTab, activeTopTab]);

  // Sync SSE connection to scalp_mode: when crypto is disabled, kill the live data stream
  useEffect(() => {
    setCryptoEnabled(scalpOn);
  }, [scalpOn]);

  return (
    <div className="term-root">
      {scalpOn && <DrawdownBreakerBadge />}

      {/* ── Header ─────────────────────────────────────────────── */}
      <div style={{
        flexShrink: 0,
        borderBottom: '1px solid var(--t-border)',
      }}>
        {/* Row 1: STERLING | KITE | CRYPTO | [kite nav when active] | [actions] */}
        <div style={{
          display: 'flex', alignItems: 'center', gap: 0,
          height: 44, padding: '0 20px',
        }}>
          <span style={{ display: 'inline-flex', alignItems: 'center', gap: 9, marginRight: 16, userSelect: 'none' }}>
            <SterlingLogo size={24} />
            <span style={{
              fontSize: 17, fontWeight: 800, letterSpacing: '0.18em',
              color: 'var(--t-bright)', fontFamily: 'inherit',
            }}>
              STERLING
            </span>
          </span>
          <button onClick={() => setActiveTopTab('kite')} style={{ ...TOP_TAB(activeTopTab === 'kite'), marginRight: 4 }}>
            KITE
          </button>
          {showCryptoTab && (
            <button onClick={() => setActiveTopTab('crypto')} style={{ ...TOP_TAB(activeTopTab === 'crypto'), opacity: 1, color: activeTopTab === 'crypto' ? 'var(--t-bright)' : 'var(--t-dim)', marginRight: 4 }}>
              CRYPTO
            </button>
          )}

          <div style={{ flex: 1 }} />
          <div style={{ display: 'flex', alignItems: 'center', gap: 6, height: '100%' }}>
            {/* Kite nav items — pushed to the right when KITE tab is active */}
            {activeTopTab === 'kite' && (
              <>
                {([
                  { id: 'dashboard' as const, label: 'Dashboard' },
                  { id: 'orders' as const, label: 'Orders' },
                  { id: 'holdings' as const, label: 'Holdings' },
                  { id: 'positions' as const, label: 'Positions' },
                  { id: 'more' as const, label: 'More' },
                  { id: 'data' as const, label: 'Data' },
                  { id: 'adaptiveEdge' as const, label: 'Adaptive Edge' },
                  { id: 'connect' as const, label: 'Connect' },
                  { id: 'help' as const, label: 'Help' },
                ]).map((item) => (
                  <button
                    key={item.id}
                    onClick={() => handleKiteNav(item.id)}
                    style={{
                      background: 'none', border: 'none', cursor: 'pointer',
                      fontFamily: 'inherit', fontSize: 13, fontWeight: kiteNav === item.id ? 500 : 400,
                      color: kiteNav === item.id ? '#f06428' : '#444',
                      padding: '0 9px', height: '100%',
                      transition: 'color .15s ease',
                    }}
                  >
                    {item.label}
                  </button>
                ))}
                <span style={{ width: 1, height: 18, background: 'var(--t-border)', margin: '0 8px' }} />
              </>
            )}
            {/* Bell — always visible in kite mode; conditional in crypto */}
            {(activeTopTab === 'kite' || scalpOn) && (
              <button onClick={() => scalpOn ? setShowLive(true) : undefined} title="Notifications" style={{
                background: 'none', border: '1px solid var(--t-border)', cursor: 'pointer',
                width: 32, height: 32, borderRadius: 8,
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                color: 'var(--t-dim)', fontSize: 13, transition: 'border-color .12s, color .12s',
              }}
                onMouseEnter={e => { (e.currentTarget as HTMLElement).style.borderColor = 'var(--t-bright)44'; (e.currentTarget as HTMLElement).style.color = 'var(--t-bright)'; }}
                onMouseLeave={e => { (e.currentTarget as HTMLElement).style.borderColor = 'var(--t-border)'; (e.currentTarget as HTMLElement).style.color = 'var(--t-dim)'; }}
              >🔔</button>
            )}
            {/* Kite user avatar + name — shown when kite is active */}
            {activeTopTab === 'kite' && (
              <div style={{ display: 'flex', alignItems: 'center', gap: 6, cursor: 'pointer' }}>
                <div style={{ position: 'relative' }}>
                  <div style={{
                    width: 28, height: 28, borderRadius: 14,
                    background: 'rgba(240,100,40,0.15)',
                    color: '#f06428', display: 'flex', alignItems: 'center', justifyContent: 'center',
                    fontSize: 11, fontWeight: 700,
                  }}>
                    {kiteStatus?.user_name ? kiteStatus.user_name.substring(0, 2).toUpperCase() : 'MA'}
                  </div>
                  {kiteStatus?.connected && (
                    <span style={{
                      position: 'absolute', bottom: -1, right: -1,
                      width: 8, height: 8, borderRadius: '50%',
                      background: kiteStatus.is_paper ? '#ff9800' : '#4caf50',
                      border: '2px solid var(--t-bg2)',
                    }} />
                  )}
                </div>
                <span style={{ fontSize: 11, color: 'var(--t-dim)' }}>
                  {kiteStatus?.user_name ? kiteStatus.user_name.split(' ')[0] : 'Madaram'}
                </span>
              </div>
            )}
            {/* More options (three dots) — replaces old settings gear */}
            <button onClick={() => setShowSettings(true)} title="More options" style={{
              background: 'none', border: '1px solid var(--t-border)', cursor: 'pointer',
              width: 32, height: 32, borderRadius: 8,
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              color: 'var(--t-dim)', fontSize: 16, lineHeight: 1, transition: 'border-color .12s, color .12s',
            }}
              onMouseEnter={e => { (e.currentTarget as HTMLElement).style.borderColor = 'var(--t-bright)44'; (e.currentTarget as HTMLElement).style.color = 'var(--t-bright)'; }}
              onMouseLeave={e => { (e.currentTarget as HTMLElement).style.borderColor = 'var(--t-border)'; (e.currentTarget as HTMLElement).style.color = 'var(--t-dim)'; }}
            >⋮</button>
          </div>
        </div>

        {/* Row 2: crypto sub-tabs + controls — only when crypto is selected */}
        {showCryptoTab && activeTopTab === 'crypto' && (
          <div style={{ display: 'flex', alignItems: 'center', padding: '0 20px', borderTop: '1px solid var(--t-border)', overflow: 'hidden' }}>
            {CRYPTO_TABS.map((id) => (
              <button
                key={id}
                onClick={() => setActiveSection(id)}
                style={{
                  backgroundColor: 'transparent',
                  backgroundImage: activeSection === id ? 'var(--brand-grad)' : 'none',
                  backgroundRepeat: 'no-repeat',
                  backgroundSize: '100% 2.5px',
                  backgroundPosition: '50% 100%',
                  border: 'none', borderRadius: 3,
                  color: activeSection === id ? 'var(--t-bright)' : 'var(--t-dim)',
                  padding: '9px 12px', cursor: 'pointer',
                  fontFamily: 'inherit', fontSize: 10, fontWeight: activeSection === id ? 700 : 400,
                  letterSpacing: '0.06em', marginBottom: -1, transition: 'color .15s ease',
                }}
              >
                {CRYPTO_LABELS[id]}
              </button>
            ))}
            <div style={{ flex: 1 }} />
            <div style={{ display: 'flex', alignItems: 'center', gap: 5 }}>
              <PaperLiveToggle />
              <AlgoToggle chipStyle={chip} />
              <AIGatekeeperToggle chipStyle={chip} />
              <DataSourceSelector chipStyle={chip} />
              <CbChip />
              <button onClick={toggleTheme} title="Toggle theme" style={chip}>
                {theme === 'dark' ? '◑' : theme === 'grey' ? '☀' : '◐'}
              </button>
              <button onClick={() => setAppMode('pro')} title="Sterling Pro" style={{ ...chip, color: 'var(--t-blue)', borderColor: 'var(--t-blue)44' }}>
                Pro
              </button>
            </div>
          </div>
        )}
      </div>

      {/* ── Content ──────────────────────────────────────────────── */}
      {activeTopTab === 'kite' && (
        <>
          {/* KiteTicker now renders inside KiteTab's center column so the right-side
              Sterling Kite Engine panel starts at the top bar's bottom (not below the ticker). */}
          <div style={{ flex: 1, minHeight: 0, overflow: 'hidden', display: 'flex', flexDirection: 'column' }}>
            <KiteTab />
          </div>
        </>
      )}

      {showCryptoTab && activeTopTab === 'crypto' && (
        <>
          <TickerStrip />
          <div style={{ flex: 1, minHeight: 0, overflow: 'hidden', background: 'transparent', display: 'flex', flexDirection: 'column' }}>
            {activeSection === 'sterlingEngine' && <SterlingEngineTab />}
            {activeSection === 'grok' && <GrokTab />}
            {activeSection === 'sterling_v2' && <SterlingV2Tab />}
            {activeSection === 'positions' && <PositionsStrip asPage />}
            {activeSection === 'backtest' && (
              <ThreeColumnLayout
                leftNav={[{ id: 'backtest', label: 'Backtest', color: 'var(--t-blue)' }]}
                activeNav="backtest"
                onNavClick={() => {}}
                centerHeader={<>
                  <div style={{ fontSize: 17, fontWeight: 800, letterSpacing: '0.06em', color: 'var(--t-bright)' }}>Backtest</div>
                  <div style={{ fontSize: 10, color: 'var(--t-dim)', marginTop: 1 }}>Historical candle data & signal simulation</div>
                </>}
                centerContent={<BacktestView />}
                rightSidebar={<>
                  <RightSection label="Analytics">
                    <V4AnalyticsDashboard activeSymbol={underlying} />
                  </RightSection>
                </>}
              />
            )}
            {activeSection === 'paper' && (
              <div style={{ flex: 1, minHeight: 0, overflow: 'auto', padding: 20 }}>
                <PaperResearchTab />
              </div>
            )}
          </div>
          <StatusBar />
        </>
      )}

      <SimpleSettingsDrawer open={showSettings} onClose={() => setShowSettings(false)} />

      {/* Live control drawer */}
      {showLive && (
        <div
          onClick={() => setShowLive(false)}
          style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.6)', zIndex: 3000, display: 'flex', justifyContent: 'flex-end' }}
        >
          <div onClick={(e) => e.stopPropagation()} style={{
            width: 380, height: '100%', background: 'var(--bg, #07090d)',
            borderLeft: '1px solid var(--t-border)', display: 'flex', flexDirection: 'column', overflow: 'auto',
          }}>
            <div style={{
              display: 'flex', justifyContent: 'space-between', alignItems: 'center',
              padding: '10px 14px', borderBottom: '1px solid var(--t-border)', background: 'var(--t-bg2)',
            }}>
              <span style={{ fontSize: 11, letterSpacing: 2, fontWeight: 700, color: 'var(--t-bright)' }}>LIVE CONTROL</span>
              <button onClick={() => setShowLive(false)} style={{ background: 'none', border: 'none', color: 'var(--t-dim)', cursor: 'pointer', fontSize: 16, lineHeight: 1, padding: 0 }}>×</button>
            </div>
            <div style={{ padding: 12 }}>
              <LiveControlPanel />
            </div>
          </div>
        </div>
      )}
    </div>
  );
}