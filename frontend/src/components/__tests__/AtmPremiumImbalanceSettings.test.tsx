/**
 * The panel's contract with the operator.
 *
 * This strategy was reverse-engineered, so the panel carries two obligations
 * the other engine panels do not: it must state that provenance rather than
 * looking like a validated engine, and it must not present a research-only
 * option as if it were tradable. Both are asserted here.
 *
 * Defaults and vocabularies come from the server, never from a second copy in
 * the client — that drift is the bug class this codebase keeps hitting.
 */
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import React from 'react';
import { AtmPremiumImbalanceSettings } from '../AtmPremiumImbalanceSettings';
import type {
  AtmPremiumImbalanceConfig, AtmPremiumImbalanceResponse,
} from '../../hooks/useAtmPremiumImbalance';

const DEFAULTS: AtmPremiumImbalanceConfig = {
  enabled: false,
  underlying: 'SENSEX',
  expiry_policy: 'NEAREST',
  expiry_dte_min: 0, expiry_dte_max: 60, avoid_expiry_day: false,
  explicit_expiry: '',
  strike_policy: 'ATM_NEAREST',
  session_start: '09:15',
  session_end: '15:25',
  quote_mode: 'COMPATIBILITY',
  max_quote_age_ms: 2000,
  max_ce_pe_skew_ms: 1000,
  signal_mode: 'CHEAPER_LEG',
  minimum_difference: 0,
  minimum_difference_percent: 0,
  entry_price_policy: 'MARKETABLE_ASK',
  require_session_origin_tick: true,
  first_tick_source: 'SESSION_TICK',
  entry_buffer_points: 0.5,
  entry_through_pct: 0,
  manual_price_file: '',
  max_entry_attempts: 3,
  entry_attempt_timeout_ms: 1500,
  exit_policy: 'FIXED_POINT_TARGET',
  protection_mode: 'NONE',
  target_points: 15,
  exit_buffer_points: 0.5,
  stop_enabled: false,
  stop_points: 0,
  max_hold_seconds: 0,
  max_trades_per_session: 1,
  sizing_mode: 'QUANTITY',
  lots: 0,
  stop_basis: 'POINTS',
  stop_percent: 0,
  trail_points: 0,
  trail_percent: 0,
  trail_start_points: 0,
  trail_start_percent: 0,
  breakeven_points: 0,
  breakeven_percent: 0,
  entry_window_seconds: 300,
  close_at_session_end: true,
  quantity: 0,
  max_quantity: 500,
  max_premium_at_risk_inr: 25000,
  daily_loss_limit_inr: 10000,
  data_source: 'kite',
  execution_mode: 'paper',
};

const STRATEGY: AtmPremiumImbalanceResponse['strategy'] = {
  id: 'atm_premium_imbalance',
  name: 'ATM Premium Imbalance',
  contract_version: 'A230.4',
  tagline: 'Buys the cheaper ATM leg at the open and takes a fixed +15 points.',
  how_it_works: 'Compares ATM call and put premiums at the open.',
  provenance: 'Reverse-engineered from recordings',
  live_ready: false,
  enabled: false,
};

const setConfig = vi.fn();
let serverConfig: AtmPremiumImbalanceConfig;

vi.mock('../../hooks/useAtmPremiumImbalance', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../../hooks/useAtmPremiumImbalance')>();
  return {
    ...actual,
    useAtmPremiumImbalanceConfig: () => ({
      data: {
        strategy: { ...STRATEGY, enabled: serverConfig.enabled },
        config: serverConfig,
        defaults: DEFAULTS,
        vocabularies: {
          quote_mode: ['COMPATIBILITY', 'EXECUTABLE', 'SYNCHRONIZED'],
          sizing_mode: ['LOTS', 'QUANTITY'],
          stop_basis: ['PERCENT', 'POINTS'],
          data_source: ['kite', 'truedata'],
        },
        research_only: {
          entry_price_policy: ['FIRST_TICK_PLUS_BUFFER'],
          exit_policy: ['PREMIUM_CONVERGENCE'],
        },
      },
      isLoading: false,
      error: null,
    }),
    useAtmPremiumImbalanceSnapshot: () => ({
      data: { resolved: { ce: { lot_size: 20 }, pe: { lot_size: 20 } } },
      isLoading: false, error: null,
    }),
    useSetAtmPremiumImbalanceConfig: () => ({
      mutate: setConfig, isPending: false, isError: false, error: null,
    }),
  };
});

