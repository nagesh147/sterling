import { describe, it, expect, beforeEach, vi } from 'vitest';
import { act } from '@testing-library/react';
import { useSimulationStore } from '../useSimulation';

describe('useSimulationStore', () => {
  beforeEach(() => {
    // Reset store
    act(() => {
      useSimulationStore.setState({
        barOpen: false,
        status: {
          state: 'idle',
          config: null,
          current_time_iso: '',
          progress_pct: 0,
          bars_played: 0,
          bars_total: 0,
          stats: { signals_fired: 0, trades_entered: 0, wins: 0, losses: 0, pnl: 0, events: [] },
          elapsed_real_s: 0,
        },
        date: '2026-08-28',
        startTime: '09:15:00',
        endTime: '15:30:00',
        speed: 5,
        showSummary: false,
      });
    });
  });

  it('initializes with default state', () => {
    const state = useSimulationStore.getState();
    expect(state.barOpen).toBe(false);
    expect(state.status.state).toBe('idle');
    expect(state.speed).toBe(5);
    expect(state.showSummary).toBe(false);
  });

  it('updates form inputs correctly', () => {
    act(() => {
      useSimulationStore.getState().setDate('2026-08-25');
      useSimulationStore.getState().setStartTime('10:00:00');
      useSimulationStore.getState().setEndTime('14:00:00');
      useSimulationStore.getState().setSpeed(10);
    });

    const state = useSimulationStore.getState();
    expect(state.date).toBe('2026-08-25');
    expect(state.startTime).toBe('10:00:00');
    expect(state.endTime).toBe('14:00:00');
    expect(state.speed).toBe(10);
  });

  it('toggles bar visibility', () => {
    act(() => {
      useSimulationStore.getState().setBarOpen(true);
    });
    expect(useSimulationStore.getState().barOpen).toBe(true);

    act(() => {
      useSimulationStore.getState().setBarOpen(false);
    });
    expect(useSimulationStore.getState().barOpen).toBe(false);
  });

  it('updates simulation status correctly', () => {
    const newStatus = {
      state: 'running' as const,
      config: {
        date: '2026-08-28',
        start_time: '09:15:00',
        end_time: '15:30:00',
        speed: 5,
        resolution: '5m',
        instruments: ['NIFTY'],
      },
      current_time_iso: '10:15:00',
      progress_pct: 25.5,
      bars_played: 12,
      bars_total: 75,
      stats: {
        signals_fired: 3,
        trades_entered: 2,
        wins: 2,
        losses: 0,
        pnl: 150.5,
        events: [],
      },
      elapsed_real_s: 10.2,
    };

    act(() => {
      useSimulationStore.getState().setStatus(newStatus);
    });

    const state = useSimulationStore.getState();
    expect(state.status.state).toBe('running');
    expect(state.status.progress_pct).toBe(25.5);
    expect(state.status.stats.signals_fired).toBe(3);
    expect(state.status.stats.pnl).toBe(150.5);
  });
});
