import React from 'react';
import { render, screen, fireEvent, act } from '@testing-library/react';
import { describe, it, expect, beforeEach, vi } from 'vitest';
import { SimulationBar, SimulationFooterButton } from '../SimulationBar';
import { useSimulationStore } from '../../../hooks/useSimulation';

vi.mock('@tanstack/react-query', () => ({
  useQueryClient: () => ({
    invalidateQueries: vi.fn(),
  }),
}));

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
    (globalThis.fetch as any).mockImplementation(() =>
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

  it('renders date, time inputs, and speed pills when open', async () => {
    await act(async () => {
      render(<SimulationBar />);
    });

    // Date and time controls
    expect(screen.getByDisplayValue('2026-08-28')).toBeInTheDocument();
    expect(screen.getByDisplayValue('09:15:00')).toBeInTheDocument();
    expect(screen.getByDisplayValue('15:30:00')).toBeInTheDocument();

    // Speed pills
    expect(screen.getByText('1×')).toBeInTheDocument();
    expect(screen.getByText('5×')).toBeInTheDocument();
    expect(screen.getByText('50×')).toBeInTheDocument();
  });

  it('allows selecting speed', async () => {
    await act(async () => {
      render(<SimulationBar />);
    });
    const speed100Btn = screen.getByText('100×');
    await act(async () => {
      fireEvent.click(speed100Btn);
    });

    expect(useSimulationStore.getState().speed).toBe(100);
  });

  it('renders footer replay button and toggles bar open state', async () => {
    useSimulationStore.setState({ barOpen: false });
    await act(async () => {
      render(<SimulationFooterButton />);
    });

    const replayBtn = screen.getByRole('button', { name: /REPLAY/i });
    expect(replayBtn).toBeInTheDocument();

    await act(async () => {
      fireEvent.click(replayBtn);
    });
    expect(useSimulationStore.getState().barOpen).toBe(true);
  });

  it('minimizes the dock when the minimize button in header is clicked', async () => {
    useSimulationStore.setState({ barOpen: true });
    await act(async () => {
      render(<SimulationBar />);
    });

    const minimizeBtn = screen.getByRole('button', { name: /Minimize Replay Dock/i });
    expect(minimizeBtn).toBeInTheDocument();

    await act(async () => {
      fireEvent.click(minimizeBtn);
    });

    expect(useSimulationStore.getState().barOpen).toBe(false);
  });

  it('formats historical simulation date as explicit date rather than Today', async () => {
    const { sessionDayLabel, formatSessionDay } = await import('../board/boardTypes');
    // Simulated date on 04 Sept 2026
    const simKey = '2026-09-04';
    expect(formatSessionDay(simKey)).toBe('04 Sept 2026');

    // With a simulation timestamp on 04 Sept 2026 and real time being different
    const simNowMs = Date.parse('2026-09-04T15:28:15+05:30');
    const label = sessionDayLabel(simKey, simNowMs, true);
    expect(label).toBe('04 Sept 2026');
    expect(label).not.toBe('Today');

    // Standard non-historical mode labels the session today as Today
    expect(sessionDayLabel(simKey, simNowMs, false)).toBe('Today');
  });

  it('renders Entry Time and Exit Time headers and values in Trades tab', async () => {
    const runningStatus = {
      state: 'running' as const,
      config: {
        date: '2026-09-04',
        start_time: '09:15:00',
        end_time: '15:30:00',
        speed: 5,
        resolution: '5m',
        instruments: ['LT'],
      },
      current_time_iso: '09:30:00',
      progress_pct: 10,
      bars_played: 3,
      bars_total: 75,
      stats: {
        signals_fired: 1,
        trades_entered: 1,
        wins: 1,
        losses: 0,
        pnl: 525.0,
        events: [],
        trades: [
          {
            trade_id: 'TRD-1001',
            entry_time_iso: '09:15:00',
            exit_time_iso: '09:25:00',
            timestamp_ms: 1788503100000,
            strategy: 'supertrend',
            symbol: 'LT26SEP4000PE',
            underlying: 'LT',
            direction: 'BUY',
            opt_type: 'PE',
            strike: 4000,
            lots: 1,
            quantity: 175,
            entry_price: 66.75,
            exit_price: 69.75,
            stop_loss: 47.0,
            target_price: 68.05,
            status: 'WIN',
            pnl_usd: 525.0,
            pnl_pct: 4.49,
            duration_mins: 10,
          },
        ],
      },
      elapsed_real_s: 2.5,
      status_message: 'Running',
      last_signal: null,
    };

    (globalThis.fetch as any).mockImplementation(() =>
      Promise.resolve({
        ok: true,
        json: () => Promise.resolve(runningStatus),
      })
    );

    useSimulationStore.setState({
      barOpen: true,
      status: runningStatus,
    });

    await act(async () => {
      render(<SimulationBar />);
    });

    // Click on Trades tab
    const tradesTabBtn = screen.getByRole('button', { name: /Trades \(1\)/i });
    await act(async () => {
      fireEvent.click(tradesTabBtn);
    });

    // Verify Entry Time and Exit Time column headers are present
    expect(screen.getByText('Entry Time')).toBeInTheDocument();
    expect(screen.getByText('Exit Time')).toBeInTheDocument();

    // Verify trade timestamps are displayed
    expect(screen.getByText('09:15:00')).toBeInTheDocument();
    expect(screen.getByText('09:25:00')).toBeInTheDocument();
    expect(screen.getByText('TRD-1001')).toBeInTheDocument();
    expect(screen.getByText('LT26SEP4000PE')).toBeInTheDocument();
  });

  it('allows toggling between realistic and ideal friction modes in configuration', async () => {
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
      frictionMode: 'realistic',
    });

    await act(async () => {
      render(<SimulationBar />);
    });

    // Configuration tab is open by default
    const idealBtn = screen.getByRole('button', { name: /Ideal/i });
    expect(idealBtn).toBeInTheDocument();

    await act(async () => {
      fireEvent.click(idealBtn);
    });

    expect(useSimulationStore.getState().frictionMode).toBe('ideal');
  });

  it('supports window controls: half screen, maximize, restore, and fullscreen', async () => {
    useSimulationStore.setState({ barOpen: true });
    await act(async () => {
      render(<SimulationBar />);
    });

    const halfBtn = screen.getByRole('button', { name: /Half screen Market Replay/i });
    const maxBtn = screen.getByRole('button', { name: /Maximize Market Replay/i });
    const fullBtn = screen.getByRole('button', { name: /Full screen Market Replay/i });

    expect(halfBtn).toBeInTheDocument();
    expect(maxBtn).toBeInTheDocument();
    expect(fullBtn).toBeInTheDocument();

    // Half screen (dashboard-aligned) is default view
    expect(halfBtn).toHaveAttribute('aria-pressed', 'true');

    // Click Half screen toggles to full-width dock
    await act(async () => {
      fireEvent.click(halfBtn);
    });
    expect(halfBtn).toHaveAttribute('aria-pressed', 'false');
    expect(screen.getByRole('button', { name: /Restore Market Replay/i })).toBeInTheDocument();

    // Click Half screen again aligns back to dashboard section
    await act(async () => {
      fireEvent.click(halfBtn);
    });
    expect(halfBtn).toHaveAttribute('aria-pressed', 'true');

    // Click Maximize
    await act(async () => {
      fireEvent.click(maxBtn);
    });
    expect(maxBtn).toHaveAttribute('aria-pressed', 'true');

    // Click Restore restores back to default half view
    const restoreBtn = screen.getByRole('button', { name: /Restore Market Replay/i });
    await act(async () => {
      fireEvent.click(restoreBtn);
    });
    expect(maxBtn).toHaveAttribute('aria-pressed', 'false');
    expect(halfBtn).toHaveAttribute('aria-pressed', 'true');

    // Click Fullscreen
    await act(async () => {
      fireEvent.click(fullBtn);
    });
    expect(screen.getByRole('button', { name: /Full screen Market Replay/i })).toHaveAttribute('aria-pressed', 'true');
  });

  it('toggles maximize when double-clicking the shell bar title', async () => {
    useSimulationStore.setState({ barOpen: true });
    await act(async () => {
      render(<SimulationBar />);
    });

    const titleEl = screen.getByText('Market Replay');
    const shellBar = titleEl.closest('.sim-shell-bar')!;
    expect(shellBar).toBeInTheDocument();

    // Double-click to maximize
    await act(async () => {
      fireEvent.doubleClick(shellBar);
    });
    expect(screen.getByRole('button', { name: /Maximize Market Replay/i })).toHaveAttribute('aria-pressed', 'true');

    // Double-click again to restore
    await act(async () => {
      fireEvent.doubleClick(shellBar);
    });
    expect(screen.getByRole('button', { name: /Maximize Market Replay/i })).toHaveAttribute('aria-pressed', 'false');
  });

  it('handles Escape key to restore focus mode back to docked', async () => {
    useSimulationStore.setState({ barOpen: true });
    await act(async () => {
      render(<SimulationBar />);
    });

    const maxBtn = screen.getByRole('button', { name: /Maximize Market Replay/i });
    await act(async () => {
      fireEvent.click(maxBtn);
    });
    expect(maxBtn).toHaveAttribute('aria-pressed', 'true');

    // Press Escape
    await act(async () => {
      fireEvent.keyDown(window, { key: 'Escape' });
    });
    expect(screen.getByRole('button', { name: /Maximize Market Replay/i })).toHaveAttribute('aria-pressed', 'false');
  });

  it('switches to Split View tab and displays both signals and trades side-by-side', async () => {
    const statusWithData = {
      state: 'running' as const,
      config: {
        date: '2026-09-04',
        start_time: '09:15:00',
        end_time: '15:30:00',
        speed: 5,
        resolution: '5m',
        instruments: ['LT'],
      },
      current_time_iso: '09:30:00',
      progress_pct: 10,
      bars_played: 3,
      bars_total: 75,
      stats: {
        signals_fired: 1,
        trades_entered: 1,
        wins: 1,
        losses: 0,
        pnl: 525.0,
        events: [
          {
            time_iso: '09:15:00',
            strategy: 'supertrend',
            instrument: 'LT',
            direction: 'BEARISH' as const,
            strength: 'STRONG' as const,
            entry: 66.75,
            stop: 47.0,
            target: 68.05,
            contract: 'LT26SEP4000PE',
          },
        ],
        trades: [
          {
            trade_id: 'TRD-1001',
            entry_time_iso: '09:15:00',
            exit_time_iso: '09:25:00',
            timestamp_ms: 1788503100000,
            strategy: 'supertrend',
            symbol: 'LT26SEP4000PE',
            underlying: 'LT',
            direction: 'BUY',
            opt_type: 'PE',
            strike: 4000,
            lots: 1,
            quantity: 175,
            entry_price: 66.75,
            exit_price: 69.75,
            stop_loss: 47.0,
            target_price: 68.05,
            status: 'WIN',
            pnl_usd: 525.0,
            pnl_pct: 4.49,
            duration_mins: 10,
          },
        ],
      },
      elapsed_real_s: 2.5,
      status_message: 'Running',
      last_signal: null,
    };

    (globalThis.fetch as any).mockImplementation(() =>
      Promise.resolve({
        ok: true,
        json: () => Promise.resolve(statusWithData),
      })
    );

    useSimulationStore.setState({
      barOpen: true,
      status: statusWithData,
    });

    await act(async () => {
      render(<SimulationBar />);
    });

    const splitTabBtn = screen.getByRole('button', { name: /Split View/i });
    expect(splitTabBtn).toBeInTheDocument();

    await act(async () => {
      fireEvent.click(splitTabBtn);
    });

    // In split view, both Signals Feed and Executed Trades columns are rendered
    expect(screen.getByText(/Signals Feed \(1\)/i)).toBeInTheDocument();
    expect(screen.getByText(/Executed Trades \(1\)/i)).toBeInTheDocument();
    expect(screen.getAllByText('LT26SEP4000PE')).toHaveLength(2);
    expect(screen.getByText('TRD-1001')).toBeInTheDocument();
  });
});

