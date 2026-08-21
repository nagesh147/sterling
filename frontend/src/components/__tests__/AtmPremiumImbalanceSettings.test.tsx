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
