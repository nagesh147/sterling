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
  const [showSettings, setShowSettings] = useState(false);
  const [showLive, setShowLive] = useState(false);
  const [activeSection, setActiveSection] = useState<'signals' | 'positions' | 'calibration'>('signals');

  return (
    <div className="term-root">
      <DrawdownBreakerBadge />

      {/* ── Floating header pill ─────────────────────────────────────── */}
      <div style={{
        flexShrink: 0,
        padding: '10px 16px 0',
        background: 'var(--t-bg)',
      }}>
        <div style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          height: 46,
          background: 'rgba(13, 17, 26, 0.92)',
          border: '1px solid rgba(255,255,255,0.07)',
          borderRadius: 14,
          padding: '0 20px',
          backdropFilter: 'blur(20px)',
          boxShadow: '0 4px 24px rgba(0,0,0,0.45), inset 0 1px 0 rgba(255,255,255,0.05)',
        }}>
          {/* Wordmark */}
          <span style={{
            fontSize: 17,
            fontWeight: 800,
            letterSpacing: '0.18em',
            color: 'rgba(220, 232, 245, 0.92)',
            fontFamily: 'inherit',
            userSelect: 'none',
          }}>
            STERLING
          </span>

          {/* Right icons — bell · avatar · gear */}
          <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
            {/* Notification bell */}
            <button
              onClick={() => setShowLive(true)}
              title="Live alerts & controls"
              style={{
                background: 'none', border: 'none', cursor: 'pointer',
                width: 34, height: 34, borderRadius: 9,
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                color: 'rgba(150,170,200,0.7)', fontSize: 15,
                transition: 'background 0.15s, color 0.15s',
              }}
              onMouseEnter={e => { (e.currentTarget as HTMLElement).style.background = 'rgba(255,255,255,0.07)'; (e.currentTarget as HTMLElement).style.color = 'rgba(220,232,245,0.9)'; }}
              onMouseLeave={e => { (e.currentTarget as HTMLElement).style.background = 'none'; (e.currentTarget as HTMLElement).style.color = 'rgba(150,170,200,0.7)'; }}
            >
              🔔
            </button>

            {/* Profile avatar placeholder */}
            <div
              title="User profile"
              style={{
                width: 30, height: 30, borderRadius: '50%',
                background: 'linear-gradient(135deg, #2563EB 0%, #1E40AF 100%)',
                border: '2px solid rgba(255,255,255,0.12)',
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                fontSize: 11, fontWeight: 800, color: '#fff',
                letterSpacing: '0.02em', cursor: 'pointer',
                flexShrink: 0,
              }}
            >
              S
            </div>

            {/* Settings gear */}
            <button
              onClick={() => setShowSettings(true)}
              title="Settings"
              style={{
                background: 'none', border: 'none', cursor: 'pointer',
                width: 34, height: 34, borderRadius: 9,
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                color: 'rgba(150,170,200,0.7)', fontSize: 15,
                transition: 'background 0.15s, color 0.15s',
              }}
              onMouseEnter={e => { (e.currentTarget as HTMLElement).style.background = 'rgba(255,255,255,0.07)'; (e.currentTarget as HTMLElement).style.color = 'rgba(220,232,245,0.9)'; }}
              onMouseLeave={e => { (e.currentTarget as HTMLElement).style.background = 'none'; (e.currentTarget as HTMLElement).style.color = 'rgba(150,170,200,0.7)'; }}
            >
              ⚙
            </button>
          </div>
        </div>
      </div>

      {/* ── Ticker strip ─────────────────────────────────────────────── */}
      <TickerStrip />

      {/* ── Section tabs + functional controls ───────────────────────── */}
      <div style={{
        display: 'flex',
        alignItems: 'center',
        background: 'var(--t-bg2)',
        borderBottom: '1px solid var(--t-border)',
        flexShrink: 0,
        paddingLeft: 12,
        paddingRight: 10,
        gap: 0,
      }}>
        {/* Section tabs */}
        {([
          ['signals',     'SIGNALS'],
          ['positions',   'POSITIONS'],
          ['calibration', 'CALIBRATION'],
        ] as ['signals' | 'positions' | 'calibration', string][]).map(([id, label]) => (
          <button
            key={id}
            onClick={() => setActiveSection(id)}
            style={{
              background: 'none',
              border: 'none',
              borderBottom: `2px solid ${activeSection === id ? 'var(--t-blue)' : 'transparent'}`,
              color: activeSection === id ? 'var(--t-bright)' : 'var(--t-dim)',
              padding: '8px 16px',
              cursor: 'pointer',
              fontFamily: 'inherit',
              fontSize: 11,
              fontWeight: activeSection === id ? 700 : 400,
              letterSpacing: '0.08em',
              marginBottom: -1,
              transition: 'color 0.1s',
            }}
          >
            {label}
          </button>
        ))}

        {/* Right: compact functional controls */}
        <div style={{ marginLeft: 'auto', display: 'flex', alignItems: 'center', gap: 5, paddingRight: 2 }}>
          <PaperLiveToggle />
          <AlgoToggle chipStyle={chip} />
          <DataSourceSelector chipStyle={chip} />
          <CbChip />
          <button
            onClick={toggleTheme}
            title={`Switch to ${theme === 'dark' ? 'light' : 'dark'} mode`}
            style={chip}
          >
            {theme === 'dark' ? '☀' : '◑'}
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
