import React, { useEffect, useMemo, useRef, useState } from 'react';
import { useSimulation, useSimulationStore, useSimBarOpen, useSimActive, SimSignalEvent, SimTradeEvent } from '../../hooks/useSimulation';
import { k } from '../../styles/kiteUI';
import './SimulationBar.css';

// Utility to tint colors
const tint = (color: string, opacity: number) => `color-mix(in srgb, ${color} ${opacity * 100}%, transparent)`;

// Tick intervals for 30 mins
const TICKS = ['09:15', '09:45', '10:15', '10:45', '11:15', '11:45', '12:15', '12:45', '13:15', '13:45', '14:15', '14:45', '15:15', '15:30'];

const STRATEGY_OPTIONS = [
  { id: 'supertrend', label: '🎯 SUPERTREND' },
  { id: 'vcp', label: '📈 VCP SQUEEZE' },
  { id: 'adaptive_edge', label: '⚡ ADAPTIVE EDGE' },
  { id: 'bear_to_bearish', label: '📉 BEAR TO BEARISH' },
  { id: 'atm_imbalance', label: '⚖️ ATM IMBALANCE' },
  { id: 'navigator', label: '🧭 NAVIGATOR' },
  { id: 'nifty_orb', label: '🔔 NIFTY ORB' },
];

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

// Helper: export replayed trades log to CSV
export function exportTradesToCSV(trades: SimTradeEvent[], date: string) {
  if (!trades || trades.length === 0) return;
  const headers = ['Trade ID', 'Entry Time', 'Exit Time', 'Strategy', 'Symbol', 'Underlying', 'Direction', 'Option Type', 'Strike', 'Lots', 'Quantity', 'Entry Price', 'Exit Price', 'Status', 'PnL (INR)', 'PnL (%)', 'Duration (Mins)'];
  const rows = trades.map(tr => [
    tr.trade_id,
    tr.entry_time_iso,
    tr.exit_time_iso,
    (tr.strategy || '').toUpperCase(),
    tr.symbol,
    tr.underlying,
    tr.direction,
    tr.opt_type,
    tr.strike,
    tr.lots,
    tr.quantity,
    tr.entry_price,
    tr.exit_price || '',
    tr.status,
    tr.pnl_usd,
    tr.pnl_pct,
    tr.duration_mins,
  ]);
  const csvContent = [headers.join(','), ...rows.map(r => r.join(','))].join('\n');
  const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = `sterling_replay_trades_${date}.csv`;
  a.click();
  URL.revokeObjectURL(url);
}

