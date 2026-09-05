import React from 'react';
import { render, screen } from '@testing-library/react';
import { describe, it, expect, beforeEach } from 'vitest';
import { SimulationSummary } from '../SimulationSummary';
import { useSimulationStore } from '../../../hooks/useSimulation';

describe('SimulationSummary Component', () => {
  beforeEach(() => {
    useSimulationStore.setState({
      showSummary: false,
      date: '2026-09-04',
      startTime: '09:15',
      endTime: '15:30',
      status: {
        state: 'idle',
        config: {
          date: '2026-09-04',
          start_time: '09:15',
          end_time: '15:30',
          speed: 5,
          resolution: '1m',
          instruments: ['NIFTY'],
          friction_mode: 'realistic',
          slippage_bps: 100,
        },
        current_time_iso: '2026-09-04T15:30:00',
        progress_pct: 100,
        bars_played: 75,
        bars_total: 75,
        stats: {
          signals_fired: 3,
          trades_entered: 2,
          wins: 1,
          losses: 1,
          pnl: 1250.5,
          events: [
            {
              time_iso: '09:15:00',
              strategy: 'supertrend',
              instrument: 'NIFTY 25000 CE',
              contract: 'NIFTY 25000 CE',
              direction: 'BULLISH',
              entry: 105.0,
              stop: 90.0,
              target: 130.0,
              strength: 'STRONG',
            },
          ],
          trades: [
            {
              trade_id: 'SIM-001',
              strategy: 'supertrend',
              symbol: 'NIFTY 25000 CE',
              underlying: 'NIFTY',
              direction: 'LONG',
              opt_type: 'CE',
              strike: 25000,
              lots: 1,
              quantity: 25,
              entry_price: 105.5,
              raw_entry: 105.0,
              exit_price: 130.0,
              raw_exit: 130.5,
              stop_loss: 90.0,
              target_price: 130.0,
              timestamp_ms: 1725421500000,
              slippage: 25.0,
              pnl_usd: 612.5,
              pnl_pct: 23.2,
              status: 'WIN',
              entry_time_iso: '09:15:00',
              exit_time_iso: '09:45:00',
              duration_mins: 30,
            },
            {
              trade_id: 'SIM-002',
              strategy: 'vcp',
              symbol: 'NIFTY 25100 PE',
              underlying: 'NIFTY',
              direction: 'LONG',
              opt_type: 'PE',
              strike: 25100,
              lots: 1,
              quantity: 25,
              entry_price: 82.0,
              raw_entry: 81.5,
              exit_price: 65.0,
              raw_exit: 65.5,
              stop_loss: 95.0,
              target_price: 60.0,
              timestamp_ms: 1725424200000,
              slippage: 25.0,
              pnl_usd: -425.0,
              pnl_pct: -20.7,
              status: 'LOSS',
              entry_time_iso: '10:00:00',
              exit_time_iso: '10:20:00',
              duration_mins: 20,
            },
          ],
        },
        elapsed_real_s: 15,
        status_message: 'Completed',
        last_signal: null,
      },
    });
  });

  it('renders nothing when showSummary is false', () => {
    const { container } = render(<SimulationSummary />);
    expect(container.firstChild).toBeNull();
  });

  it('renders simulation summary with realistic friction badge and execution metrics', () => {
    useSimulationStore.setState({ showSummary: true });
    render(<SimulationSummary />);

    expect(screen.getByText('Simulation Complete')).toBeInTheDocument();
    expect(screen.getByText('⚡ REALISTIC FRICTION')).toBeInTheDocument();
    expect(screen.getByText('Slippage Drag')).toBeInTheDocument();
    expect(screen.getByText('-₹50.00')).toBeInTheDocument();
    expect(screen.getByText('Profit Factor')).toBeInTheDocument();
    expect(screen.getByText('Max Drawdown')).toBeInTheDocument();

    // Trades table checks
    expect(screen.getByText('Executed Trades Log')).toBeInTheDocument();
    expect(screen.getByText('Slippage')).toBeInTheDocument();
    expect(screen.getByText('SIM-001')).toBeInTheDocument();
    expect(screen.getByText('SIM-002')).toBeInTheDocument();
    expect(screen.getByText('raw ₹105')).toBeInTheDocument();
    expect(screen.getAllByText('-₹25.00').length).toBeGreaterThanOrEqual(1);

    // CSV export buttons
    expect(screen.getByText('📥 Export Signals CSV')).toBeInTheDocument();
    expect(screen.getByText('📥 Export Trades CSV')).toBeInTheDocument();
  });

  it('renders zero friction badge when friction mode is ideal', () => {
    const currentStatus = useSimulationStore.getState().status;
    useSimulationStore.setState({
      showSummary: true,
      status: {
        ...currentStatus,
        config: {
          ...currentStatus.config!,
          friction_mode: 'ideal',
        },
      },
    });

    render(<SimulationSummary />);
    expect(screen.getByText('🎯 ZERO FRICTION')).toBeInTheDocument();
  });
});