beforeEach(() => {
  setConfig.mockClear();
  serverConfig = { ...DEFAULTS };
});

describe('AtmPremiumImbalanceSettings', () => {
  it('states the provenance and the two evidenced constants', () => {
    render(<AtmPremiumImbalanceSettings />);
    expect(screen.getByText(/Reverse-engineered from screen recordings/)).toBeInTheDocument();
    expect(screen.getByText(/\+15 point target/)).toBeInTheDocument();
    expect(screen.getByText(/best bid − 0.5/)).toBeInTheDocument();
    expect(screen.getByText(/Nothing has been through a walk-forward/)).toBeInTheDocument();
  });

  it('says live is blocked while the strategy is not live-ready', () => {
    render(<AtmPremiumImbalanceSettings />);
    expect(screen.getByText(/Live execution stays blocked/)).toBeInTheDocument();
  });

  it('marks research-only policies as unable to run live', () => {
    render(<AtmPremiumImbalanceSettings />);
    // Driven by the server's research_only list, not a client copy: the points
    // entry variant and the convergence exit are both research-only.
    expect(screen.getAllByTitle(/Cannot run live/)).toHaveLength(2);
  });

  it('renders the observed defaults from the server payload', () => {
    render(<AtmPremiumImbalanceSettings />);
    expect(screen.getByDisplayValue('15')).toBeInTheDocument();     // target points
    expect(screen.getByDisplayValue('3')).toBeInTheDocument();      // max attempts
  });

  it('shows the entry buffer only for the policies that use it', () => {
    render(<AtmPremiumImbalanceSettings />);
    expect(screen.getByText('Entry buffer')).toBeInTheDocument();
    expect(screen.queryByText('Through the ask')).not.toBeInTheDocument();
    // Queried by placeholder, not label: "Price file" is also a policy option
    // label and is always on screen.
    expect(screen.queryByPlaceholderText('strike_prices.txt')).not.toBeInTheDocument();
  });

  it('swaps to the price-file field when the manual policy is chosen', () => {
    serverConfig = { ...DEFAULTS, entry_price_policy: 'MANUAL_FILE' };
    render(<AtmPremiumImbalanceSettings />);
    expect(screen.getByPlaceholderText('strike_prices.txt')).toBeInTheDocument();
    expect(screen.queryByText('Entry buffer')).not.toBeInTheDocument();
  });

  it('keeps the stop distance hidden until a stop is enabled', () => {
    render(<AtmPremiumImbalanceSettings />);
    expect(screen.queryByText('Stop distance')).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole('switch', { name: 'Stop loss' }));
    expect(screen.getByText('Stop distance')).toBeInTheDocument();
  });

  it('does not send anything until the draft is applied', () => {
    render(<AtmPremiumImbalanceSettings />);
    fireEvent.click(screen.getByRole('switch', { name: 'Stop loss' }));
    expect(setConfig).not.toHaveBeenCalled();
  });

  it('shows the explicit expiry field only for the EXPLICIT policy', () => {
    serverConfig = { ...DEFAULTS, expiry_policy: 'EXPLICIT' };
    render(<AtmPremiumImbalanceSettings />);
    expect(screen.getByPlaceholderText('YYYY-MM-DD')).toBeInTheDocument();
  });
});

