import React, { useEffect, useMemo, useState } from 'react';
import { useSimulation, useSimulationStore, useSimBarOpen, useSimActive, SimSignalEvent } from '../../hooks/useSimulation';
import { k } from '../../styles/kiteUI';
import './SimulationBar.css';

// Utility to tint colors
const tint = (color: string, opacity: number) => `color-mix(in srgb, ${color} ${opacity * 100}%, transparent)`;

// Tick intervals for 30 mins
const TICKS = ['09:15', '09:45', '10:15', '10:45', '11:15', '11:45', '12:15', '12:45', '13:15', '13:45', '14:15', '14:45', '15:15', '15:30'];

// Helper: parse HH:MM or ISO datetime string to minutes since midnight safely
function parseTimeToMinutes(timeStr?: string): number {
  if (!timeStr) return 0;
  const str = timeStr.includes('T') ? (timeStr.split('T')[1] || '') : timeStr;
  const parts = str.split(':').map(Number);
  if (parts.length >= 2 && !isNaN(parts[0]) && !isNaN(parts[1])) {
    return parts[0] * 60 + parts[1];
  }
  return 0;
}

// Helper: safely format time string to HH:MM or HH:MM:SS
function formatTime(isoStr?: string, len: number = 8): string {
  if (!isoStr) return '--:--:--';
  const str = isoStr.includes('T') ? (isoStr.split('T')[1] || isoStr) : isoStr;
  return str.substring(0, len);
}

// Helper: export replayed signals log to CSV
export function exportSignalsToCSV(events: SimSignalEvent[], date: string) {
  if (!events || events.length === 0) return;
  const headers = ['Time', 'Strategy', 'Instrument', 'Direction', 'Strength', 'Entry Price', 'Stop Loss', 'Target Price'];
  const rows = events.map(ev => [
    ev.time_iso,
    (ev.strategy || '').toUpperCase(),
    ev.instrument,
    ev.direction,
    ev.strength,
    ev.entry,
    ev.stop,
    ev.target,
  ]);
  const csvContent = [headers.join(','), ...rows.map(r => r.join(','))].join('\n');
  const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = `sterling_replay_signals_${date}.csv`;
  a.click();
  URL.revokeObjectURL(url);
}

