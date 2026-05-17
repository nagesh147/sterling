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

export function SimpleTerminal() {
  const setAppMode = useSetAppMode();
  const theme = useTheme();
  const toggleTheme = useToggleTheme();
  const [showSettings, setShowSettings] = useState(false);
  const [showLive, setShowLive] = useState(false);
  const [activeSection, setActiveSection] = useState<'signals' | 'positions' | 'calibration'>('signals');

  return (
    <div className="term-root">
      <DrawdownBreakerBadge />

      {/* Ticker strip — live prices all symbols */}
      <TickerStrip />

      {/* Header bar */}
      <div style={{
        height: 40, background: 'var(--t-bg2)',
        borderBottom: '1px solid var(--t-border)',
        display: 'flex', alignItems: 'center',
        gap: 8, flexShrink: 0, paddingLeft: 12, paddingRight: 12,
      }}>
        <span style={{
          color: 'var(--t-bright)', fontWeight: 700, fontSize: 13, letterSpacing: 2,
          fontFamily: 'JetBrains Mono, monospace', flexShrink: 0,
        }}>
          STERLING
        </span>
        <TradingModeSelector />

        <div style={{ marginLeft: 'auto', display: 'flex', alignItems: 'center', gap: 8 }}>
          <PaperLiveToggle />
          <AlgoToggle />
          <DataSourceSelector />
          <CbChip />
          <button
            onClick={toggleTheme}
            title={`Switch to ${theme === 'dark' ? 'light' : 'dark'} mode`}
            style={{
              background: 'none', border: '1px solid var(--t-border)', borderRadius: 3,
              color: 'var(--t-dim)', cursor: 'pointer', padding: '3px 7px',
              fontFamily: 'inherit', fontSize: 12, lineHeight: 1,
            }}
          >
            {theme === 'dark' ? '☀' : '◑'}
          </button>
          <button
            onClick={() => setShowLive(true)}
            title="Live Control — kill switch · daily loss · retry queue"
            style={{
              background: 'none', border: '1px solid var(--t-border)', borderRadius: 3,
              color: 'var(--t-dim)', cursor: 'pointer', padding: '3px 8px',
              fontFamily: 'inherit', fontSize: 10, lineHeight: 1, letterSpacing: 1,
            }}
          >
            LIVE
          </button>
          <button
            onClick={() => setShowSettings(true)}
            title="Settings"
            style={{
              background: 'none', border: '1px solid var(--t-border)', borderRadius: 3,
              color: 'var(--t-dim)', cursor: 'pointer', padding: '3px 8px',
              fontFamily: 'inherit', fontSize: 11, lineHeight: 1,
            }}
          >
            ⚙
          </button>
          <button
            onClick={() => setAppMode('pro')}
            title="Switch to Bloomberg Terminal 3-pane layout"
            style={{
              background: 'none', border: '1px solid var(--t-border)', borderRadius: 3,
              color: 'var(--t-dim)', cursor: 'pointer', padding: '3px 10px',
              fontFamily: 'inherit', fontSize: 10, letterSpacing: 1,
            }}
          >
            TERMINAL
          </button>
        </div>
      </div>


      {/* Section tabs */}
      <div style={{
        display: 'flex', background: 'var(--t-bg2)',
        borderBottom: '1px solid var(--t-border)',
        flexShrink: 0, paddingLeft: 12,
      }}>
        {([
          ['signals',     'SIGNALS'],
          ['positions',   'POSITIONS'],
          ['calibration', 'CALIBRATION'],
        ] as ['signals' | 'positions' | 'calibration', string][]).map(([id, label]) => (
          <button
            key={id}
            onClick={() => setActiveSection(id)}
            style={{
              background: 'none', border: 'none',
              borderBottom: `2px solid ${activeSection === id ? 'var(--t-blue)' : 'transparent'}`,
              color: activeSection === id ? 'var(--t-bright)' : 'var(--t-dim)',
              padding: '7px 16px', cursor: 'pointer',
              fontFamily: 'inherit', fontSize: 11, letterSpacing: 1, marginBottom: -1,
            }}
          >
            {label}
          </button>
        ))}
      </div>

      {/* Main content */}
      <div style={{ flex: 1, overflow: 'auto', padding: '12px', background: 'var(--t-bg)' }}>
        {activeSection === 'signals' && (
          <div className="term-signals-wrap" style={{ maxWidth: 1200, margin: '0 auto' }}>
            <SignalsTable />
          </div>
        )}
        {activeSection === 'positions' && (
          <div style={{ maxWidth: 1200, margin: '0 auto' }}>
            <PositionsStrip />
          </div>
        )}
        {activeSection === 'calibration' && (
          <div style={{ maxWidth: 600, margin: '0 auto' }}>
            <CalibrationPanel />
          </div>
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
