import React, { useEffect, useMemo } from 'react';
import { useSimulation, useSimulationStore, useSimBarOpen, useSimActive } from '../../hooks/useSimulation';
import { k } from '../../styles/kiteUI';
import './SimulationBar.css';

// Utility to tint colors (simplified stub based on kiteUI tint)
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

export function SimulationBar() {
  const sim = useSimulation();
  const barOpen = useSimBarOpen();
  const simActive = useSimActive();

  // Keyboard shortcuts
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (!barOpen) return;
      if (e.target instanceof HTMLInputElement || e.target instanceof HTMLTextAreaElement) return;

      if (e.key === ' ') {
        e.preventDefault();
        if (sim.status.state === 'running') sim.pause();
        else if (sim.status.state === 'paused') sim.resume();
        else if (sim.status.state === 'idle') sim.start();
      } else if (e.key === 'Escape') {
        sim.setBarOpen(false);
      } else if (e.key === '=' || e.key === '+') {
        const speeds = [1, 2, 5, 10, 15, 20, 50];
        const idx = speeds.indexOf(sim.speed);
        if (idx < speeds.length - 1) sim.setSpeed(speeds[idx + 1]);
      } else if (e.key === '-' || e.key === '_') {
        const speeds = [1, 2, 5, 10, 15, 20, 50];
        const idx = speeds.indexOf(sim.speed);
        if (idx > 0) sim.setSpeed(speeds[idx - 1]);
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [barOpen, sim]);

  // Keyboard shortcuts
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (!barOpen) return;
      if (e.target instanceof HTMLInputElement || e.target instanceof HTMLTextAreaElement) return;

      if (e.key === ' ') {
        e.preventDefault();
        if (sim.status.state === 'running') sim.pause();
        else if (sim.status.state === 'paused') sim.resume();
        else if (sim.status.state === 'idle') sim.start();
      } else if (e.key === 'Escape') {
        sim.setBarOpen(false);
      } else if (e.key === '=' || e.key === '+') {
        const speeds = [1, 2, 5, 10, 15, 20, 50];
        const idx = speeds.indexOf(sim.speed);
        if (idx < speeds.length - 1) sim.setSpeed(speeds[idx + 1]);
      } else if (e.key === '-' || e.key === '_') {
        const speeds = [1, 2, 5, 10, 15, 20, 50];
        const idx = speeds.indexOf(sim.speed);
        if (idx > 0) sim.setSpeed(speeds[idx - 1]);
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [barOpen, sim]);

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
          title={`${formatTime(ev.time_iso, 5)} - ${ev.strategy} ${ev.direction}`}
        />
      );
    });
  }, [sim.status.stats.events, sim.status.config]);

  if (!barOpen) return null;

  return (
    <div className="sim-bar-wrapper" data-open={barOpen}>
      <div className="sim-bar">
        {/* Left: Input group */}
        <div className="sim-date-group">
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
          <button className="sim-btn" title="Jump to start" disabled={simActive}>⏮</button>
          <button className="sim-btn" title="Back 5 bars" disabled={!simActive}>◀◀</button>
          
          {sim.status.state === 'running' ? (
            <button className="sim-btn sim-btn--play" title="Pause (Space)" onClick={sim.pause}>⏸</button>
          ) : sim.status.state === 'paused' ? (
            <button className="sim-btn sim-btn--play" title="Resume (Space)" onClick={sim.resume}>⏵</button>
          ) : (
            <button className="sim-btn sim-btn--play" title="Start Replay (Space)" onClick={sim.start}>⏵</button>
          )}
          
          <button className="sim-btn" title="Forward 5 bars" disabled={!simActive}>▶▶</button>
          <button className="sim-btn" title="Jump to end" disabled={simActive}>⏭</button>
          <button className="sim-btn sim-btn--stop" title="Stop & View Summary" onClick={sim.stop} disabled={!simActive}>⏹</button>
        </div>

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
          {[1, 2, 5, 10, 15, 20, 50].map(s => (
            <button 
              key={s} 
              className="sim-speed-pill" 
              data-active={sim.speed === s}
              onClick={() => sim.setSpeed(s)}
            >
              {s}×
            </button>
          ))}
        </div>

        {/* Stats */}
        <div className="sim-stats">
          <div className="sim-stat">
            <span className="sim-stat-label">Sig</span>
            <span className="sim-stat-value" data-pulse={sim.status.stats.signals_fired > 0}>{sim.status.stats.signals_fired}</span>
          </div>
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
  );
}

export function SimulationFooterButton() {
  const barOpen = useSimBarOpen();
  const setBarOpen = useSimulationStore(s => s.setBarOpen);
  
  return (
    <button className="sim-footer-btn" onClick={() => setBarOpen(!barOpen)}>
      <span style={{ fontSize: '11px' }}>▶</span>
      REPLAY
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