export function SimulationBar() {
  const sim = useSimulation();
  const barOpen = useSimBarOpen();
  const simActive = useSimActive();
  const [showStreamDrawer, setShowStreamDrawer] = useState(false);
  const [drawerTab, setDrawerTab] = useState<'signals' | 'trades'>('signals');
  const [toastSignal, setToastSignal] = useState<SimSignalEvent | null>(null);

  const [isExpanded, setIsExpanded] = useState(false);
  const [activeDockTab, setActiveDockTab] = useState<'config' | 'signals' | 'trades'>('config');
  const [viewMode, setViewMode] = useState<'docked' | 'half' | 'maximized'>('docked');

  const [showStratDropdown, setShowStratDropdown] = useState(false);
  const [showLegsDropdown, setShowLegsDropdown] = useState(false);
  const [showConfigModal, setShowConfigModal] = useState(false);

  const stratDropdownRef = useRef<HTMLDivElement>(null);
  const legsDropdownRef = useRef<HTMLDivElement>(null);

  // Close dropdowns on click outside
  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (stratDropdownRef.current && !stratDropdownRef.current.contains(e.target as Node)) {
        setShowStratDropdown(false);
      }
      if (legsDropdownRef.current && !legsDropdownRef.current.contains(e.target as Node)) {
        setShowLegsDropdown(false);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

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

      {/* Replay Signal & Trade Stream Drawer */}
      {showStreamDrawer && (
        <div className="sim-drawer-overlay" onClick={() => setShowStreamDrawer(false)}>
          <div className="sim-drawer-card" style={{ width: 780, maxWidth: '92vw' }} onClick={e => e.stopPropagation()}>
            <div className="sim-drawer-header">
              <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                <button
                  className="sim-speed-pill"
                  data-active={drawerTab === 'signals'}
                  onClick={() => setDrawerTab('signals')}
                  style={{ height: 26, fontSize: 10 }}
                >
                  ⚡ SIGNALS ({sim.status.stats.events.length})
                </button>
                <button
                  className="sim-speed-pill"
                  data-active={drawerTab === 'trades'}
                  onClick={() => setDrawerTab('trades')}
                  style={{ height: 26, fontSize: 10 }}
                >
                  💼 EXECUTED TRADES ({(sim.status.stats.trades || []).length})
                </button>
              </div>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                {drawerTab === 'signals' && sim.status.stats.events.length > 0 && (
                  <button
                    className="sim-speed-pill"
                    style={{ height: 22, padding: '0 8px', fontSize: 9, borderColor: 'var(--k-green)', color: 'var(--k-green)', background: 'color-mix(in srgb, var(--k-green) 12%, transparent)' }}
                    onClick={() => exportSignalsToCSV(sim.status.stats.events, sim.date)}
                    title="Export Signal Log to CSV"
                  >
                    📥 Export Signals CSV
                  </button>
                )}
                {drawerTab === 'trades' && (sim.status.stats.trades || []).length > 0 && (
                  <button
                    className="sim-speed-pill"
                    style={{ height: 22, padding: '0 8px', fontSize: 9, borderColor: 'var(--k-green)', color: 'var(--k-green)', background: 'color-mix(in srgb, var(--k-green) 12%, transparent)' }}
                    onClick={() => exportTradesToCSV(sim.status.stats.trades || [], sim.date)}
                    title="Export Trades Log to CSV"
                  >
                    📥 Export Trades CSV
                  </button>
                )}
                <button className="sim-drawer-close" onClick={() => setShowStreamDrawer(false)}>✕</button>
              </div>
            </div>

            <div className="sim-drawer-body">
              {drawerTab === 'signals' ? (
                sim.status.stats.events.length === 0 ? (
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
                )
              ) : (
                !(sim.status.stats.trades && sim.status.stats.trades.length > 0) ? (
                  <div className="sim-drawer-empty">
                    No trades executed yet. Strong signals will enter trades automatically.
                  </div>
                ) : (
                  <table style={{ width: '100%', fontSize: 11, textAlign: 'left', borderCollapse: 'collapse' }}>
                    <thead>
                      <tr style={{ borderBottom: '1px solid var(--k-border)', color: 'var(--k-dim)', fontSize: 10 }}>
                        <th style={{ padding: '6px 4px' }}>ID</th>
                        <th style={{ padding: '6px 4px' }}>Time</th>
                        <th style={{ padding: '6px 4px' }}>Strategy</th>
                        <th style={{ padding: '6px 4px' }}>Contract</th>
                        <th style={{ padding: '6px 4px' }}>Lots (Qty)</th>
                        <th style={{ padding: '6px 4px' }}>Entry ₹</th>
                        <th style={{ padding: '6px 4px' }}>Exit ₹</th>
                        <th style={{ padding: '6px 4px' }}>Status</th>
                        <th style={{ padding: '6px 4px', textAlign: 'right' }}>Realized P&L</th>
                      </tr>
                    </thead>
                    <tbody>
                      {sim.status.stats.trades.slice().reverse().map((tr, i) => {
                        const isWin = tr.status === 'WIN';
                        return (
                          <tr key={i} style={{ borderBottom: '1px solid color-mix(in srgb, var(--k-text) 6%, transparent)' }}>
                            <td style={{ padding: '6px 4px', fontFamily: 'monospace', color: 'var(--k-cyan)', fontWeight: 600 }}>{tr.trade_id}</td>
                            <td style={{ padding: '6px 4px', color: 'var(--k-dim)' }}>{tr.entry_time_iso} → {tr.exit_time_iso}</td>
                            <td style={{ padding: '6px 4px', fontWeight: 600, color: 'var(--k-text)' }}>[{tr.strategy.toUpperCase()}]</td>
                            <td style={{ padding: '6px 4px', color: 'var(--k-text)', fontWeight: 600 }}>{tr.symbol}</td>
                            <td style={{ padding: '6px 4px', color: 'var(--k-dim)' }}>{tr.lots}L ({tr.quantity}Q)</td>
                            <td style={{ padding: '6px 4px', color: 'var(--k-text)' }}>₹{tr.entry_price}</td>
                            <td style={{ padding: '6px 4px', color: 'var(--k-text)' }}>{tr.exit_price ? `₹${tr.exit_price}` : '--'}</td>
                            <td style={{ padding: '6px 4px' }}>
                              <span style={{
                                padding: '2px 6px',
                                borderRadius: 4,
                                fontSize: 9,
                                fontWeight: 700,
                                background: isWin ? 'color-mix(in srgb, var(--k-green) 15%, transparent)' : 'color-mix(in srgb, var(--k-red) 15%, transparent)',
                                color: isWin ? 'var(--k-green)' : 'var(--k-red)',
                              }}>
                                {tr.status}
                              </span>
                            </td>
                            <td style={{ padding: '6px 4px', textAlign: 'right', fontWeight: 700, color: tr.pnl_usd >= 0 ? 'var(--k-green)' : 'var(--k-red)' }}>
                              {tr.pnl_usd >= 0 ? '+' : ''}₹{tr.pnl_usd.toFixed(2)} ({tr.pnl_pct >= 0 ? '+' : ''}{tr.pnl_pct}%)
                            </td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                )
              )}
            </div>
          </div>
        </div>
      )}

      {/* Expandable Replay Footer Dock (Sterling Dock Shell) */}
      <div 
        className="sim-bar-wrapper kw-pane" 
        data-open={barOpen}
        style={{
          height: viewMode === 'maximized' ? '80vh' : viewMode === 'half' ? '50vh' : 'auto',
          maxHeight: viewMode === 'maximized' ? '80vh' : viewMode === 'half' ? '50vh' : 'none',
          transition: 'height 0.25s ease, max-height 0.25s ease',
        }}
      >
        {/* Sterling Dock Shell Header Bar */}
        <div
          style={{
            height: 31,
            flexShrink: 0,
            display: 'flex',
            alignItems: 'center',
            gap: 7,
            padding: '0 8px',
            borderBottom: '1px solid var(--k-border-2)',
            background: 'var(--k-surface-3)',
            userSelect: 'none',
          }}
        >
          {/* Drag Handle & Icon */}
          <span aria-hidden="true" style={{ width: 10, display: 'grid', gridTemplateColumns: 'repeat(2,3px)', gap: 2, color: '#c2c2c2', flexShrink: 0 }}>
            {Array.from({ length: 6 }).map((_, index) => <span key={index} style={{ width: 2.5, height: 2.5, borderRadius: '50%', background: 'currentColor' }} />)}
          </span>
          <span style={{ color: 'var(--k-cyan)', display: 'inline-flex' }}>⚡</span>

          {/* Title & Status */}
          <span style={{ fontSize: 11, fontWeight: 650, color: 'var(--k-text)', letterSpacing: '.01em' }}>
            MARKET REPLAY ENGINE
          </span>
          <span style={{ fontSize: 9.5, fontWeight: 700, color: 'var(--k-dim)', fontVariantNumeric: 'tabular-nums' }}>
            [{sim.status.current_time_iso || '09:15:00'} IST · {sim.speed}× SPEED]
          </span>

          {/* Right-Aligned Dock Window Controls */}
          <div style={{ marginLeft: 'auto', display: 'flex', alignItems: 'center', gap: 2 }}>
            {/* Config Toggle */}
            <button
              type="button"
              className="kw-pane-control"
              style={{ width: 'auto', padding: '0 6px', fontSize: 10, fontWeight: 700, color: isExpanded ? 'var(--k-cyan)' : 'var(--k-dim)' }}
              onClick={() => setIsExpanded(!isExpanded)}
              title="Toggle Expandable Dock Panel"
            >
              {isExpanded ? '▼ DOCK' : '▲ DOCK'}
            </button>

            {/* Minimize */}
            <button
              type="button"
              className="kw-pane-control"
              title="Minimize Dock"
              aria-label="Minimize Dock"
              onClick={() => sim.setBarOpen(false)}
            >
              <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M5 18h14"/></svg>
            </button>

            {/* Half Screen */}
            <button
              type="button"
              className="kw-pane-control"
              title="Half Screen View"
              aria-label="Half Screen View"
              onClick={() => setViewMode(viewMode === 'half' ? 'docked' : 'half')}
            >
              <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8"><rect x="3" y="4" width="18" height="16" rx="2"/><path d="M12 4v16"/><path d="M3 4h9v16H3z" fill="currentColor" opacity=".14" stroke="none"/></svg>
            </button>

            {/* Maximize */}
            <button
              type="button"
              className="kw-pane-control"
              title="Maximize Dock View"
              aria-label="Maximize Dock View"
              onClick={() => setViewMode(viewMode === 'maximized' ? 'docked' : 'maximized')}
            >
              <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8"><rect x="4" y="4" width="16" height="16" rx="2"/></svg>
            </button>

            {/* Full Screen */}
            <button
              type="button"
              className="kw-pane-control"
              title="Full Screen Presentation"
              aria-label="Full Screen Presentation"
              onClick={() => {
                if (!document.fullscreenElement) {
                  document.documentElement.requestFullscreen().catch(() => {});
                } else {
                  document.exitFullscreen().catch(() => {});
                }
              }}
            >
              <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round"><path d="M8 3H3v5M16 3h5v5M21 16v5h-5M8 21H3v-5"/></svg>
            </button>
          </div>
        </div>

        {/* Top Dock Toolbar Strip */}
        <div className="sim-dock-toolbar">
          {/* Left: Quick Date & Time Inputs */}
          <div className="sim-date-group">
            <button
              className="sim-speed-pill"
              style={{ height: 26, padding: '0 8px', fontSize: 10, borderColor: 'var(--k-cyan)', color: 'var(--k-cyan)', background: 'color-mix(in srgb, var(--k-cyan) 12%, transparent)' }}
              onClick={() => { setActiveDockTab('config'); setIsExpanded(!isExpanded); }}
              disabled={simActive}
              title="Configure Strategies, Moneyness & Lots"
            >
              ⚙️ Config
            </button>

            {/* Multi-Select Strategy Dropdown Button */}
            <div ref={stratDropdownRef} style={{ position: 'relative' }}>
              <button
                className="sim-speed-pill"
                style={{ height: 26, padding: '0 8px', fontSize: 10, borderColor: 'var(--k-border-strong-3)' }}
                onClick={(e) => {
                  e.stopPropagation();
                  setShowStratDropdown(!showStratDropdown);
                  setShowLegsDropdown(false);
                }}
                disabled={simActive}
                title="Multi-select strategies to replay"
              >
                ⚡ STRATEGIES ({sim.selectedStrategies.includes('all') ? 'ALL' : sim.selectedStrategies.length}) ▼
              </button>

              {showStratDropdown && (
                <div 
                  style={{
                    position: 'absolute',
                    top: 32,
                    left: 0,
                    zIndex: 10000,
                    width: 230,
                    padding: 8,
                    borderRadius: 8,
                    border: '1px solid var(--k-border-strong-3)',
                    background: 'var(--k-surface-3, #181d28)',
                    boxShadow: '0 12px 32px rgba(0,0,0,0.65)',
                    display: 'flex',
                    flexDirection: 'column',
                    gap: 4,
                  }}
                  onClick={(e) => e.stopPropagation()}
                >
                  <div style={{ fontSize: 9.5, fontWeight: 750, color: 'var(--k-dim)', padding: '2px 4px', textTransform: 'uppercase' }}>
                    Select Strategies:
                  </div>
                  <button
                    type="button"
                    className="sim-speed-pill"
                    data-active={sim.selectedStrategies.includes('all')}
                    style={{ textAlign: 'left', justifyContent: 'flex-start' }}
                    onClick={(e) => {
                      e.stopPropagation();
                      sim.toggleStrategy('all');
                    }}
                  >
                    <span style={{ marginRight: 6 }}>{sim.selectedStrategies.includes('all') ? '☑' : '☐'}</span>
                    ⚡ ALL STRATEGIES
                  </button>
                  {STRATEGY_OPTIONS.map(strat => {
                    const isSel = sim.selectedStrategies.includes(strat.id);
                    return (
                      <button
                        type="button"
                        key={strat.id}
                        className="sim-speed-pill"
                        data-active={isSel}
                        style={{ textAlign: 'left', justifyContent: 'flex-start' }}
                        onClick={(e) => {
                          e.stopPropagation();
                          sim.toggleStrategy(strat.id);
                        }}
                      >
                        <span style={{ marginRight: 6 }}>{isSel ? '☑' : '☐'}</span>
                        {strat.label}
                      </button>
                    );
                  })}
                </div>
              )}
            </div>

            {/* Multi-Select Moneyness / Legs Dropdown Button */}
            <div ref={legsDropdownRef} style={{ position: 'relative' }}>
              <button
                className="sim-speed-pill"
                style={{ height: 26, padding: '0 8px', fontSize: 10, borderColor: 'var(--k-border-strong-3)' }}
                onClick={(e) => {
                  e.stopPropagation();
                  setShowLegsDropdown(!showLegsDropdown);
                  setShowStratDropdown(false);
                }}
                disabled={simActive}
                title="Multi-select strike moneyness legs"
              >
                🎯 LEGS ({sim.selectedMoneyness.includes('ALL') ? 'ALL' : sim.selectedMoneyness.length}) ▼
              </button>

              {showLegsDropdown && (
                <div 
                  style={{
                    position: 'absolute',
                    top: 32,
                    left: 0,
                    zIndex: 10000,
                    width: 220,
                    padding: 8,
                    borderRadius: 8,
                    border: '1px solid var(--k-border-strong-3)',
                    background: 'var(--k-surface-3, #181d28)',
                    boxShadow: '0 12px 32px rgba(0,0,0,0.65)',
                    display: 'flex',
                    flexDirection: 'column',
                    gap: 4,
                  }}
                  onClick={(e) => e.stopPropagation()}
                >
                  <div style={{ fontSize: 9.5, fontWeight: 750, color: 'var(--k-dim)', padding: '2px 4px', textTransform: 'uppercase' }}>
                    Select Option Legs:
                  </div>
                  {[
                    { key: 'ALL', label: '✨ ALL (ATM + ITM + OTM)' },
                    { key: 'ATM', label: '🎯 ATM (At-The-Money)' },
                    { key: 'ITM1', label: '🟢 ITM1 (+1 Strike ITM)' },
                    { key: 'ITM2', label: '🟢 ITM2 (+2 Strikes ITM)' },
                    { key: 'OTM1', label: '🔴 OTM1 (+1 Strike OTM)' },
                    { key: 'OTM2', label: '🔴 OTM2 (+2 Strikes OTM)' },
                  ].map(leg => {
                    const isSel = sim.selectedMoneyness.includes(leg.key);
                    return (
                      <button
                        type="button"
                        key={leg.key}
                        className="sim-speed-pill"
                        data-active={isSel}
                        style={{ textAlign: 'left', justifyContent: 'flex-start' }}
                        onClick={(e) => {
                          e.stopPropagation();
                          sim.toggleMoneyness(leg.key);
                        }}
                      >
                        <span style={{ marginRight: 6 }}>{isSel ? '☑' : '☐'}</span>
                        {leg.label}
                      </button>
                    );
                  })}
                </div>
              )}
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

          {/* Center: Transport & Speeds */}
          <div className="sim-transport">
            <button className="sim-btn" title="Jump to start (Home)" onClick={sim.jumpStart} disabled={!simActive}>⏮</button>
            <button className="sim-btn" title="Back 5 bars (←)" onClick={() => sim.stepBars(-5)} disabled={!simActive}>◀◀</button>
            
            {sim.status.state === 'running' ? (
              <button className="sim-btn sim-btn--play" title="Pause (Space)" onClick={sim.pause}>⏸</button>
            ) : sim.status.state === 'paused' ? (
              <button className="sim-btn sim-btn--play" title="Resume (Space)" onClick={sim.resume}>⏵</button>
            ) : (
              <button className="sim-btn sim-btn--play" title="Start Replay (Space)" onClick={sim.start}>⏵</button>
            )}
            
            <button className="sim-btn" title="Forward 5 bars (→)" onClick={() => sim.stepBars(5)} disabled={!simActive}>▶▶</button>
            <button className="sim-btn" title="Jump to end (End)" onClick={sim.jumpEnd} disabled={!simActive}>⏭</button>
            <button className="sim-btn sim-btn--stop" title="Stop & View Summary" onClick={sim.stop} disabled={!simActive}>⏹</button>
          </div>

          {/* Speed Pills */}
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

          {/* Timeline */}
          <div className="sim-timeline" style={{ maxWidth: 180 }}>
            <div className="sim-timeline-header">
              <span className="sim-clock">{sim.status.current_time_iso || sim.startTime}</span>
              <span>{sim.status.progress_pct}%</span>
            </div>
            <div className="sim-progress-track">
              <div className="sim-progress-fill" style={{ width: `${sim.status.progress_pct}%` }} />
            </div>
          </div>

          {/* Right: Expandable Dock Tabs & Stats */}
          <div className="sim-stats">
            <button 
              className="sim-speed-pill"
              data-active={isExpanded && activeDockTab === 'signals'}
              onClick={() => { setActiveDockTab('signals'); setIsExpanded(true); }}
              title="Open replayed signals log"
            >
              ⚡ Signals ({sim.status.stats.signals_fired})
            </button>

            <button 
              className="sim-speed-pill"
              data-active={isExpanded && activeDockTab === 'trades'}
              onClick={() => { setActiveDockTab('trades'); setIsExpanded(true); }}
              title="Open executed paper trades log"
            >
              💼 Trades ({(sim.status.stats.trades || []).length})
            </button>

            <button
              className="sim-speed-pill"
              style={{ color: 'var(--k-cyan)', borderColor: 'var(--k-cyan)', background: isExpanded ? 'color-mix(in srgb, var(--k-cyan) 20%, transparent)' : undefined }}
              onClick={() => setIsExpanded(!isExpanded)}
              title={isExpanded ? 'Collapse Dock' : 'Expand Dock'}
            >
              {isExpanded ? '▼ Dock' : '▲ Dock'}
            </button>
          </div>
        </div>

        {/* Expandable Multi-Tab Dock Panel */}
        <div className="sim-dock-expandable" data-expanded={isExpanded}>
          <div className="sim-dock-tabstrip">
            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <button
                className="sim-speed-pill"
                data-active={activeDockTab === 'config'}
                onClick={() => setActiveDockTab('config')}
              >
                ⚙️ CONFIGURATION
              </button>
              <button
                className="sim-speed-pill"
                data-active={activeDockTab === 'signals'}
                onClick={() => setActiveDockTab('signals')}
              >
                ⚡ SIGNALS ({sim.status.stats.events.length})
              </button>
              <button
                className="sim-speed-pill"
                data-active={activeDockTab === 'trades'}
                onClick={() => setActiveDockTab('trades')}
              >
                💼 EXECUTED TRADES ({(sim.status.stats.trades || []).length})
              </button>
            </div>

            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              {activeDockTab === 'signals' && sim.status.stats.events.length > 0 && (
                <button
                  className="sim-speed-pill"
                  style={{ height: 22, padding: '0 8px', fontSize: 9, borderColor: 'var(--k-green)', color: 'var(--k-green)' }}
                  onClick={() => exportSignalsToCSV(sim.status.stats.events, sim.date)}
                >
                  📥 Export Signals CSV
                </button>
              )}
              {activeDockTab === 'trades' && (sim.status.stats.trades || []).length > 0 && (
                <button
                  className="sim-speed-pill"
                  style={{ height: 22, padding: '0 8px', fontSize: 9, borderColor: 'var(--k-green)', color: 'var(--k-green)' }}
                  onClick={() => exportTradesToCSV(sim.status.stats.trades || [], sim.date)}
                >
                  📥 Export Trades CSV
                </button>
              )}
              <button className="sim-drawer-close" onClick={() => setIsExpanded(false)}>✕</button>
            </div>
          </div>

          <div className="sim-dock-content">
            {activeDockTab === 'config' && (
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 20 }}>
                <div>
                  <div style={{ fontSize: 11, fontWeight: 700, color: 'var(--k-cyan)', marginBottom: 8 }}>
                    ⚡ ACTIVE REPLAY STRATEGIES (MULTI-SELECT)
                  </div>
                  <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
                    <button
                      className="sim-speed-pill"
                      data-active={sim.selectedStrategies.includes('all')}
                      style={{ height: 26, padding: '0 10px', fontSize: 10 }}
                      onClick={() => sim.toggleStrategy('all')}
                      disabled={simActive}
                    >
                      ⚡ ALL STRATEGIES
                    </button>
                    {STRATEGY_OPTIONS.map(strat => {
                      const isSel = sim.selectedStrategies.includes(strat.id);
                      return (
                        <button
                          key={strat.id}
                          className="sim-speed-pill"
                          data-active={isSel}
                          style={{ height: 26, padding: '0 10px', fontSize: 10 }}
                          onClick={() => sim.toggleStrategy(strat.id)}
                          disabled={simActive}
                        >
                          <span style={{ marginRight: 4 }}>{isSel ? '☑' : '☐'}</span>
                          {strat.label}
                        </button>
                      );
                    })}
                  </div>
                </div>
                <div>
                  <div style={{ fontSize: 11, fontWeight: 700, color: 'var(--k-cyan)', marginBottom: 8 }}>
                    🎯 STRIKE MONEYNESS LEGS (MULTI-SELECT)
                  </div>
                  <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6, marginBottom: 12 }}>
                    <button
                      className="sim-speed-pill"
                      data-active={sim.selectedMoneyness.includes('ALL')}
                      style={{ height: 26, padding: '0 10px', fontSize: 10 }}
                      onClick={() => sim.toggleMoneyness('ALL')}
                      disabled={simActive}
                    >
                      ✨ ALL LEGS
                    </button>
                    {[
                      { id: 'ATM', label: '🎯 ATM' },
                      { id: 'ITM1', label: '🟢 ITM1' },
                      { id: 'ITM2', label: '🟢 ITM2' },
                      { id: 'OTM1', label: '🔴 OTM1' },
                      { id: 'OTM2', label: '🔴 OTM2' },
                    ].map(leg => {
                      const isSel = sim.selectedMoneyness.includes(leg.id);
                      return (
                        <button
                          key={leg.id}
                          className="sim-speed-pill"
                          data-active={isSel}
                          style={{ height: 26, padding: '0 10px', fontSize: 10 }}
                          onClick={() => sim.toggleMoneyness(leg.id)}
                          disabled={simActive}
                        >
                          <span style={{ marginRight: 4 }}>{isSel ? '☑' : '☐'}</span>
                          {leg.label}
                        </button>
                      );
                    })}
                  </div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                    <span style={{ fontSize: 10, color: 'var(--k-dim)' }}>Lots:</span>
                    {[1, 2, 5, 10, 25, 50].map(l => (
                      <button
                        key={l}
                        className="sim-speed-pill"
                        data-active={sim.lots === l}
                        style={{ height: 24, padding: '0 8px', fontSize: 9 }}
                        onClick={() => sim.setLots(l)}
                        disabled={simActive}
                      >
                        {l}L
                      </button>
                    ))}
                  </div>
                </div>
              </div>
            )}

            {activeDockTab === 'signals' && (
              sim.status.stats.events.length === 0 ? (
                <div className="sim-drawer-empty">Replay stepping through bars... No signals triggered yet.</div>
              ) : (
                sim.status.stats.events.slice().reverse().map((ev, i) => (
                  <div key={i} className="sim-stream-row" data-direction={ev.direction}>
                    <div className="sim-stream-time">{ev.time_iso}</div>
                    <div className="sim-stream-strat">[{ev.strategy.toUpperCase()}]</div>
                    <div className="sim-stream-inst">{ev.instrument}</div>
                    <div className="sim-stream-dir" data-bull={ev.direction === 'BULLISH' || ev.direction === 'LONG'}>{ev.direction}</div>
                    <div className="sim-stream-price">Entry: ₹{ev.entry}</div>
                    <div className="sim-stream-sl">SL: ₹{ev.stop}</div>
                    <div className="sim-stream-tp">TP: ₹{ev.target}</div>
                  </div>
                ))
              )
            )}

            {activeDockTab === 'trades' && (
              !(sim.status.stats.trades && sim.status.stats.trades.length > 0) ? (
                <div className="sim-drawer-empty">No trades executed yet. Strong signals will enter trades automatically.</div>
              ) : (
                <table style={{ width: '100%', fontSize: 11, textAlign: 'left', borderCollapse: 'collapse' }}>
                  <thead>
                    <tr style={{ borderBottom: '1px solid var(--k-border)', color: 'var(--k-dim)', fontSize: 10 }}>
                      <th style={{ padding: '6px 4px' }}>ID</th>
                      <th style={{ padding: '6px 4px' }}>Time</th>
                      <th style={{ padding: '6px 4px' }}>Strategy</th>
                      <th style={{ padding: '6px 4px' }}>Contract</th>
                      <th style={{ padding: '6px 4px' }}>Lots (Qty)</th>
                      <th style={{ padding: '6px 4px' }}>Entry ₹</th>
                      <th style={{ padding: '6px 4px' }}>Exit ₹</th>
                      <th style={{ padding: '6px 4px' }}>Status</th>
                      <th style={{ padding: '6px 4px', textAlign: 'right' }}>Realized P&L</th>
                    </tr>
                  </thead>
                  <tbody>
                    {sim.status.stats.trades.slice().reverse().map((tr, i) => {
                      const isWin = tr.status === 'WIN';
                      return (
                        <tr key={i} style={{ borderBottom: '1px solid color-mix(in srgb, var(--k-text) 6%, transparent)' }}>
                          <td style={{ padding: '6px 4px', fontFamily: 'monospace', color: 'var(--k-cyan)', fontWeight: 600 }}>{tr.trade_id}</td>
                          <td style={{ padding: '6px 4px', color: 'var(--k-dim)' }}>{tr.entry_time_iso} → {tr.exit_time_iso}</td>
                          <td style={{ padding: '6px 4px', fontWeight: 600, color: 'var(--k-text)' }}>[{tr.strategy.toUpperCase()}]</td>
                          <td style={{ padding: '6px 4px', color: 'var(--k-text)', fontWeight: 600 }}>{tr.symbol}</td>
                          <td style={{ padding: '6px 4px', color: 'var(--k-dim)' }}>{tr.lots}L ({tr.quantity}Q)</td>
                          <td style={{ padding: '6px 4px', color: 'var(--k-text)' }}>₹{tr.entry_price}</td>
                          <td style={{ padding: '6px 4px', color: 'var(--k-text)' }}>{tr.exit_price ? `₹${tr.exit_price}` : '--'}</td>
                          <td style={{ padding: '6px 4px' }}>
                            <span style={{
                              padding: '2px 6px',
                              borderRadius: 4,
                              fontSize: 9,
                              fontWeight: 700,
                              background: isWin ? 'color-mix(in srgb, var(--k-green) 15%, transparent)' : 'color-mix(in srgb, var(--k-red) 15%, transparent)',
                              color: isWin ? 'var(--k-green)' : 'var(--k-red)',
                            }}>
                              {tr.status}
                            </span>
                          </td>
                          <td style={{ padding: '6px 4px', textAlign: 'right', fontWeight: 700, color: tr.pnl_usd >= 0 ? 'var(--k-green)' : 'var(--k-red)' }}>
                            {tr.pnl_usd >= 0 ? '+' : ''}₹{tr.pnl_usd.toFixed(2)} ({tr.pnl_pct >= 0 ? '+' : ''}{tr.pnl_pct}%)
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              )
            )}
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
  const status = useSimulationStore(s => s.status);
  
  return (
    <button 
      type="button"
      className="kw-dock-chip" 
      data-active={barOpen || active} 
      onClick={() => setBarOpen(!barOpen)}
      style={{
        background: active ? 'color-mix(in srgb, var(--k-cyan, #22d3ee) 18%, transparent)' : undefined,
        borderColor: active ? 'var(--k-cyan, #22d3ee)' : undefined,
        color: active ? 'var(--k-cyan, #22d3ee)' : 'var(--k-ink-3)',
        boxShadow: active ? '0 0 10px color-mix(in srgb, var(--k-cyan, #22d3ee) 30%, transparent)' : undefined,
        fontWeight: 700,
      }}
    >
      <span style={{ color: active ? 'var(--k-cyan)' : 'var(--k-brand)', display: 'inline-flex', fontSize: 11 }}>
        {active ? '⚡' : '▶'}
      </span>
      REPLAY DOCK {active ? `(${status.current_time_iso || 'RUNNING'})` : ''}
    </button>
  );
}

export function SimulationFooterBadge() {
  const active = useSimActive();
  if (!active) return null;
  
  return (
    <span 
      style={{
        display: 'inline-flex',
        alignItems: 'center',
        gap: 5,
        height: 22,
        padding: '0 8px',
        borderRadius: 6,
        background: 'color-mix(in srgb, var(--k-cyan, #22d3ee) 12%, transparent)',
        border: '1px solid color-mix(in srgb, var(--k-cyan, #22d3ee) 40%, transparent)',
        color: 'var(--k-cyan, #22d3ee)',
        fontSize: 9.5,
        fontWeight: 800,
        letterSpacing: '.04em',
      }}
    >
      <span style={{ width: 6, height: 6, borderRadius: '50%', background: 'var(--k-cyan)', boxShadow: '0 0 6px var(--k-cyan)' }} />
      REPLAYING
    </span>
  );
}
