import React, { useEffect, useMemo, useRef, useState } from 'react';
import { createPortal } from 'react-dom';
import { useSimulation, useSimulationStore, useSimBarOpen, useSimActive, SimSignalEvent, SimTradeEvent } from '../../hooks/useSimulation';
import { k } from '../../styles/kiteUI';
import './SimulationBar.css';

const DOCK_HEIGHT_KEY = 'sterling:replay-dock:height';

function DragDots() {
  return (
    <span aria-hidden="true" style={{ width: 10, display: 'grid', gridTemplateColumns: 'repeat(2,3px)', gap: 2, color: '#c2c2c2', flexShrink: 0 }}>
      {Array.from({ length: 6 }).map((_, index) => <span key={index} style={{ width: 2.5, height: 2.5, borderRadius: '50%', background: 'currentColor' }} />)}
    </span>
  );
}

function ControlIcon({ kind }: { kind: 'minimize' | 'half' | 'maximize' | 'fullscreen' | 'restore' }) {
  if (kind === 'minimize') return <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M5 18h14"/></svg>;
  if (kind === 'half') return <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8"><rect x="3" y="4" width="18" height="16" rx="2"/><path d="M12 4v16"/><path d="M3 4h9v16H3z" fill="currentColor" opacity=".14" stroke="none"/></svg>;
  if (kind === 'maximize') return <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8"><rect x="4" y="4" width="16" height="16" rx="2"/></svg>;
  if (kind === 'restore') return <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8"><rect x="5" y="8" width="12" height="11" rx="1.5"/><path d="M8 8V5h11v11h-2"/></svg>;
  return <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round"><path d="M8 3H3v5M16 3h5v5M21 16v5h-5M8 21H3v-5"/></svg>;
}

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
  const headers = [
    'Trade ID', 'Entry Time', 'Exit Time', 'Strategy', 'Symbol', 'Underlying',
    'Direction', 'Option Type', 'Strike', 'Lots', 'Quantity',
    'Entry Fill', 'Raw Entry', 'Exit Fill', 'Raw Exit', 'Slippage Drag (INR)',
    'Status', 'PnL (INR)', 'PnL (%)', 'Duration (Mins)'
  ];
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
    tr.raw_entry ?? tr.entry_price,
    tr.exit_price || '',
    tr.raw_exit ?? (tr.exit_price || ''),
    tr.slippage ? tr.slippage.toFixed(2) : '0.00',
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
  const [activeDockTab, setActiveDockTab] = useState<'config' | 'signals' | 'trades' | 'split'>('config');
  const [viewMode, setViewMode] = useState<'half' | 'full' | 'maximized' | 'fullscreen'>('half');
  const [dockHeight, setDockHeight] = useState<number>(() => {
    try {
      const saved = localStorage.getItem(DOCK_HEIGHT_KEY);
      const parsed = saved ? parseInt(saved, 10) : 320;
      return Number.isFinite(parsed) && parsed >= 160 ? parsed : 320;
    } catch {
      return 320;
    }
  });
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
        if (viewMode !== 'half') {
          e.preventDefault();
          setViewMode('half');
        } else {
          sim.setBarOpen(false);
        }
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
  }, [barOpen, sim, viewMode]);

  const handleResizeStart = (e: React.MouseEvent) => {
    e.preventDefault();
    setIsResizing(true);
    const startY = e.clientY;
    const startHeight = dockHeight || 320;

    const handleMouseMove = (moveEvent: MouseEvent) => {
      const deltaY = startY - moveEvent.clientY;
      const newHeight = Math.max(160, Math.min(window.innerHeight - 80, startHeight + deltaY));
      setDockHeight(newHeight);
      setIsExpanded(true);
      try {
        localStorage.setItem(DOCK_HEIGHT_KEY, String(newHeight));
      } catch {}
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

  const renderSignalsTable = () => (
    sim.status.stats.events.length === 0 ? (
      <div className="sim-empty-state">Replay stepping through bars... No signals triggered yet.</div>
    ) : (
      <div className="sim-signals-grid">
        <div className="sim-signals-header">
          <div>TIME</div>
          <div>STRATEGY</div>
          <div>CONTRACT / UNDERLYING</div>
          <div>DIR</div>
          <div>ENTRY</div>
          <div>SL</div>
          <div>TP</div>
        </div>
        {sim.status.stats.events.slice().reverse().map((ev, i) => (
          <div key={i} className="sim-signal-row" data-direction={ev.direction}>
            <div className="sim-signal-time">{ev.time_iso}</div>
            <div className="sim-signal-strat">[{ev.strategy.toUpperCase()}]</div>
            <div className="sim-signal-inst">
              {ev.contract ? (
                <div style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}>
                  <span style={{ fontWeight: 600 }}>{ev.contract}</span>
                  {ev.spot != null && (
                    <span style={{ fontSize: 9, opacity: 0.65, padding: '1px 4px', borderRadius: 3, background: 'var(--k-border)' }}>
                      Spot ₹{ev.spot}
                    </span>
                  )}
                </div>
              ) : (
                ev.instrument
              )}
            </div>
            <div className="sim-signal-dir" data-bull={ev.direction === 'BULLISH' || ev.direction === 'LONG'}>{ev.direction}</div>
            <div className="sim-signal-price">₹{ev.entry}</div>
            <div className="sim-signal-sl">₹{ev.stop}</div>
            <div className="sim-signal-tp">₹{ev.target}</div>
          </div>
        ))}
      </div>
    )
  );

  const renderTradesTable = () => (
    !(sim.status.stats.trades && sim.status.stats.trades.length > 0) ? (
      <div className="sim-empty-state">No trades executed yet. Strong signals will enter trades automatically.</div>
    ) : (
      <table className="sim-trade-table">
        <thead>
          <tr>
            <th className="sim-table-th">ID</th>
            <th className="sim-table-th">Entry Time</th>
            <th className="sim-table-th">Exit Time</th>
            <th className="sim-table-th">Strategy</th>
            <th className="sim-table-th">Contract</th>
            <th className="sim-table-th">Lots (Qty)</th>
            <th className="sim-table-th">Entry ₹</th>
            <th className="sim-table-th">Exit ₹</th>
            <th className="sim-table-th">Slippage</th>
            <th className="sim-table-th">Status</th>
            <th className="sim-table-th">Realized P&L</th>
          </tr>
        </thead>
        <tbody>
          {sim.status.stats.trades.slice().reverse().map((tr, i) => {
            const isWin = tr.status === 'WIN';
            const entryTime = tr.entry_time_iso || (tr.timestamp_ms ? new Date(tr.timestamp_ms).toLocaleTimeString('en-IN', { hour12: false }) : '--');
            const exitTime = tr.exit_time_iso || (tr.status === 'OPEN' ? 'OPEN' : '--');
            return (
              <tr key={i} className="sim-table-tr">
                <td className="sim-table-td id-cell">{tr.trade_id}</td>
                <td className="sim-table-td time-cell">{entryTime}</td>
                <td className="sim-table-td time-cell">{exitTime}</td>
                <td className="sim-table-td">[{tr.strategy.toUpperCase()}]</td>
                <td className="sim-table-td">{tr.symbol}</td>
                <td className="sim-table-td">{tr.lots}L ({tr.quantity}Q)</td>
                <td className="sim-table-td">
                  <div>₹{tr.entry_price}</div>
                  {tr.raw_entry != null && tr.raw_entry !== tr.entry_price && (
                    <div style={{ fontSize: 9.5, color: 'var(--k-dim)', opacity: 0.8 }} title={`Theoretical Signal: ₹${tr.raw_entry}`}>
                      raw ₹{tr.raw_entry}
                    </div>
                  )}
                </td>
                <td className="sim-table-td">
                  {tr.exit_price ? (
                    <>
                      <div>₹{tr.exit_price}</div>
                      {tr.raw_exit != null && tr.raw_exit !== tr.exit_price && (
                        <div style={{ fontSize: 9.5, color: 'var(--k-dim)', opacity: 0.8 }} title={`Theoretical Target/SL: ₹${tr.raw_exit}`}>
                          raw ₹{tr.raw_exit}
                        </div>
                      )}
                    </>
                  ) : '--'}
                </td>
                <td className="sim-table-td">
                  {tr.slippage && tr.slippage > 0 ? (
                    <span style={{ fontSize: 10, color: 'var(--k-red-brick)', fontWeight: 650 }} title="Slippage & bid-ask spread friction deducted from P&L">
                      -₹{tr.slippage.toFixed(2)}
                    </span>
                  ) : (
                    <span style={{ fontSize: 10, color: 'var(--k-dim)' }}>₹0.00</span>
                  )}
                </td>
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
  );

  const dockBody = (
    <div
      className="sim-dock-inner"
      style={{
        display: 'flex',
        flexDirection: 'column',
        height: '100%',
        minHeight: 0,
        overflow: 'hidden',
        background: 'var(--k-bg)',
      }}
    >
      {(viewMode === 'half' || viewMode === 'full') && (
        <div 
          className="sim-dock-resizer"
          data-active={isResizing}
          onMouseDown={handleResizeStart}
          title="Drag up/down to resize Market Replay Dock height"
        />
      )}

      {/* Row 1: Shell Bar (Standard Sterling Dock Header matching PCR / workspace dock) */}
      <div 
        className="sim-shell-bar"
        onDoubleClick={() => {
          if (viewMode !== 'half') setViewMode('half');
          else {
            setIsExpanded(true);
            setViewMode('maximized');
          }
        }}
        title={viewMode !== 'half' ? 'Double-click to restore dock' : 'Double-click to maximize dock'}
      >
        <DragDots />
        <span style={{ color: 'var(--k-brand)', display: 'inline-flex' }}>⚡</span>
        <span className="sim-shell-title">Market Replay</span>
        <span style={{ fontSize: 9, color: 'var(--k-faint)', whiteSpace: 'nowrap' }}>
          {viewMode === 'full' ? 'Bottom dock' : viewMode === 'maximized' ? 'Maximized' : viewMode === 'fullscreen' ? 'Full screen' : 'Dashboard dock'}
        </span>

        <span className="sim-shell-state" data-state={sim.status.state}>
          {sim.status.state.toUpperCase()}
        </span>
        <span className="sim-shell-clock">
          [{sim.status.current_time_iso || sim.startTime} IST · {sim.speed}× SPEED]
        </span>
        <span className="sim-shell-progress">{sim.status.progress_pct}%</span>
        
        <div className="sim-shell-controls">
          {viewMode !== 'half' && (
            <button 
              type="button"
              className="kw-pane-control"
              aria-label="Restore Market Replay"
              title="Restore to dashboard dock"
              onClick={(e) => {
                e.stopPropagation();
                setViewMode('half');
              }}
            >
              <ControlIcon kind="restore" />
            </button>
          )}

          <button 
            type="button"
            className="kw-pane-control" 
            style={{ width: 'auto', padding: '0 6px', fontSize: 10, fontWeight: 700, color: isExpanded ? 'var(--k-brand)' : 'var(--k-dim)' }}
            onClick={(e) => {
              e.stopPropagation();
              setIsExpanded(!isExpanded);
            }}
            title={isExpanded ? "Collapse replay tabs" : "Expand replay tabs"}
            aria-label={isExpanded ? "Collapse replay tabs" : "Expand replay tabs"}
          >
            {isExpanded ? '▼ TABLE' : '▲ TABLE'}
          </button>

          <button 
            type="button"
            className="kw-pane-control sim-minimize-btn" 
            onClick={(e) => {
              e.stopPropagation();
              useSimulationStore.getState().setBarOpen(false);
            }}
            title="Minimize Market Replay Dock"
            aria-label="Minimize Replay Dock"
          >
            <ControlIcon kind="minimize" />
          </button>

          <button 
            type="button"
            className="kw-pane-control" 
            aria-label="Half screen Market Replay"
            aria-pressed={viewMode === 'half'}
            onClick={(e) => {
              e.stopPropagation();
              setIsExpanded(true);
              setViewMode(viewMode === 'half' ? 'full' : 'half');
            }}
            title={viewMode === 'half' ? "Full width bottom dock" : "Align to dashboard section (Split)"}
          >
            <ControlIcon kind="half" />
          </button>

          <button 
            type="button"
            className="kw-pane-control" 
            aria-label="Maximize Market Replay"
            aria-pressed={viewMode === 'maximized'}
            onClick={(e) => {
              e.stopPropagation();
              setIsExpanded(true);
              setViewMode(viewMode === 'maximized' ? 'half' : 'maximized');
            }}
            title="Maximize Market Replay"
          >
            <ControlIcon kind="maximize" />
          </button>

          <button 
            type="button"
            className="kw-pane-control" 
            aria-label="Full screen Market Replay"
            aria-pressed={viewMode === 'fullscreen'}
            onClick={(e) => {
              e.stopPropagation();
              setIsExpanded(true);
              setViewMode(viewMode === 'fullscreen' ? 'half' : 'fullscreen');
            }}
            title="Full screen Market Replay"
          >
            <ControlIcon kind="fullscreen" />
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
            <button className="sim-tab-btn" data-active={activeDockTab === 'split'} onClick={() => setActiveDockTab('split')}>🔀 Split View</button>
            
            <div className="sim-tab-actions">
              {activeDockTab === 'signals' && sim.status.stats.events.length > 0 && (
                <button className="sim-export-btn" onClick={() => exportSignalsToCSV(sim.status.stats.events, sim.date)}>📥 Export Signals</button>
              )}
              {activeDockTab === 'trades' && (sim.status.stats.trades || []).length > 0 && (
                <button className="sim-export-btn" onClick={() => exportTradesToCSV(sim.status.stats.trades || [], sim.date)}>📥 Export Trades</button>
              )}
              {activeDockTab === 'split' && (
                <div style={{ display: 'inline-flex', alignItems: 'center', gap: 4 }}>
                  {sim.status.stats.events.length > 0 && (
                    <button className="sim-export-btn" onClick={() => exportSignalsToCSV(sim.status.stats.events, sim.date)}>📥 Signals</button>
                  )}
                  {(sim.status.stats.trades || []).length > 0 && (
                    <button className="sim-export-btn" onClick={() => exportTradesToCSV(sim.status.stats.trades || [], sim.date)}>📥 Trades</button>
                  )}
                </div>
              )}
              <button className="sim-close-btn" onClick={() => setIsExpanded(false)} title="Collapse dock tabs">✕</button>
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

                <div>
                  <div className="sim-config-header">⚡ EXECUTION FRICTION & REALISM</div>
                  <div className="sim-config-options">
                    <button
                      className="sim-speed-pill"
                      data-active={sim.frictionMode === 'realistic'}
                      onClick={() => sim.setFrictionMode('realistic')}
                      disabled={simActive}
                      title="Simulates real-world spread (0.5% index, 1.5% stock) and execution slippage"
                    >
                      ⚡ Realistic (Spread + Slippage)
                    </button>
                    <button
                      className="sim-speed-pill"
                      data-active={sim.frictionMode === 'ideal'}
                      onClick={() => sim.setFrictionMode('ideal')}
                      disabled={simActive}
                      title="Ideal theoretical execution at exact signal price with zero friction"
                    >
                      🎯 Ideal (Zero Friction)
                    </button>
                  </div>
                  <div style={{ fontSize: 10, color: 'var(--k-dim)', marginTop: 6, lineHeight: 1.4 }}>
                    {sim.frictionMode === 'realistic'
                      ? 'Realistic mode simulates buying at Ask and selling at Bid with exchange tick friction.'
                      : 'Ideal mode executes directly at theoretical signal price without market friction.'}
                  </div>
                </div>
              </div>
            )}

            {activeDockTab === 'signals' && renderSignalsTable()}

            {activeDockTab === 'trades' && renderTradesTable()}

            {activeDockTab === 'split' && (
              <div className="sim-split-container">
                <div className="sim-split-col">
                  <div className="sim-split-col-head">
                    <span>⚡ Signals Feed ({sim.status.stats.events.length})</span>
                    {sim.status.stats.events.length > 0 && (
                      <button className="sim-export-btn" onClick={() => exportSignalsToCSV(sim.status.stats.events, sim.date)}>📥 Export</button>
                    )}
                  </div>
                  <div className="sim-split-col-body">
                    {renderSignalsTable()}
                  </div>
                </div>
                <div className="sim-split-col">
                  <div className="sim-split-col-head">
                    <span>💼 Executed Trades ({(sim.status.stats.trades || []).length})</span>
                    {(sim.status.stats.trades || []).length > 0 && (
                      <button className="sim-export-btn" onClick={() => exportTradesToCSV(sim.status.stats.trades || [], sim.date)}>📥 Export</button>
                    )}
                  </div>
                  <div className="sim-split-col-body">
                    {renderTradesTable()}
                  </div>
                </div>
              </div>
            )}
          </div>
        </div>
      </div>
    );

  if (!barOpen) {
    return null;
  }

  if (viewMode === 'fullscreen') {
    return (
      <>
        {createPortal(
          <div
            style={{
              position: 'fixed',
              inset: 0,
              zIndex: 12000,
              padding: 8,
              background: '#efefef',
              fontFamily: k.fontFamily,
            }}
          >
            <section
              className="sim-dock kw-pane"
              data-open="true"
              data-mode="fullscreen"
              style={{
                height: '100%',
                minWidth: 0,
                minHeight: 0,
                display: 'flex',
                flexDirection: 'column',
                overflow: 'hidden',
                background: 'var(--k-bg)',
                border: '1px solid #e4e4e4',
                boxShadow: '0 10px 36px rgba(0,0,0,.09)',
              }}
            >
              {dockBody}
            </section>
          </div>,
          document.body
        )}
        {toastSignal && (
          <div className="sim-toast-popup" data-direction={toastSignal.direction}>
            <span className="sim-toast-badge">SIGNAL FIRED</span>
            <span>{toastSignal.time_iso}</span>
            <strong>[{toastSignal.strategy.toUpperCase()}]</strong>
            <span>{toastSignal.contract || toastSignal.instrument}</span>
            <span>₹{toastSignal.entry}</span>
          </div>
        )}
      </>
    );
  }

  const containerStyle: React.CSSProperties = viewMode === 'maximized'
    ? {
        position: 'fixed',
        top: 0,
        left: 0,
        right: 0,
        bottom: 36,
        zIndex: 145,
        height: 'calc(100vh - 36px)',
        overflow: 'hidden',
        background: 'var(--k-bg)',
        borderTop: '1px solid var(--k-border-strong-4)',
        boxShadow: '0 10px 36px rgba(0,0,0,.09)',
      }
    : viewMode === 'full'
    ? {
        position: 'fixed',
        bottom: 36,
        left: 0,
        right: 0,
        zIndex: 140,
        height: isExpanded ? `${dockHeight}px` : '32px',
        overflow: 'hidden',
        background: 'var(--k-bg)',
        borderTop: '1px solid var(--k-border-strong-4)',
        boxShadow: '0 -8px 24px rgba(0, 0, 0, 0.14)',
      }
    : {
        // viewMode === 'half' (Default dashboard-aligned view)
        width: '100%',
        flexShrink: 0,
        height: isExpanded ? `${dockHeight}px` : '32px',
        borderTop: '1px solid var(--k-border-strong-4)',
      };

  return (
    <>
      <section
        className="sim-dock kw-pane"
        data-open="true"
        data-mode={viewMode}
        style={containerStyle}
      >
        {dockBody}
      </section>

      {toastSignal && (
        <div className="sim-toast-popup" data-direction={toastSignal.direction}>
          <span className="sim-toast-badge">SIGNAL FIRED</span>
          <span>{toastSignal.time_iso}</span>
          <strong>[{toastSignal.strategy.toUpperCase()}]</strong>
          <span>{toastSignal.contract || toastSignal.instrument}</span>
          <span>₹{toastSignal.entry}</span>
        </div>
      )}
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
      data-active={barOpen} 
      title={barOpen ? "Minimize Market Replay Dock" : "Open Market Replay Dock"}
      aria-label={barOpen ? "Minimize Market Replay Dock" : "Open Market Replay Dock"}
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
