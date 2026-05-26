import React, { useState } from 'react';
import { TickerStrip } from '../components/TickerStrip';
import { StatusBar } from '../components/StatusBar';
import { SignalsTable } from '../components/SignalsTable';
import { PositionsStrip } from '../components/PositionsStrip';
import { DrawdownBreakerBadge } from '../components/DrawdownBreakerBadge';
import { PaperLiveToggle } from '../components/PaperLiveToggle';
import { TradingModeSelector } from '../components/TradingModeSelector';
import { CalibrationPanel } from '../components/CalibrationPanel';
import { SimpleSettingsDrawer, AlgoToggle } from '../components/SimpleSettings';
import { DataSourceSelector } from '../components/DataSourceSelector';
import LiveControlPanel from '../components/LiveControlPanel';
import { useSetAppMode, useTheme, useToggleTheme, useSelectedUnderlying } from '../store/useStore';
import { useDrawdownBreaker } from '../hooks/useDrawdownBreaker';
import { V4AnalyticsDashboard } from '../components/V4AnalyticsDashboard';
import { OHLCVChart } from '../components/OHLCVChart';
import { BacktestPanel } from '../components/BacktestPanel';
import { StrategyTab } from '../components/strategy/StrategyTab';
import { ScalpingTab } from '../components/scalping/ScalpingTab';
import { ThreeColumnLayout, LeftSection, RightSection, StatCard } from '../components/ThreeColumnLayout';
import '../styles/terminal.css';

function CbChip() {
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

// ── Backtest tab — chart toggle + panels ──────────────────────────────────────

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

      {/* ── Chart panel ── */}
      <div style={{ background: 'var(--t-bg2)', border: '1px solid var(--t-border)', borderRadius: 10, overflow: 'hidden', flexShrink: 0 }}>
        {/* Chart header with toggle */}
        <div style={{ padding: '8px 14px', borderBottom: showChart ? '1px solid var(--t-border)' : 'none',
          display: 'flex', alignItems: 'center', gap: 10 }}>
          <span style={{ fontSize: 10, fontWeight: 700, letterSpacing: '0.12em', color: 'var(--t-bright)' }}>
            HISTORICAL CANDLES
          </span>
          <span style={{ fontSize: 9, color: 'var(--t-dim)' }}>Delta Exchange · 6m · 5m–4h</span>
          <div style={{ marginLeft: 'auto', display: 'flex', alignItems: 'center', gap: 6 }}>
            {/* Symbol selector */}
            <div style={{ display: 'flex', gap: 3 }}>
              {['BTC', 'ETH', 'SOL', 'XRP'].map(s => (
                <button key={s} onClick={() => setSymbol(s)} style={headerBtn(symbol === s)}>{s}</button>
              ))}
            </div>
            {/* Chart toggle */}
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

      {/* ── Signal backtest panel ── */}
      <div style={{ background: 'var(--t-bg2)', border: '1px solid var(--t-border)', borderRadius: 10, overflow: 'hidden' }}>
        <div style={{ padding: '8px 14px', borderBottom: '1px solid var(--t-border)',
          display: 'flex', alignItems: 'center', gap: 8 }}>
          <span style={{ fontSize: 10, fontWeight: 700, letterSpacing: '0.12em', color: 'var(--t-bright)' }}>
            SIGNAL BACKTEST + SIMULATION
          </span>
          <span style={{ fontSize: 9, color: 'var(--t-dim)' }}>
            Sterling regime · signal quality · capital simulation with fees, SL/TP, trail, Kelly
          </span>
        </div>
        <div style={{ padding: 14 }}>
          <BacktestPanel underlying={symbol} />
        </div>
      </div>
    </div>
  );
}

// Shared chip style for every header control button
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

