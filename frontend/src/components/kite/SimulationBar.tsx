import React, { useEffect, useMemo, useRef, useState } from 'react';
import { useSimulation, useSimulationStore, useSimBarOpen, useSimActive, SimSignalEvent, SimTradeEvent } from '../../hooks/useSimulation';
import { k } from '../../styles/kiteUI';
import './SimulationBar.css';

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

function parseTimeToMinutes(timeStr?: string): number {
  if (!timeStr) return 0;
  const str = timeStr.includes('T') ? (timeStr.split('T')[1] || '') : timeStr;
  const parts = str.split(':').map(Number);
  if (parts.length >= 2 && !isNaN(parts[0]) && !isNaN(parts[1])) {
    return parts[0] * 60 + parts[1];
  }
  return 0;
}

function formatTime(isoStr?: string, len: number = 8): string {
  if (!isoStr) return '--:--:--';
  const str = isoStr.includes('T') ? (isoStr.split('T')[1] || isoStr) : isoStr;
  return str.substring(0, len);
}

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
  
  const [toastSignal, setToastSignal] = useState<SimSignalEvent | null>(null);

  const [isExpanded, setIsExpanded] = useState(true);
  const [activeDockTab, setActiveDockTab] = useState<'config' | 'signals' | 'trades'>('config');
  const [viewMode, setViewMode] = useState<'docked' | 'half' | 'maximized'>('docked');
  const [dockHeight, setDockHeight] = useState<number | null>(null);
  const [isResizing, setIsResizing] = useState(false);

  const [showStratDropdown, setShowStratDropdown] = useState(false);
  const [showLegsDropdown, setShowLegsDropdown] = useState(false);

  const stratDropdownRef = useRef<HTMLDivElement>(null);
  const legsDropdownRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (barOpen) {
      setIsExpanded(true);
      sim.syncStatus();
    }
  }, [barOpen]);

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

  useEffect(() => {
    if (sim.status.last_signal) {
      setToastSignal(sim.status.last_signal);
      const timer = setTimeout(() => setToastSignal(null), 3000);
      return () => clearTimeout(timer);
    }
  }, [sim.status.last_signal?.time_iso, sim.status.last_signal?.instrument, sim.status.last_signal?.strategy]);

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
        sim.setBarOpen(false);
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
  }, [barOpen, sim]);

  const handleResizeStart = (e: React.MouseEvent) => {
    e.preventDefault();
    setIsResizing(true);
    const startY = e.clientY;
    const startHeight = dockHeight || (viewMode === 'maximized' ? window.innerHeight * 0.8 : viewMode === 'half' ? window.innerHeight * 0.5 : 320);

    const handleMouseMove = (moveEvent: MouseEvent) => {
      const deltaY = startY - moveEvent.clientY;
      const newHeight = Math.max(160, Math.min(window.innerHeight - 80, startHeight + deltaY));
      setDockHeight(newHeight);
      setIsExpanded(true);
    };

    const handleMouseUp = () => {
      setIsResizing(false);
      window.removeEventListener('mousemove', handleMouseMove);
      window.removeEventListener('mouseup', handleMouseUp);
    };

    window.addEventListener('mousemove', handleMouseMove);
    window.addEventListener('mouseup', handleMouseUp);
  };

  const heatmapDots = useMemo(() => {
    if (!sim.status.config) return [];
    
    const startMins = parseTimeToMinutes(sim.status.config.start_time || '09:15:00');
    const endMins = parseTimeToMinutes(sim.status.config.end_time || '15:30:00');
    const totalMins = Math.max(1, endMins - startMins);

    return sim.status.stats.events.map((ev, i) => {
      const evMins = parseTimeToMinutes(ev.time_iso);
      const pct = Math.max(0, Math.min(100, ((evMins - startMins) / totalMins) * 100));
      const color = ev.direction === 'BULLISH' || ev.direction === 'LONG' ? 'var(--k-green)' : 'var(--k-red)';
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

  return (
    <>
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

      <div 
        className="sim-dock" 
        data-open={barOpen}
        style={{
          height: isExpanded
            ? (viewMode === 'maximized' ? '80vh' : viewMode === 'half' ? '50vh' : dockHeight ? `${dockHeight}px` : 'auto')
            : 'auto',
          maxHeight: viewMode === 'maximized' ? '80vh' : viewMode === 'half' ? '50vh' : 'none',
          transition: isResizing ? 'none' : 'height 0.25s ease, max-height 0.25s ease',
        }}
      >
        <div 
          className="sim-dock-resizer"
          data-active={isResizing}
          onMouseDown={handleResizeStart}
          title="Drag up/down to resize Market Replay Dock height"
        />

        {/* Row 1: Shell Bar */}
        <div className="sim-shell-bar">
          <span className="sim-shell-title">⚡ MARKET REPLAY</span>
          <span className="sim-shell-state" data-state={sim.status.state}>
            {sim.status.state.toUpperCase()}
          </span>
          <span className="sim-shell-clock">
            {sim.status.current_time_iso || sim.startTime} IST
          </span>
          <span className="sim-shell-progress">{sim.status.progress_pct}%</span>
          
          <div className="sim-shell-controls">
            <button className="sim-win-btn" onClick={() => setIsExpanded(!isExpanded)}>
              {isExpanded ? '▼ DOCK' : '▲ DOCK'}
            </button>
            <button className="sim-win-btn" onClick={() => sim.setBarOpen(false)}>
              <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M5 18h14"/></svg>
            </button>
            <button className="sim-win-btn" onClick={() => { setIsExpanded(true); setViewMode(viewMode === 'half' ? 'docked' : 'half'); }}>
              <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8"><rect x="3" y="4" width="18" height="16" rx="2"/><path d="M12 4v16"/><path d="M3 4h9v16H3z" fill="currentColor" opacity=".14" stroke="none"/></svg>
            </button>
            <button className="sim-win-btn" onClick={() => { setIsExpanded(true); setViewMode(viewMode === 'maximized' ? 'docked' : 'maximized'); }}>
              <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8"><rect x="4" y="4" width="16" height="16" rx="2"/></svg>
            </button>
            <button className="sim-win-btn" onClick={() => {
              if (!document.fullscreenElement) document.documentElement.requestFullscreen().catch(()=>{});
              else document.exitFullscreen().catch(()=>{});
            }}>
              <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round"><path d="M8 3H3v5M16 3h5v5M21 16v5h-5M8 21H3v-5"/></svg>
            </button>
          </div>
        </div>

        {/* Row 2: Toolbar */}
        <div className="sim-toolbar">
          <div className="sim-toolbar-left">
            <button className="sim-btn-config" onClick={() => { setActiveDockTab('config'); setIsExpanded(true); }} disabled={simActive}>
              ⚙️ Config
            </button>
            
            <div ref={stratDropdownRef} className="sim-dropdown-container">
              <button className="sim-dropdown-btn" onClick={() => { setShowStratDropdown(!showStratDropdown); setShowLegsDropdown(false); }} disabled={simActive}>
                ⚡ STRATEGIES ({sim.selectedStrategies.includes('all') ? 'ALL' : sim.selectedStrategies.length}) ▼
              </button>
              {showStratDropdown && (
                <div className="sim-dropdown">
                  <div className="sim-dropdown-header">Select Strategies:</div>
                  <button className="sim-dropdown-item" data-active={sim.selectedStrategies.includes('all')} onClick={() => sim.toggleStrategy('all')}>
                    <span>{sim.selectedStrategies.includes('all') ? '☑' : '☐'}</span> ⚡ ALL STRATEGIES
                  </button>
                  {STRATEGY_OPTIONS.map(strat => {
                    const isSel = sim.selectedStrategies.includes(strat.id);
                    return (
                      <button key={strat.id} className="sim-dropdown-item" data-active={isSel} onClick={() => sim.toggleStrategy(strat.id)}>
                        <span>{isSel ? '☑' : '☐'}</span> {strat.label}
                      </button>
                    );
                  })}
                </div>
              )}
            </div>

            <div ref={legsDropdownRef} className="sim-dropdown-container">
              <button className="sim-dropdown-btn" onClick={() => { setShowLegsDropdown(!showLegsDropdown); setShowStratDropdown(false); }} disabled={simActive}>
                🎯 LEGS ({sim.selectedMoneyness.includes('ALL') ? 'ALL' : sim.selectedMoneyness.length}) ▼
              </button>
              {showLegsDropdown && (
                <div className="sim-dropdown">
                  <div className="sim-dropdown-header">Select Option Legs:</div>
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
                      <button key={leg.key} className="sim-dropdown-item" data-active={isSel} onClick={() => sim.toggleMoneyness(leg.key)}>
                        <span>{isSel ? '☑' : '☐'}</span> {leg.label}
                      </button>
                    );
                  })}
                </div>
              )}
            </div>

            <input type="date" className="sim-input" value={sim.date} onChange={e => sim.setDate(e.target.value)} disabled={simActive} />
            <input type="time" className="sim-input" value={sim.startTime} onChange={e => sim.setStartTime(e.target.value)} disabled={simActive} />
            <input type="time" className="sim-input" value={sim.endTime} onChange={e => sim.setEndTime(e.target.value)} disabled={simActive} />
          </div>

          <div className="sim-toolbar-center">
            <button className="sim-btn-transport" onClick={() => sim.jumpStart()} disabled={!simActive}>⏮</button>
            <button className="sim-btn-transport" onClick={() => sim.stepBars(-5)} disabled={!simActive}>◀◀</button>
            {sim.status.state === 'running' ? (
              <button className="sim-btn-transport" onClick={() => sim.pause()}>⏸</button>
            ) : sim.status.state === 'paused' ? (
              <button className="sim-btn-transport" onClick={() => sim.resume()}>⏵</button>
            ) : (
              <button className="sim-btn-transport" onClick={() => sim.start()}>⏵</button>
            )}
            <button className="sim-btn-transport" onClick={() => sim.stepBars(5)} disabled={!simActive}>▶▶</button>
            <button className="sim-btn-transport" onClick={() => sim.jumpEnd()} disabled={!simActive}>⏭</button>
            <button className="sim-btn-transport" onClick={() => sim.stop()} disabled={!simActive}>⏹</button>
          </div>

          <div className="sim-toolbar-right">
            {[1, 5, 10, 50, 100, 250, 500, 1000, 5000].map(s => (
              <button key={s} className="sim-speed-pill" data-active={sim.speed === s} onClick={() => sim.setSpeed(s)}>
                {s === 5000 ? '⚡ MAX' : `${s}×`}
              </button>
            ))}
          </div>
        </div>

        {/* Row 3: Stats Bar */}
        {simActive && (
          <div className="sim-stats-bar">
            <div className="sim-stats-timeline">
              <div className="sim-progress-track">
                {heatmapDots}
                <div className="sim-progress-fill" style={{ width: `${sim.status.progress_pct}%` }} />
              </div>
            </div>
            <div className="sim-stats-cells">
              <span className="sim-stat-cell">Signals: {sim.status.stats.signals_fired}</span>
              <span className="sim-stat-cell">Trades: {(sim.status.stats.trades || []).length}</span>
              <span className="sim-stat-cell">Win Rate: {sim.status.stats.wins + sim.status.stats.losses > 0 ? Math.round(sim.status.stats.wins / (sim.status.stats.wins + sim.status.stats.losses) * 100) : 0}%</span>
              <span className="sim-stat-cell" data-profit={(sim.status.stats.pnl || 0) >= 0}>
                P&L: ₹{(sim.status.stats.pnl || 0).toFixed(2)}
              </span>
            </div>
          </div>
        )}

        {/* Expandable Dock Panel */}
        <div className="sim-dock-panel" data-expanded={isExpanded}>
          <div className="sim-tab-strip">
            <button className="sim-tab-btn" data-active={activeDockTab === 'config'} onClick={() => setActiveDockTab('config')}>⚙ Configuration</button>
            <button className="sim-tab-btn" data-active={activeDockTab === 'signals'} onClick={() => setActiveDockTab('signals')}>⚡ Signals ({sim.status.stats.events.length})</button>
            <button className="sim-tab-btn" data-active={activeDockTab === 'trades'} onClick={() => setActiveDockTab('trades')}>💼 Trades ({(sim.status.stats.trades || []).length})</button>
            
            <div className="sim-tab-actions">
              {activeDockTab === 'signals' && sim.status.stats.events.length > 0 && (
                <button className="sim-export-btn" onClick={() => exportSignalsToCSV(sim.status.stats.events, sim.date)}>📥 Export</button>
              )}
              {activeDockTab === 'trades' && (sim.status.stats.trades || []).length > 0 && (
                <button className="sim-export-btn" onClick={() => exportTradesToCSV(sim.status.stats.trades || [], sim.date)}>📥 Export</button>
              )}
              <button className="sim-close-btn" onClick={() => setIsExpanded(false)}>✕</button>
            </div>
          </div>

          <div className="sim-tab-content">
            {activeDockTab === 'config' && (
              <div className="sim-config-grid">
                <div>
                  <div className="sim-config-header">⚡ ACTIVE REPLAY STRATEGIES</div>
                  <div className="sim-config-options">
                    <button className="sim-speed-pill" data-active={sim.selectedStrategies.includes('all')} onClick={() => sim.toggleStrategy('all')} disabled={simActive}>
                      ⚡ ALL STRATEGIES
                    </button>
                    {STRATEGY_OPTIONS.map(strat => (
                      <button key={strat.id} className="sim-speed-pill" data-active={sim.selectedStrategies.includes(strat.id)} onClick={() => sim.toggleStrategy(strat.id)} disabled={simActive}>
                        <span>{sim.selectedStrategies.includes(strat.id) ? '☑' : '☐'}</span> {strat.label}
                      </button>
                    ))}
                  </div>
                </div>
                <div>
                  <div className="sim-config-header">🎯 STRIKE MONEYNESS LEGS</div>
                  <div className="sim-config-options">
                    <button className="sim-speed-pill" data-active={sim.selectedMoneyness.includes('ALL')} onClick={() => sim.toggleMoneyness('ALL')} disabled={simActive}>
                      ✨ ALL LEGS
                    </button>
                    {[
                      { id: 'ATM', label: '🎯 ATM' },
                      { id: 'ITM1', label: '🟢 ITM1' },
                      { id: 'ITM2', label: '🟢 ITM2' },
                      { id: 'OTM1', label: '🔴 OTM1' },
                      { id: 'OTM2', label: '🔴 OTM2' },
                    ].map(leg => (
                      <button key={leg.id} className="sim-speed-pill" data-active={sim.selectedMoneyness.includes(leg.id)} onClick={() => sim.toggleMoneyness(leg.id)} disabled={simActive}>
                        <span>{sim.selectedMoneyness.includes(leg.id) ? '☑' : '☐'}</span> {leg.label}
                      </button>
                    ))}
                  </div>
                  <div className="sim-lots-selector">
                    <span>Lots:</span>
                    {[1, 2, 5, 10, 25, 50].map(l => (
                      <button key={l} className="sim-speed-pill" data-active={sim.lots === l} onClick={() => sim.setLots(l)} disabled={simActive}>
                        {l}L
                      </button>
                    ))}
                  </div>
                </div>
              </div>
            )}

            {activeDockTab === 'signals' && (
              sim.status.stats.events.length === 0 ? (
                <div className="sim-empty-state">Replay stepping through bars... No signals triggered yet.</div>
              ) : (
                <div className="sim-signals-grid">
                  <div className="sim-signals-header">
                    <div>TIME</div>
                    <div>STRATEGY</div>
                    <div>INSTRUMENT</div>
                    <div>DIR</div>
                    <div>ENTRY</div>
                    <div>SL</div>
                    <div>TP</div>
                  </div>
                  {sim.status.stats.events.slice().reverse().map((ev, i) => (
                    <div key={i} className="sim-signal-row" data-direction={ev.direction}>
                      <div className="sim-signal-time">{ev.time_iso}</div>
                      <div className="sim-signal-strat">[{ev.strategy.toUpperCase()}]</div>
                      <div className="sim-signal-inst">{ev.instrument}</div>
                      <div className="sim-signal-dir" data-bull={ev.direction === 'BULLISH' || ev.direction === 'LONG'}>{ev.direction}</div>
                      <div className="sim-signal-price">₹{ev.entry}</div>
                      <div className="sim-signal-sl">₹{ev.stop}</div>
                      <div className="sim-signal-tp">₹{ev.target}</div>
                    </div>
                  ))}
                </div>
              )
            )}

            {activeDockTab === 'trades' && (
              !(sim.status.stats.trades && sim.status.stats.trades.length > 0) ? (
                <div className="sim-empty-state">No trades executed yet. Strong signals will enter trades automatically.</div>
              ) : (
                <table className="sim-trade-table">
                  <thead>
                    <tr>
                      <th className="sim-table-th">ID</th>
                      <th className="sim-table-th">Time</th>
                      <th className="sim-table-th">Strategy</th>
                      <th className="sim-table-th">Contract</th>
                      <th className="sim-table-th">Lots (Qty)</th>
                      <th className="sim-table-th">Entry ₹</th>
                      <th className="sim-table-th">Exit ₹</th>
                      <th className="sim-table-th">Status</th>
                      <th className="sim-table-th">Realized P&L</th>
                    </tr>
                  </thead>
                  <tbody>
                    {sim.status.stats.trades.slice().reverse().map((tr, i) => {
                      const isWin = tr.status === 'WIN';
                      return (
                        <tr key={i} className="sim-table-tr">
                          <td className="sim-table-td id-cell">{tr.trade_id}</td>
                          <td className="sim-table-td">{tr.entry_time_iso} → {tr.exit_time_iso}</td>
                          <td className="sim-table-td">[{tr.strategy.toUpperCase()}]</td>
                          <td className="sim-table-td">{tr.symbol}</td>
                          <td className="sim-table-td">{tr.lots}L ({tr.quantity}Q)</td>
                          <td className="sim-table-td">₹{tr.entry_price}</td>
                          <td className="sim-table-td">{tr.exit_price ? `₹${tr.exit_price}` : '--'}</td>
                          <td className="sim-table-td">
                            <span className="sim-status-chip" data-win={isWin}>{tr.status}</span>
                          </td>
                          <td className="sim-table-td pnl-cell" data-profit={tr.pnl_usd >= 0}>
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
    >
      <span className="kw-dock-chip-icon">
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
    <span className="sim-footer-badge">
      <span className="sim-footer-badge-dot" />
      REPLAYING
    </span>
  );
}