export function SimulationBar() {
  const sim = useSimulation();
  const barOpen = useSimBarOpen();
  const simActive = useSimActive();
  const [showStreamDrawer, setShowStreamDrawer] = useState(false);
  const [toastSignal, setToastSignal] = useState<SimSignalEvent | null>(null);

  // Trigger toast on new signal
  useEffect(() => {
    if (sim.status.last_signal) {
      setToastSignal(sim.status.last_signal);
      const timer = setTimeout(() => setToastSignal(null), 3000);
      return () => clearTimeout(timer);
    }
  }, [sim.status.last_signal?.time_iso, sim.status.last_signal?.instrument, sim.status.last_signal?.strategy]);

  // Keyboard shortcuts
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (!barOpen) return;
      if (e.target instanceof HTMLInputElement || e.target instanceof HTMLTextAreaElement || e.target instanceof HTMLSelectElement) return;

      if (e.key === ' ') {
        e.preventDefault();
        if (sim.status.state === 'running') sim.pause();
        else if (sim.status.state === 'paused') sim.resume();
        else if (sim.status.state === 'idle') sim.start();
      } else if (e.key === 'ArrowLeft') {
        e.preventDefault();
        sim.stepBars(-5);
      } else if (e.key === 'ArrowRight') {
        e.preventDefault();
        sim.stepBars(5);
      } else if (e.key === 'Home') {
        e.preventDefault();
        sim.jumpStart();
      } else if (e.key === 'End') {
        e.preventDefault();
        sim.jumpEnd();
      } else if (e.key === 'Escape') {
        if (showStreamDrawer) setShowStreamDrawer(false);
        else sim.setBarOpen(false);
      } else if (e.key === '=' || e.key === '+') {
        const speeds = [1, 5, 10, 50, 100, 250, 500, 1000, 5000];
        const idx = speeds.indexOf(sim.speed);
        if (idx < speeds.length - 1) sim.setSpeed(speeds[idx + 1]);
      } else if (e.key === '-' || e.key === '_') {
        const speeds = [1, 5, 10, 50, 100, 250, 500, 1000, 5000];
        const idx = speeds.indexOf(sim.speed);
        if (idx > 0) sim.setSpeed(speeds[idx - 1]);
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [barOpen, sim, showStreamDrawer]);

  // Compute heatmap dots
  const heatmapDots = useMemo(() => {
    if (!sim.status.config) return [];
    
    const startMins = parseTimeToMinutes(sim.status.config.start_time || '09:15:00');
    const endMins = parseTimeToMinutes(sim.status.config.end_time || '15:30:00');
    const totalMins = Math.max(1, endMins - startMins);

    return sim.status.stats.events.map((ev, i) => {
      const evMins = parseTimeToMinutes(ev.time_iso);
      const pct = Math.max(0, Math.min(100, ((evMins - startMins) / totalMins) * 100));
      const color = ev.direction === 'BULLISH' || ev.direction === 'LONG' ? k.green : k.red;
      return (
        <div 
          key={i} 
          className="sim-heatmap-dot" 
          style={{ left: `${pct}%`, background: color, boxShadow: `0 0 4px ${color}` }}
          title={`${formatTime(ev.time_iso, 5)} - [${ev.strategy.toUpperCase()}] ${ev.instrument} ${ev.direction}`}
        />
      );
    });
  }, [sim.status.stats.events, sim.status.config]);

  if (!barOpen) return null;

  const isBullish = sim.status.last_signal?.direction === 'BULLISH' || sim.status.last_signal?.direction === 'LONG';

  const [showConfigModal, setShowConfigModal] = useState(false);

  const STRATEGY_LIST = [
    { key: 'all', label: '⚡ ALL STRATEGIES' },
    { key: 'supertrend', label: '🎯 SuperTrend' },
    { key: 'vcp', label: '📈 VCP Squeeze' },
    { key: 'adaptive_edge', label: '⚡ Adaptive Edge' },
    { key: 'bear_to_bearish', label: '📉 Bear to Bearish' },
    { key: 'atm_imbalance', label: '⚖️ ATM Imbalance' },
    { key: 'navigator', label: '🧭 Navigator' },
    { key: 'nifty_orb', label: '🔔 Nifty ORB' },
  ];

  return (
    <>
      {/* Toast popup when a signal triggers */}
      {toastSignal && sim.status.state === 'running' && (
        <div className="sim-toast-popup" data-direction={toastSignal.direction}>
          <span className="sim-toast-badge">[{toastSignal.strategy.toUpperCase()}]</span>
          <span className="sim-toast-title">
            {toastSignal.direction === 'BULLISH' ? '🟢 LONG' : '🔴 SHORT'} {toastSignal.instrument}
          </span>
          <span className="sim-toast-price">@ ₹{toastSignal.entry}</span>
          <span className="sim-toast-time">({toastSignal.time_iso})</span>
        </div>
      )}

      {/* Multi-Strategy & Strike Settings Drawer */}
      {showConfigModal && (
        <div className="sim-drawer-overlay" onClick={() => setShowConfigModal(false)}>
          <div className="sim-drawer-card" style={{ maxWidth: 520 }} onClick={e => e.stopPropagation()}>
            <div className="sim-drawer-header">
              <div className="sim-drawer-title">
                ⚙️ MARKET REPLAY CONFIGURATION
              </div>
              <button className="sim-drawer-close" onClick={() => setShowConfigModal(false)}>✕</button>
            </div>

            <div className="sim-drawer-body" style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
              {/* Strategies Multi-Select */}
              <div>
                <div style={{ fontSize: 11, fontWeight: 700, color: 'var(--k-cyan)', marginBottom: 8 }}>
                  ⚡ SELECT STRATEGIES TO REPLAY ({sim.selectedStrategies.includes('all') ? 'ALL' : sim.selectedStrategies.length})
                </div>
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
                  {STRATEGY_LIST.map(s => {
                    const isSelected = sim.selectedStrategies.includes(s.key) || (sim.selectedStrategies.includes('all') && s.key === 'all');
                    return (
                      <button
                        key={s.key}
                        className="sim-speed-pill"
                        data-active={isSelected}
                        style={{ height: 26, padding: '0 10px', fontSize: 10, borderRadius: 13 }}
                        onClick={() => sim.toggleStrategy(s.key)}
                        disabled={simActive}
                      >
                        {s.label}
                      </button>
                    );
                  })}
                </div>
              </div>

              {/* Moneyness / Strike Selection */}
              <div>
                <div style={{ fontSize: 11, fontWeight: 700, color: 'var(--k-cyan)', marginBottom: 8 }}>
                  🎯 MONEYNESS & STRIKE SELECTION
                </div>
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
                  {[
                    { key: 'ATM', label: '🎯 ATM (At-The-Money)' },
                    { key: 'ITM1', label: '🟢 ITM1 (+1 Strike In-the-Money)' },
                    { key: 'ITM2', label: '🟢 ITM2 (+2 Strikes In-the-Money)' },
                    { key: 'OTM1', label: '🔴 OTM1 (+1 Strike Out-of-Money)' },
                    { key: 'OTM2', label: '🔴 OTM2 (+2 Strikes Out-of-Money)' },
                    { key: 'ALL', label: '✨ ALL (ATM + ITM + OTM)' },
                  ].map(m => (
                    <button
                      key={m.key}
                      className="sim-speed-pill"
                      data-active={sim.moneyness === m.key}
                      style={{ height: 26, padding: '0 10px', fontSize: 10, borderRadius: 13 }}
                      onClick={() => sim.setMoneyness(m.key)}
                      disabled={simActive}
                    >
                      {m.label}
                    </button>
                  ))}
                </div>
              </div>

              {/* Position Sizing (Lots) */}
              <div>
                <div style={{ fontSize: 11, fontWeight: 700, color: 'var(--k-cyan)', marginBottom: 8 }}>
                  📦 POSITION SIZING (LOTS)
                </div>
                <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                  {[1, 2, 5, 10, 25, 50].map(l => (
                    <button
                      key={l}
                      className="sim-speed-pill"
                      data-active={sim.lots === l}
                      style={{ height: 26, padding: '0 10px', fontSize: 10 }}
                      onClick={() => sim.setLots(l)}
                      disabled={simActive}
                    >
                      {l} {l === 1 ? 'Lot' : 'Lots'}
                    </button>
                  ))}
                  <input
                    type="number"
                    min={1}
                    max={100}
                    className="sim-input"
                    style={{ width: 50, height: 26 }}
                    value={sim.lots}
                    onChange={e => sim.setLots(Math.max(1, parseInt(e.target.value) || 1))}
                    disabled={simActive}
                  />
                </div>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Replay Signal Stream Drawer */}
      {showStreamDrawer && (
        <div className="sim-drawer-overlay" onClick={() => setShowStreamDrawer(false)}>
          <div className="sim-drawer-card" onClick={e => e.stopPropagation()}>
            <div className="sim-drawer-header">
              <div className="sim-drawer-title">
                ⚡ REPLAY SIGNAL LOG ({sim.status.stats.events.length})
              </div>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                {sim.status.stats.events.length > 0 && (
                  <button
                    className="sim-speed-pill"
                    style={{ height: 22, padding: '0 8px', fontSize: 9, borderColor: 'var(--k-green)', color: 'var(--k-green)', background: 'color-mix(in srgb, var(--k-green) 12%, transparent)' }}
                    onClick={() => exportSignalsToCSV(sim.status.stats.events, sim.date)}
                    title="Export Signal Log to CSV"
                  >
                    📥 Export CSV
                  </button>
                )}
                <button className="sim-drawer-close" onClick={() => setShowStreamDrawer(false)}>✕</button>
              </div>
            </div>

            <div className="sim-drawer-body">
              {sim.status.stats.events.length === 0 ? (
                <div className="sim-drawer-empty">
                  Replay stepping through bars... No signals triggered yet.
                </div>
              ) : (
                sim.status.stats.events.slice().reverse().map((ev, i) => (
                  <div key={i} className="sim-stream-row" data-direction={ev.direction}>
                    <div className="sim-stream-time">{ev.time_iso}</div>
                    <div className="sim-stream-strat">[{ev.strategy.toUpperCase()}]</div>
                    <div className="sim-stream-inst">{ev.instrument}</div>
                    <div className="sim-stream-dir" data-bull={ev.direction === 'BULLISH' || ev.direction === 'LONG'}>
                      {ev.direction}
                    </div>
                    <div className="sim-stream-price">Entry: ₹{ev.entry}</div>
                    <div className="sim-stream-sl">SL: ₹{ev.stop}</div>
                    <div className="sim-stream-tp">TP: ₹{ev.target}</div>
                  </div>
                ))
              )}
            </div>
          </div>
        </div>
      )}

      <div className="sim-bar-wrapper" data-open={barOpen}>
        <div className="sim-bar">
          {/* Left: Input group */}
          <div className="sim-date-group">
            <button
              className="sim-speed-pill"
              style={{ height: 26, padding: '0 8px', fontSize: 10, borderColor: 'var(--k-cyan)', color: 'var(--k-cyan)', background: 'color-mix(in srgb, var(--k-cyan) 12%, transparent)' }}
              onClick={() => setShowConfigModal(true)}
              disabled={simActive}
              title="Configure Strategies, Moneyness & Lots"
            >
              ⚙️ Config
            </button>
            <select
              className="sim-input"
              style={{ paddingRight: 4, cursor: 'pointer' }}
              value={sim.selectedStrategy}
              onChange={e => sim.setSelectedStrategy(e.target.value)}
              disabled={simActive}
              title="Select strategy to replay (or ALL)"
            >
              <option value="all">⚡ ALL STRATEGIES</option>
              <option value="supertrend">🎯 SUPERTREND</option>
              <option value="vcp">📈 VCP SQUEEZE</option>
              <option value="adaptive_edge">⚡ ADAPTIVE EDGE</option>
              <option value="bear_to_bearish">📉 BEAR TO BEARISH</option>
              <option value="atm_imbalance">⚖️ ATM IMBALANCE</option>
              <option value="navigator">🧭 NAVIGATOR</option>
              <option value="nifty_orb">🔔 NIFTY ORB</option>
            </select>
            <select
              className="sim-input"
              style={{ paddingRight: 4, cursor: 'pointer' }}
              value={sim.moneyness}
              onChange={e => sim.setMoneyness(e.target.value)}
              disabled={simActive}
              title="Strike selection (ATM, ITM, OTM, or ALL)"
            >
              <option value="ATM">🎯 ATM (At-The-Money)</option>
              <option value="ITM1">🟢 ITM1 (In-The-Money +1)</option>
              <option value="ITM2">🟢 ITM2 (In-The-Money +2)</option>
              <option value="OTM1">🔴 OTM1 (Out-of-Money +1)</option>
              <option value="OTM2">🔴 OTM2 (Out-of-Money +2)</option>
              <option value="ALL">✨ ALL (ATM + ITM + OTM)</option>
            </select>
            <div style={{ display: 'flex', alignItems: 'center', gap: 3 }}>
              <span style={{ fontSize: 9, fontWeight: 700, color: 'var(--k-dim)' }}>LOTS:</span>
              <input
                type="number"
                min={1}
                max={100}
                className="sim-input"
                style={{ width: 44 }}
                value={sim.lots}
                onChange={e => sim.setLots(Math.max(1, parseInt(e.target.value) || 1))}
                disabled={simActive}
                title="Number of lots per position"
              />
            </div>
            <input 
              type="date" 
              className="sim-input" 
              value={sim.date} 
              onChange={e => sim.setDate(e.target.value)} 
              disabled={simActive}
            />
            <input 
              type="time" 
              className="sim-input" 
              value={sim.startTime} 
              onChange={e => sim.setStartTime(e.target.value)} 
              disabled={simActive}
            />
            <input 
              type="time" 
              className="sim-input" 
              value={sim.endTime} 
              onChange={e => sim.setEndTime(e.target.value)} 
              disabled={simActive}
            />
          </div>

          {/* Transport */}
          <div className="sim-transport">
            <button className="sim-btn" title="Jump to start" onClick={sim.jumpStart} disabled={!simActive}>⏮</button>
            <button className="sim-btn" title="Back 5 bars" onClick={() => sim.stepBars(-5)} disabled={!simActive}>◀◀</button>
            
            {sim.status.state === 'running' ? (
              <button className="sim-btn sim-btn--play" title="Pause (Space)" onClick={sim.pause}>⏸</button>
            ) : sim.status.state === 'paused' ? (
              <button className="sim-btn sim-btn--play" title="Resume (Space)" onClick={sim.resume}>⏵</button>
            ) : (
              <button className="sim-btn sim-btn--play" title="Start Replay (Space)" onClick={sim.start}>⏵</button>
            )}
            
            <button className="sim-btn" title="Forward 5 bars" onClick={() => sim.stepBars(5)} disabled={!simActive}>▶▶</button>
            <button className="sim-btn" title="Jump to end" onClick={sim.jumpEnd} disabled={!simActive}>⏭</button>
            <button className="sim-btn sim-btn--stop" title="Stop & View Summary" onClick={sim.stop} disabled={!simActive}>⏹</button>
          </div>

          {/* Status Message / Hydration Banner */}
          {sim.status.state === 'loading' && (
            <div className="sim-status-banner">
              <span className="sim-spinner">⚡</span>
              <span>{sim.status.status_message || 'Hydrating historical candles...'}</span>
            </div>
          )}

          {/* Last Fired Signal Ticker */}
          {sim.status.state !== 'loading' && sim.status.last_signal && (
            <div 
              className="sim-last-signal-pill" 
              data-direction={sim.status.last_signal.direction}
              onClick={() => setShowStreamDrawer(true)}
              title="Click to view all replayed signals log"
            >
              <span className="sim-sig-dot" />
              <span className="sim-sig-strat">[{sim.status.last_signal.strategy.toUpperCase()}]</span>
              <span className="sim-sig-inst">{sim.status.last_signal.instrument}</span>
              <span className="sim-sig-dir">{isBullish ? 'BUY' : 'SELL'}</span>
              <span className="sim-sig-price">@ ₹{sim.status.last_signal.entry}</span>
              <span className="sim-sig-time">({sim.status.last_signal.time_iso})</span>
            </div>
          )}

          {/* Timeline */}
          <div className="sim-timeline">
            <div className="sim-timeline-header">
              <span>{sim.status.config?.resolution || '5m'}</span>
              <span className="sim-clock">
                {formatTime(sim.status.current_time_iso, 8)}
              </span>
              <span>{sim.status.bars_played} / {sim.status.bars_total} bars</span>
            </div>
            
            <div className="sim-progress-track">
              <div className="sim-progress-fill" style={{ width: `${sim.status.progress_pct}%` }} />
              <div className="sim-progress-head" data-playing={sim.status.state === 'running'} style={{ left: `${sim.status.progress_pct}%` }} />
            </div>

            <div className="sim-ticks">
              {TICKS.map((t, i) => <span key={i} className="sim-tick">{t}</span>)}
            </div>

            <div className="sim-heatmap">
              {heatmapDots}
            </div>
          </div>

          {/* Speeds */}
          <div className="sim-speeds">
            {[1, 5, 10, 50, 100, 250, 500, 1000, 5000].map(s => (
              <button 
                key={s} 
                className="sim-speed-pill" 
                data-active={sim.speed === s}
                onClick={() => sim.setSpeed(s)}
              >
                {s === 5000 ? '⚡ MAX' : `${s}×`}
              </button>
            ))}
          </div>

          {/* Stats */}
          <div className="sim-stats">
            <button 
              className="sim-stream-btn"
              onClick={() => setShowStreamDrawer(true)}
              title="Open full signal stream drawer"
            >
              ⚡ Signals ({sim.status.stats.signals_fired})
            </button>

            <div className="sim-stat">
              <span className="sim-stat-label">W/L</span>
              <span className="sim-stat-value">{sim.status.stats.wins}/{sim.status.stats.losses}</span>
            </div>

            <div className="sim-stat">
              <span className="sim-stat-label">P&L</span>
              <span 
                className="sim-stat-value" 
                data-positive={sim.status.stats.pnl > 0 ? true : sim.status.stats.pnl < 0 ? false : undefined}
              >
                {sim.status.stats.pnl > 0 ? '+' : ''}{sim.status.stats.pnl.toFixed(2)}
              </span>
            </div>
          </div>
        </div>
      </div>
    </>
  );
}

export function SimulationFooterButton() {
  const barOpen = useSimBarOpen();
  const setBarOpen = useSimulationStore(s => s.setBarOpen);
  const active = useSimActive();
  
  return (
    <button 
      className="sim-footer-btn" 
      data-active={barOpen || active} 
      onClick={() => setBarOpen(!barOpen)}
      style={{
        background: active ? 'color-mix(in srgb, var(--k-cyan, #22d3ee) 20%, transparent)' : undefined,
        borderColor: active ? 'var(--k-cyan, #22d3ee)' : undefined,
        boxShadow: active ? '0 0 10px color-mix(in srgb, var(--k-cyan, #22d3ee) 30%, transparent)' : undefined,
      }}
    >
      <span style={{ fontSize: '11px' }}>{active ? '⚡' : '▶'}</span>
      REPLAY {active ? 'ACTIVE' : ''}
    </button>
  );
}

export function SimulationFooterBadge() {
  const active = useSimActive();
  if (!active) return null;
  
  return (
    <div className="sim-footer-badge" data-playing={true}>
      <span style={{ width: 6, height: 6, borderRadius: '50%', background: 'var(--k-cyan)', boxShadow: '0 0 4px var(--k-cyan)' }}></span>
      REPLAYING
    </div>
  );
}