export function SimpleTerminal() {
  const setAppMode = useSetAppMode();
  const theme = useTheme();
  const toggleTheme = useToggleTheme();
  const underlying = useSelectedUnderlying();
  const [showSettings, setShowSettings] = useState(false);
  const [showLive, setShowLive] = useState(false);
  const [activeSection, setActiveSection] = useState<'scalping' | 'strategy' | 'signals' | 'positions' | 'backtest' | 'calibration'>('scalping');

  return (
    <div className="term-root">
      <DrawdownBreakerBadge />

      {/* ── Header ─────────────────────────────────────────────────── */}
      <div style={{
        flexShrink: 0,
        background: 'var(--t-bg2)',
        borderBottom: '1px solid var(--t-border)',
      }}>
        {/* Top bar: wordmark left, icons right */}
        <div style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          height: 44,
          padding: '0 20px',
        }}>
          <span style={{
            fontSize: 17, fontWeight: 800, letterSpacing: '0.18em',
            color: 'var(--t-bright)', fontFamily: 'inherit', userSelect: 'none',
          }}>
            STERLING
          </span>
          <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
            <button onClick={() => setShowLive(true)} title="Live alerts & controls" style={{
              background: 'none', border: '1px solid var(--t-border)', cursor: 'pointer',
              width: 34, height: 34, borderRadius: 8,
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              color: 'var(--t-dim)', fontSize: 14, transition: 'border-color .12s, color .12s',
            }}
              onMouseEnter={e => { (e.currentTarget as HTMLElement).style.borderColor = 'var(--t-bright)44'; (e.currentTarget as HTMLElement).style.color = 'var(--t-bright)'; }}
              onMouseLeave={e => { (e.currentTarget as HTMLElement).style.borderColor = 'var(--t-border)'; (e.currentTarget as HTMLElement).style.color = 'var(--t-dim)'; }}
            >🔔</button>
            <div title="User profile" style={{
              width: 32, height: 32, borderRadius: '50%',
              background: 'linear-gradient(135deg, #2563EB 0%, #1E40AF 100%)',
              border: '2px solid rgba(255,255,255,0.12)',
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              fontSize: 11, fontWeight: 800, color: '#fff', letterSpacing: '0.02em', cursor: 'pointer',
            }}>S</div>
            <button onClick={() => setShowSettings(true)} title="Settings" style={{
              background: 'none', border: '1px solid var(--t-border)', cursor: 'pointer',
              width: 34, height: 34, borderRadius: 8,
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              color: 'var(--t-dim)', fontSize: 14, transition: 'border-color .12s, color .12s',
            }}
              onMouseEnter={e => { (e.currentTarget as HTMLElement).style.borderColor = 'var(--t-bright)44'; (e.currentTarget as HTMLElement).style.color = 'var(--t-bright)'; }}
              onMouseLeave={e => { (e.currentTarget as HTMLElement).style.borderColor = 'var(--t-border)'; (e.currentTarget as HTMLElement).style.color = 'var(--t-dim)'; }}
            >⚙</button>
          </div>
        </div>

        {/* Tab bar: tabs center, controls right */}
        <div style={{
          display: 'flex',
          alignItems: 'center',
          padding: '0 20px',
          borderTop: '1px solid var(--t-border)',
        }}>
          {([
            ['scalping',   'SCALPING'],
            ['strategy',    'RSI MEAN-REV'],
            ['signals',     'SIGNALS'],
            ['positions',   'POSITIONS'],
            ['backtest',    'BACKTEST'],
            ['calibration', 'CALIBRATION'],
          ] as ['scalping' | 'strategy' | 'signals' | 'positions' | 'backtest' | 'calibration', string][]).map(([id, label]) => (
            <button
              key={id}
              onClick={() => setActiveSection(id)}
              style={{
                background: 'none',
                border: 'none',
                borderBottom: `2px solid ${activeSection === id ? 'var(--t-blue)' : 'transparent'}`,
                color: activeSection === id ? 'var(--t-bright)' : 'var(--t-dim)',
                padding: '8px 14px',
                cursor: 'pointer',
                fontFamily: 'inherit',
                fontSize: 11,
                fontWeight: activeSection === id ? 700 : 400,
                letterSpacing: '0.08em',
                marginBottom: -1,
                transition: 'color .1s',
              }}
            >
              {label}
            </button>
          ))}
          <div style={{ flex: 1 }} />
          <div style={{ display: 'flex', alignItems: 'center', gap: 5 }}>
            <PaperLiveToggle />
            <AlgoToggle chipStyle={chip} />
            <DataSourceSelector chipStyle={chip} />
            <CbChip />
            <button
              onClick={toggleTheme}
              title={theme === 'dark' ? 'Switch to Grey' : theme === 'grey' ? 'Switch to Light' : 'Switch to Dark'}
              style={chip}
            >
              {theme === 'dark' ? '◑' : theme === 'grey' ? '☀' : '◐'}
            </button>
            <button
              onClick={() => setAppMode('pro')}
              title="Switch to 3-pane Terminal"
              style={{ ...chip, color: 'var(--t-blue)', borderColor: 'var(--t-blue)44' }}
            >
              TERMINAL
            </button>
          </div>
        </div>
      </div>

      {/* ── Ticker strip ─────────────────────────────────────────────── */}
      <TickerStrip />

      {/* Main content */}
      <div style={{ flex: 1, minHeight: 0, overflow: 'hidden', background: 'var(--t-bg)', display: 'flex', flexDirection: 'column' }}>
        {/* V4 Analytics shown on signals, backtest, and calibration tabs — in the right sidebar of those tabs */}
        {activeSection === 'scalping' && (
          <ScalpingTab />
        )}
        {activeSection === 'strategy' && (
          <StrategyTab />
        )}
        {activeSection === 'signals' && (
          <ThreeColumnLayout
            leftNav={[{ id: 'all', label: 'All Signals', color: 'var(--t-bright)'}]}
            activeNav="all"
            onNavClick={() => {}}
            centerHeader={<>
              <div style={{ fontSize: 17, fontWeight: 800, letterSpacing: '0.06em', color: 'var(--t-bright)' }}>Signals</div>
              <div style={{ fontSize: 10, color: 'var(--t-dim)', marginTop: 1 }}>Live signal feed</div>
            </>}
            centerContent={<div className="term-signals-wrap" style={{ flex: 1, minHeight: 0 }}><SignalsTable /></div>}
            centerFullBleed
            rightSidebar={<>
              <RightSection label="Analytics">
                <V4AnalyticsDashboard activeSymbol={underlying} />
              </RightSection>
            </>}
          />
        )}
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
        {activeSection === 'calibration' && (
          <ThreeColumnLayout
            leftNav={[{ id: 'calibration', label: 'Calibration', color: 'var(--t-amber)' }]}
            activeNav="calibration"
            onNavClick={() => {}}
            centerHeader={<>
              <div style={{ fontSize: 17, fontWeight: 800, letterSpacing: '0.06em', color: 'var(--t-bright)' }}>Calibration</div>
              <div style={{ fontSize: 10, color: 'var(--t-dim)', marginTop: 1 }}>Adaptive calibration metrics</div>
            </>}
            centerContent={<CalibrationPanel />}
            rightSidebar={<>
              <RightSection label="Analytics">
                <V4AnalyticsDashboard activeSymbol={underlying} />
              </RightSection>
            </>}
          />
        )}
      </div>

      <StatusBar />
      <SimpleSettingsDrawer open={showSettings} onClose={() => setShowSettings(false)} />

      {/* Live control drawer — slide-out from the right */}
      {showLive && (
        <div
          onClick={() => setShowLive(false)}
          style={{
            position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.6)',
            zIndex: 3000, display: 'flex', justifyContent: 'flex-end',
          }}
        >
          <div
            onClick={(e) => e.stopPropagation()}
            style={{
              width: 380, height: '100%', background: 'var(--bg, #07090d)',
              borderLeft: '1px solid var(--t-border)',
              display: 'flex', flexDirection: 'column', overflow: 'auto',
            }}
          >
            <div style={{
              display: 'flex', justifyContent: 'space-between', alignItems: 'center',
              padding: '10px 14px', borderBottom: '1px solid var(--t-border)',
              background: 'var(--t-bg2)',
            }}>
              <span style={{
                fontSize: 11, letterSpacing: 2, fontWeight: 700, color: 'var(--t-bright)',
              }}>
                LIVE CONTROL
              </span>
              <button
                onClick={() => setShowLive(false)}
                style={{
                  background: 'none', border: 'none', color: 'var(--t-dim)',
                  cursor: 'pointer', fontSize: 16, lineHeight: 1, padding: 0,
                }}
              >
                ×
              </button>
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
