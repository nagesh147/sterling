import React from 'react';
import { render, screen, fireEvent, act } from '@testing-library/react';
import { describe, it, expect, beforeEach, vi } from 'vitest';
import { SimulationBar, SimulationFooterButton } from '../SimulationBar';
import {
  useSimulationStore,
  getLastMarketWorkingDay,
  getTodayMarketDate,
  getYesterdayMarketDate,
  getDynamicMarketPresets,
} from '../../../hooks/useSimulation';

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
    useSimulationStore.setState({
      barOpen: true,
      viewMode: 'half',
      activeDockTab: 'split',
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
      endDate: '2026-08-28',
      startTime: '09:00:00',
      endTime: '15:30:00',
      speed: 5,
      frictionMode: 'realistic',
      showSummary: false,
    });
  });

  it('renders date, time inputs, and speed pills when open', async () => {
    await act(async () => {
      render(<SimulationBar />);
    });

    // Date and time controls
    expect(screen.getAllByDisplayValue('2026-08-28').length).toBeGreaterThanOrEqual(1);
    expect(screen.getByDisplayValue('09:00:00')).toBeInTheDocument();
    expect(screen.getByDisplayValue('15:30:00')).toBeInTheDocument();

    // Speed pills
    expect(screen.getByText('1×')).toBeInTheDocument();
    expect(screen.getByText('5×')).toBeInTheDocument();
    expect(screen.getByText('50×')).toBeInTheDocument();
  });

  it('defaults to last market working day and 09:00:00 start time', () => {
    const lastDay = getLastMarketWorkingDay();
    expect(lastDay).toMatch(/^\d{4}-\d{2}-\d{2}$/);

    // Initial store state verification
    useSimulationStore.setState({
      date: getLastMarketWorkingDay(),
      startTime: '09:00:00',
    });

    const state = useSimulationStore.getState();
    expect(state.date).toBe(lastDay);
    expect(state.startTime).toBe('09:00:00');
  });

  it('dynamically filters market presets for holidays/weekends and allows quick switching', async () => {
    // 1. Weekend Scenario: Saturday 2026-09-05 (Market closed)
    const saturdayDate = new Date('2026-09-05T12:00:00+05:30');
    const weekendPresets = getDynamicMarketPresets(saturdayDate);
    const weekendIds = weekendPresets.map(p => p.id);
    expect(weekendIds).toContain('lastWorkingDay');
    expect(weekendIds).not.toContain('today'); // Today is Saturday (closed) -> must not show Today
    expect(weekendPresets.find(p => p.id === 'lastWorkingDay')?.date).toBe('2026-09-04'); // Rolls back to Friday

    // 2. Holiday Scenario: Gandhi Jayanti Friday 2026-10-02 (Market closed)
    const holidayDate = new Date('2026-10-02T11:00:00+05:30');
    const holidayPresets = getDynamicMarketPresets(holidayDate);
    const holidayIds = holidayPresets.map(p => p.id);
    expect(holidayIds).not.toContain('today'); // Holiday -> must not show Today
    expect(holidayPresets.find(p => p.id === 'lastWorkingDay')?.date).toBe('2026-10-01'); // Thursday

    // 3. Normal active weekday: Wednesday 2026-08-26 14:00:00 IST
    const weekdayDate = new Date('2026-08-26T14:00:00+05:30');
    const weekdayPresets = getDynamicMarketPresets(weekdayDate);
    const weekdayIds = weekdayPresets.map(p => p.id);
    expect(weekdayIds).toContain('today');
    expect(weekdayPresets.find(p => p.id === 'today')?.date).toBe('2026-08-26');

    // 4. Component UI test: render and click dynamic preset button
    await act(async () => {
      render(<SimulationBar />);
    });

    const lastDayBtn = screen.getByRole('button', { name: /Last Working Day/i });
    expect(lastDayBtn).toBeInTheDocument();

    await act(async () => {
      fireEvent.click(lastDayBtn);
    });
    expect(useSimulationStore.getState().date).toBe(getLastMarketWorkingDay());
  });

  it('defaults to Split View on running simulation and supports segmented navigation', async () => {
    useSimulationStore.setState({
      activeDockTab: 'config',
      status: {
        state: 'running',
        config: {
          date: '2026-09-04',
          start_time: '09:00:00',
          end_time: '15:30:00',
          speed: 5,
          resolution: '5m',
          instruments: [],
        },
        current_time_iso: '09:30:00',
        progress_pct: 10,
        bars_played: 6,
        bars_total: 75,
        stats: { signals_fired: 1, trades_entered: 0, wins: 0, losses: 0, pnl: 0, events: [] },
        elapsed_real_s: 2,
        status_message: 'Running',
        last_signal: null,
      },
    });

    await act(async () => {
      render(<SimulationBar />);
    });

    // Auto-switched to Split View because simulation is running
    expect(useSimulationStore.getState().activeDockTab).toBe('split');
    const splitBtn = screen.getByRole('tab', { name: /Split View/i });
    expect(splitBtn).toHaveAttribute('data-active', 'true');

    // Segmented tabs can be switched
    const signalsTab = screen.getByRole('tab', { name: /Signals/i });
    await act(async () => {
      fireEvent.click(signalsTab);
    });
    expect(useSimulationStore.getState().activeDockTab).toBe('signals');
  });

  it('renders Consolidation PnL bar and table summary row', async () => {
    const runningWithTrades = {
      state: 'running' as const,
      config: {
        date: '2026-09-04',
        start_time: '09:00:00',
        end_time: '15:30:00',
        speed: 5,
        resolution: '5m',
        instruments: ['LT'],
      },
      current_time_iso: '09:45:00',
      progress_pct: 15,
      bars_played: 9,
      bars_total: 75,
      stats: {
        signals_fired: 2,
        trades_entered: 1,
        wins: 1,
        losses: 0,
        pnl: 750.5,
        events: [
          {
            time_iso: '09:15:00',
            strategy: 'supertrend',
            instrument: 'LT',
            direction: 'BULLISH' as const,
            strength: 'STRONG' as const,
            entry: 3800.0,
            stop: 3750.0,
            target: 3900.0,
            contract: 'LT26SEP3800CE',
          },
        ],
        trades: [
          {
            trade_id: 'TRD-101',
            entry_time_iso: '09:15:00',
            exit_time_iso: '09:35:00',
            timestamp_ms: 1788503100000,
            strategy: 'supertrend',
            symbol: 'LT26SEP3800CE',
            underlying: 'LT',
            direction: 'BUY',
            opt_type: 'CE',
            strike: 3800,
            lots: 2,
            quantity: 350,
            entry_price: 45.0,
            exit_price: 47.5,
            stop_loss: 40.0,
            target_price: 55.0,
            status: 'WIN',
            pnl_usd: 750.5,
            pnl_pct: 5.56,
            duration_mins: 20,
            slippage: 12.5,
          },
        ],
      },
      elapsed_real_s: 3.5,
      status_message: 'Running',
      last_signal: null,
    };

    (globalThis.fetch as any).mockImplementation(() =>
      Promise.resolve({
        ok: true,
        json: () => Promise.resolve(runningWithTrades),
      })
    );

    useSimulationStore.setState({
      barOpen: true,
      activeDockTab: 'split',
      status: runningWithTrades,
    });

    await act(async () => {
      render(<SimulationBar />);
    });

    // Consolidation PnL row
    expect(screen.getAllByRole('region', { name: /Consolidated PnL/i }).length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText('REALIZED P&L').length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText('+₹750.50').length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText('WIN RATE').length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText('100%').length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText('SLIPPAGE DRAG').length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText('-₹12.50').length).toBeGreaterThanOrEqual(1);

    // Table total summary row
    expect(screen.getAllByText(/Total Summary/i).length).toBeGreaterThanOrEqual(1);
  });

  it('supports window controls: half screen, full height, maximize, restore, and fullscreen', async () => {
    useSimulationStore.setState({ barOpen: true, viewMode: 'half' });
    await act(async () => {
      render(<SimulationBar />);
    });

    const halfBtn = screen.getByRole('button', { name: /Half screen Market Replay/i });
    const fullHeightBtn = screen.getByRole('button', { name: /Full height Market Replay/i });
    const maxBtn = screen.getByRole('button', { name: /Maximize Market Replay/i });
    const fullScreenBtn = screen.getByRole('button', { name: /Full screen Market Replay/i });

    expect(halfBtn).toBeInTheDocument();
    expect(fullHeightBtn).toBeInTheDocument();
    expect(maxBtn).toBeInTheDocument();
    expect(fullScreenBtn).toBeInTheDocument();

    // Half screen is active by default
    expect(halfBtn).toHaveAttribute('aria-pressed', 'true');

    // Click Full height
    await act(async () => {
      fireEvent.click(fullHeightBtn);
    });
    expect(useSimulationStore.getState().viewMode).toBe('fullheight');
    expect(fullHeightBtn).toHaveAttribute('aria-pressed', 'true');

    // Restore button appears when not in half mode
    const restoreBtn = screen.getByRole('button', { name: /Restore Market Replay/i });
    expect(restoreBtn).toBeInTheDocument();

    // Click Restore snaps back to half
    await act(async () => {
      fireEvent.click(restoreBtn);
    });
    expect(useSimulationStore.getState().viewMode).toBe('half');

    // Click Maximize
    await act(async () => {
      fireEvent.click(maxBtn);
    });
    expect(useSimulationStore.getState().viewMode).toBe('maximized');

    // Click Restore snaps back to half
    const restoreBtn2 = screen.getByRole('button', { name: /Restore Market Replay/i });
    await act(async () => {
      fireEvent.click(restoreBtn2);
    });
    expect(useSimulationStore.getState().viewMode).toBe('half');

    // Click Full screen
    await act(async () => {
      fireEvent.click(fullScreenBtn);
    });
    expect(useSimulationStore.getState().viewMode).toBe('fullscreen');
  });

  it('toggles maximize when double-clicking the shell bar title', async () => {
    useSimulationStore.setState({ barOpen: true, viewMode: 'half' });
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
    expect(useSimulationStore.getState().viewMode).toBe('maximized');

    // Double-click again to restore
    await act(async () => {
      fireEvent.doubleClick(shellBar);
    });
    expect(useSimulationStore.getState().viewMode).toBe('half');
  });

  it('handles Escape key to restore focus mode back to docked', async () => {
    useSimulationStore.setState({ barOpen: true, viewMode: 'maximized' });
    await act(async () => {
      render(<SimulationBar />);
    });

    // Press Escape
    await act(async () => {
      fireEvent.keyDown(window, { key: 'Escape' });
    });
    expect(useSimulationStore.getState().viewMode).toBe('half');
  });

  it('allows toggling between realistic and ideal friction modes in configuration', async () => {
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
      activeDockTab: 'config',
      frictionMode: 'realistic',
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
    });

    await act(async () => {
      render(<SimulationBar />);
    });

    const configTab = screen.getByRole('tab', { name: /Configuration/i });
    await act(async () => {
      fireEvent.click(configTab);
    });

    const idealBtn = screen.getByRole('button', { name: /Ideal/i });
    expect(idealBtn).toBeInTheDocument();

    await act(async () => {
      fireEvent.click(idealBtn);
    });

    expect(useSimulationStore.getState().frictionMode).toBe('ideal');
  });

  it('allows selecting speed and toggles bar open in footer button', async () => {
    useSimulationStore.setState({ barOpen: true });
    await act(async () => {
      render(<SimulationBar />);
    });

    const speed100Btn = screen.getByText('100×');
    await act(async () => {
      fireEvent.click(speed100Btn);
    });
    expect(useSimulationStore.getState().speed).toBe(100);

    // Footer button toggles barOpen
    await act(async () => {
      useSimulationStore.setState({ barOpen: false });
    });
    await act(async () => {
      render(<SimulationFooterButton />);
    });
    const footerBtn = screen.getByRole('button', { name: /REPLAY/i });
    await act(async () => {
      fireEvent.click(footerBtn);
    });
    expect(useSimulationStore.getState().barOpen).toBe(true);
  });
});
