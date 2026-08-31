import React from 'react';
import { render, screen, fireEvent } from '@testing-library/react';
import { describe, it, expect, beforeEach, vi } from 'vitest';
import { SimulationBar, SimulationFooterButton } from '../SimulationBar';
import { useSimulationStore } from '../../../hooks/useSimulation';

// Mock fetch API
globalThis.fetch = vi.fn().mockImplementation(() =>
  Promise.resolve({
    ok: true,
    json: () =>
      Promise.resolve({
        state: 'idle',
        config: null,
        current_time_iso: '',
        progress_pct: 0,
        bars_played: 0,
        bars_total: 0,
        stats: { signals_fired: 0, trades_entered: 0, wins: 0, losses: 0, pnl: 0, events: [] },
        elapsed_real_s: 0,
        status_message: '',
        last_signal: null,
      }),
  })
);

describe('SimulationBar Component', () => {
  beforeEach(() => {
    useSimulationStore.setState({
      barOpen: true,
      status: {
        state: 'idle',
        config: null,
        current_time_iso: '',
        progress_pct: 0,
        bars_played: 0,
        bars_total: 0,
        stats: { signals_fired: 0, trades_entered: 0, wins: 0, losses: 0, pnl: 0, events: [] },
        elapsed_real_s: 0,
        status_message: '',
        last_signal: null,
      },
      date: '2026-08-28',
      startTime: '09:15:00',
      endTime: '15:30:00',
      speed: 5,
      showSummary: false,
    });
  });

  it('renders date, time inputs, and speed pills when open', () => {
    render(<SimulationBar />);

    // Date and time controls
    expect(screen.getByDisplayValue('2026-08-28')).toBeInTheDocument();
    expect(screen.getByDisplayValue('09:15:00')).toBeInTheDocument();
    expect(screen.getByDisplayValue('15:30:00')).toBeInTheDocument();

    // Speed pills
    expect(screen.getByText('1×')).toBeInTheDocument();
    expect(screen.getByText('5×')).toBeInTheDocument();
    expect(screen.getByText('50×')).toBeInTheDocument();
  });

  it('allows selecting speed', () => {
    render(<SimulationBar />);
    const speed100Btn = screen.getByText('100×');
    fireEvent.click(speed100Btn);

    expect(useSimulationStore.getState().speed).toBe(100);
  });

  it('renders footer replay button and toggles bar open state', () => {
    useSimulationStore.setState({ barOpen: false });
    render(<SimulationFooterButton />);

    const replayBtn = screen.getByRole('button', { name: /REPLAY/i });
    expect(replayBtn).toBeInTheDocument();

    fireEvent.click(replayBtn);
    expect(useSimulationStore.getState().barOpen).toBe(true);
  });
});
