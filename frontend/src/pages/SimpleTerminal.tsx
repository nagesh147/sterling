/**
 * Simple (Basic) Mode — Bloomberg-style chrome around the focused signal + positions view.
 * Keeps SignalsTable and PositionsStrip as the main content; adds TickerStrip,
 * StatusBar, a compact header bar, and applies the terminal dark design system.
 */
import React, { useState } from 'react';
import { TickerStrip } from '../components/TickerStrip';
import { StatusBar } from '../components/StatusBar';
import { SignalsTable } from '../components/SignalsTable';
import { PositionsStrip } from '../components/PositionsStrip';
import { DrawdownBreakerBadge } from '../components/DrawdownBreakerBadge';
import { InstrumentSelector } from '../components/InstrumentSelector';
import { PaperLiveToggle } from '../components/PaperLiveToggle';
import { TradingModeSelector } from '../components/TradingModeSelector';
import { CalibrationPanel } from '../components/CalibrationPanel';
import { SimpleSettingsDrawer } from '../components/SimpleSettings';
import { useSetAppMode } from '../store/useStore';
import { useSelectedUnderlying } from '../store/useStore';
import { useSnapshot } from '../hooks/useSnapshot';
import { useDrawdownBreaker } from '../hooks/useDrawdownBreaker';
import '../styles/terminal.css';

const REGIME_COLOR: Record<string, string> = {
  BULL_TREND: '#00c87a',
  BEAR_TREND: '#f03050',
  VOLATILE:   '#f0a020',
  RANGING:    '#4a5a6a',
  IDLE:       '#4a5a6a',
};

function RegimeChip({ underlying }: { underlying: string }) {
  const { data: snap } = useSnapshot(underlying);
  if (!snap) return null;

  const regime = snap.macro_regime ?? 'RANGING';
  const color = REGIME_COLOR[regime] ?? '#4a5a6a';
  const totalScore = Math.max(snap.score_long, snap.score_short);
  const scoreColor = totalScore >= 85 ? '#00c87a' : totalScore >= 75 ? '#f0a020' : '#4a5a6a';
  const adx = snap.adx ?? 0;
  const atrPct = snap.atr_percentile ?? 50;

  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '0 12px', borderLeft: '1px solid var(--t-border)' }}>
      <span style={{
        fontSize: 10, fontWeight: 700, padding: '1px 7px', borderRadius: 3,
        background: color + '22', color, border: `1px solid ${color}44`,
        fontFamily: 'JetBrains Mono, monospace', letterSpacing: '0.06em',
      }}>
        {regime.replace('_', ' ')}
      </span>
      <span style={{ fontSize: 10, color: 'var(--t-dim)' }}>
        ADX <span style={{ color: adx >= 25 ? '#00c87a' : 'var(--t-text)', fontFamily: 'JetBrains Mono,monospace' }}>{Math.round(adx)}</span>
      </span>
      <span style={{ fontSize: 10, color: 'var(--t-dim)' }}>
        ATR <span style={{ color: atrPct > 65 ? '#f0a020' : 'var(--t-text)', fontFamily: 'JetBrains Mono,monospace' }}>{Math.round(atrPct)}%</span>
      </span>
      <span style={{ fontSize: 10, color: 'var(--t-dim)' }}>
        Score <span style={{ color: scoreColor, fontFamily: 'JetBrains Mono,monospace', fontWeight: 700 }}>{totalScore}</span>
      </span>
    </div>
  );
}

function CbChip() {
  const { data: cb } = useDrawdownBreaker();
  if (!cb || cb.state === 'clear') return null;

  const color = cb.state === 'warning' ? '#f0a020' : '#f03050';
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
  const underlying = useSelectedUnderlying();
  const [showSettings, setShowSettings] = useState(false);
  const [activeSection, setActiveSection] = useState<'signals' | 'positions' | 'calibration'>('signals');

  return (
    <div className="term-root" style={{ fontFamily: 'inherit' }}>
      <DrawdownBreakerBadge />

      {/* Ticker strip */}
      <TickerStrip />

      {/* Header bar */}
      <div style={{
        height: 40,
        background: 'var(--t-bg2)',
        borderBottom: '1px solid var(--t-border)',
        display: 'flex',
        alignItems: 'center',
        gap: 0,
        flexShrink: 0,
        paddingLeft: 12,
        paddingRight: 12,
      }}>
        {/* Brand */}
        <span style={{
          color: 'var(--t-bright)', fontWeight: 700, fontSize: 13, letterSpacing: 2,
          fontFamily: 'JetBrains Mono, monospace', marginRight: 12,
        }}>
          STERLING
        </span>

        {/* Instrument + mode + paper/live */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <InstrumentSelector />
          <TradingModeSelector />
          <PaperLiveToggle />
        </div>

        {/* Right side */}
        <div style={{ marginLeft: 'auto', display: 'flex', alignItems: 'center', gap: 8 }}>
          <CbChip />
          <button
            onClick={() => setShowSettings(true)}
            style={{
              background: 'none', border: '1px solid var(--t-border)', borderRadius: 3,
              color: 'var(--t-dim)', cursor: 'pointer', padding: '3px 8px',
              fontFamily: 'inherit', fontSize: 11, lineHeight: 1,
            }}
            title="Settings"
          >
            ⚙
          </button>
          <button
            onClick={() => setAppMode('pro')}
            style={{
              background: 'none',
              border: '1px solid var(--t-border)',
              borderRadius: 3, color: 'var(--t-dim)', cursor: 'pointer',
              padding: '3px 10px', fontFamily: 'inherit', fontSize: 10, letterSpacing: 1,
            }}
            title="Switch to Bloomberg Terminal layout"
          >
            TERMINAL
          </button>
        </div>
      </div>

      {/* Regime context bar */}
      <div style={{
        background: 'var(--t-bg3)',
        borderBottom: '1px solid var(--t-border)',
        display: 'flex', alignItems: 'center',
        padding: '0 12px',
        height: 32,
        flexShrink: 0,
        gap: 0,
        overflowX: 'auto',
      }}>
        <RegimeChip underlying={underlying} />
      </div>

      {/* Section tabs */}
      <div style={{
        display: 'flex', gap: 0,
        background: 'var(--t-bg2)',
        borderBottom: '1px solid var(--t-border)',
        flexShrink: 0,
        paddingLeft: 12,
      }}>
        {([
          ['signals',     'SIGNALS'],
          ['positions',   'POSITIONS'],
          ['calibration', 'CALIBRATION'],
        ] as [typeof activeSection, string][]).map(([id, label]) => (
          <button
            key={id}
            onClick={() => setActiveSection(id)}
            style={{
              background: 'none',
              border: 'none',
              borderBottom: `2px solid ${activeSection === id ? 'var(--t-blue)' : 'transparent'}`,
              color: activeSection === id ? 'var(--t-bright)' : 'var(--t-dim)',
              padding: '7px 16px',
              cursor: 'pointer',
              fontFamily: 'inherit',
              fontSize: 11,
              letterSpacing: 1,
              marginBottom: -1,
            }}
          >
            {label}
          </button>
        ))}
      </div>

      {/* Main content — scrollable */}
      <div style={{
        flex: 1,
        overflow: 'auto',
        padding: '12px 12px',
        background: 'var(--t-bg)',
      }}>
        {activeSection === 'signals' && (
          <div style={{ maxWidth: 1200, margin: '0 auto' }}>
            {/* Override card background for signals table to use terminal vars */}
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

      {/* Settings drawer */}
      <SimpleSettingsDrawer open={showSettings} onClose={() => setShowSettings(false)} />
    </div>
  );
}