describe('stating the trade size', () => {
  // "Lots" and "Quantity" are each both a mode button and a field label, so
  // these assert on the hints — the only text unique to one box.
  const LOTS_HINT = /One lot is 20 contracts/;
  const QTY_HINT = /Must be a multiple of 20/;

  it('offers lots or quantity', () => {
    render(<AtmPremiumImbalanceSettings />);
    expect(screen.getAllByTitle(/Say how many lots/).length).toBeGreaterThan(0);
    expect(screen.getAllByTitle(/Say the exact number of contracts/).length).toBeGreaterThan(0);
  });

  it('shows one size box at a time, matching the chosen mode', () => {
    serverConfig = { ...DEFAULTS, sizing_mode: 'QUANTITY', quantity: 20 };
    render(<AtmPremiumImbalanceSettings />);
    expect(screen.getByText(QTY_HINT)).toBeInTheDocument();
    expect(screen.queryByText(LOTS_HINT)).not.toBeInTheDocument();
  });

  it('spells out what a lot count actually orders', () => {
    // The hint has to do the arithmetic; "2" on its own tells the operator
    // nothing about how much they are buying.
    serverConfig = { ...DEFAULTS, sizing_mode: 'LOTS', lots: 2 };
    render(<AtmPremiumImbalanceSettings />);
    expect(screen.getByText(/One lot is 20 contracts, so this orders 40/)).toBeInTheDocument();
    expect(screen.queryByText(QTY_HINT)).not.toBeInTheDocument();
  });

  it('reads the lot size from the resolved contract, not a hardcoded 20', () => {
    serverConfig = { ...DEFAULTS, sizing_mode: 'LOTS', lots: 3 };
    render(<AtmPremiumImbalanceSettings />);
    expect(screen.getByText(/so this orders 60/)).toBeInTheDocument();
  });

  it('switching mode is a draft, like every other change here', () => {
    serverConfig = { ...DEFAULTS, sizing_mode: 'QUANTITY', quantity: 20 };
    render(<AtmPremiumImbalanceSettings />);
    fireEvent.click(screen.getAllByTitle(/Say how many lots/)[0]);
    expect(screen.getByText(LOTS_HINT)).toBeInTheDocument();   // the box swaps at once
    expect(setConfig).not.toHaveBeenCalled();                  // but nothing is sent
  });
});

describe('the stop ladder', () => {
  it('stays hidden until a stop is switched on', () => {
    render(<AtmPremiumImbalanceSettings />);
    expect(screen.queryByText('Trail distance')).not.toBeInTheDocument();
    expect(screen.queryByText('Break even at')).not.toBeInTheDocument();
  });

  it('shows every rung once a stop is on', () => {
    serverConfig = { ...DEFAULTS, stop_enabled: true, stop_points: 15 };
    render(<AtmPremiumImbalanceSettings />);
    expect(screen.getByText('Stop distance')).toBeInTheDocument();
    expect(screen.getByText('Break even at')).toBeInTheDocument();
    expect(screen.getByText('Trail starts at')).toBeInTheDocument();
    expect(screen.getByText('Trail distance')).toBeInTheDocument();
  });

  it('says the stop only ever moves up', () => {
    // The ratchet is the safety property; the panel should not leave it implied.
    serverConfig = { ...DEFAULTS, stop_enabled: true, stop_points: 15 };
    render(<AtmPremiumImbalanceSettings />);
    expect(screen.getByText(/only ever moves up/)).toBeInTheDocument();
  });

  it('shows one unit at a time, so a number always means its suffix', () => {
    serverConfig = { ...DEFAULTS, stop_enabled: true, stop_basis: 'PERCENT',
                     stop_percent: 20 };
    render(<AtmPremiumImbalanceSettings />);
    expect(screen.getByText(/share of the entry premium/)).toBeInTheDocument();
    expect(screen.queryByText(/Rupees below the entry fill/)).not.toBeInTheDocument();
  });

  it('offers a trailing stop, and does not pretend it came from the video', () => {
    render(<AtmPremiumImbalanceSettings />);
    const opt = screen.getAllByTitle(/No fixed target/)[0];
    expect(opt).toBeTruthy();
    expect(opt.title).toMatch(/the recordings show no stop of any kind/);
  });
});

describe('the session window', () => {
  it('exposes the entry window rather than hiding it in code', () => {
    render(<AtmPremiumImbalanceSettings />);
    expect(screen.getByText('Entry window')).toBeInTheDocument();
    expect(screen.getByText(/without a window it would enter whenever it was armed/))
      .toBeInTheDocument();
  });

  it('says why a position is closed at the end of the session', () => {
    render(<AtmPremiumImbalanceSettings />);
    expect(screen.getByText(/held to expiry — a bought option can settle worthless/))
      .toBeInTheDocument();
  });
});

