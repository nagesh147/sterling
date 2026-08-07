import { beforeEach, describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen } from '@testing-library/react';
import React from 'react';
import { ConnectPane } from '../ConnectPane';

const setConfig = vi.fn();

vi.mock('../../../hooks/useKite', () => ({
  useKiteAccounts: () => ({ data: { accounts: [], count: 0 }, isLoading: false }),
  useAddKiteAccount: () => ({ mutate: vi.fn(), isPending: false, error: null }),
  useActivateKiteAccount: () => ({ mutate: vi.fn() }),
  useDeleteKiteAccount: () => ({ mutate: vi.fn() }),
  useGenerateKiteSession: () => ({ mutate: vi.fn(), isPending: false }),
  useKiteBasketMargins: () => ({ mutate: vi.fn() }),
  useKiteLoginUrl: () => ({ data: undefined }),
  useKiteLogout: () => ({ mutate: vi.fn() }),
  useKiteOrderCharges: () => ({ mutate: vi.fn() }),
  useKiteOrderMargins: () => ({ mutate: vi.fn() }),
  useKiteMargins: () => ({ data: undefined }),
  useKiteStatus: () => ({ data: undefined }),
  useKiteTickerStatus: () => ({ data: undefined }),
  useKiteTickerSubscribe: () => ({ mutate: vi.fn() }),
  useKiteTickerUnsubscribe: () => ({ mutate: vi.fn() }),
  useRefreshKiteSession: () => ({ mutate: vi.fn() }),
  useTestKiteAccount: () => ({ mutate: vi.fn() }),
  useUpdateKiteAccount: () => ({ mutate: vi.fn(), isPending: false }),
}));

vi.mock('../../../hooks/useSterlingKiteEngine', () => ({
  useEngineConfig: () => ({ data: { engine_enabled: true } }),
  useSetEngineConfig: () => ({ mutate: setConfig, isPending: false }),
  usePatchEngineConfig: () => ({ mutate: setConfig, isPending: false }),
  useEngineSignals: () => ({ data: { rows: [] } }),
}));

vi.mock('../TradingModePanel', () => ({ TradingModePanel: () => <div>Trading mode controls</div> }));
vi.mock('../SuperTrendEnginePanel', () => ({ SuperTrendEnginePanel: () => <div>SuperTrend strategy panel</div> }));
vi.mock('../TradeRulesPanels', () => ({
  ManualRulesPanel: () => <div>Manual rules panel</div>,
  AutomaticRulesPanel: () => <div>Automatic rules panel</div>,
}));
vi.mock('../KiteTelegramPanel', () => ({
  KiteTelegramPanel: () => <div>Kite alert destinations</div>,
  BrandIconPicker: () => <div>Icon picker</div>,
}));
vi.mock('../MotionStyleSettings', () => ({ MotionStyleSettings: () => <div>Motion style choices</div> }));
vi.mock('../KiteExchangeSettingsCard', () => ({ KiteExchangeSettingsCard: () => <div>Exchange choices</div> }));

describe('ConnectPane settings hub', () => {
  beforeEach(() => {
    localStorage.clear();
    setConfig.mockClear();
  });

  it('uses one category rail and gives each settings family one home', () => {
    render(<ConnectPane />);

    expect(screen.getByRole('heading', { name: 'Setup & Settings' })).toBeInTheDocument();
    expect(screen.getByRole('navigation', { name: 'Kite settings sections' })).toBeInTheDocument();
    expect(screen.queryAllByRole('tab')).toHaveLength(0);
    expect(screen.getByRole('heading', { name: 'Account & Login' })).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: /SuperTrend Scan, entry & exit/i }));
    expect(screen.getByRole('heading', { name: 'SuperTrend' })).toBeInTheDocument();
    expect(screen.getByText('SuperTrend strategy panel')).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: /Notifications Kite Telegram alerts/i }));
    expect(screen.getByRole('heading', { name: 'Notifications' })).toBeInTheDocument();
    expect(screen.getByText('Kite alert destinations')).toBeInTheDocument();
    expect(screen.queryByText('Icon picker')).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: /Experience Motion & feedback/i }));
    expect(screen.getByRole('heading', { name: 'Experience' })).toBeInTheDocument();
    expect(screen.getByText('Motion style choices')).toBeInTheDocument();
    expect(screen.getByText('Icon picker')).toBeInTheDocument();
  });

  it('groups the rail by what a setting decides', () => {
    render(<ConnectPane />);
    ['Connection', 'Trading', 'Signal engines', 'Platform']
      .forEach((group) => expect(screen.getByText(group)).toBeInTheDocument());
  });

  it('gives manual and automatic rules separate homes, not one filtered page', () => {
    // The single page with an All / Manual / Automatic filter made the reader
    // decode a per-row badge to know whether a rule applied to them.
    render(<ConnectPane />);

    fireEvent.click(screen.getByRole('button', { name: /Manual Rules Orders you place/i }));
    expect(screen.getByRole('heading', { name: 'Manual Rules' })).toBeInTheDocument();
    expect(screen.getByText('Manual rules panel')).toBeInTheDocument();
    expect(screen.queryByText('Automatic rules panel')).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: /Automatic Rules Orders the engine places/i }));
    expect(screen.getByRole('heading', { name: 'Automatic Rules' })).toBeInTheDocument();
    expect(screen.getByText('Automatic rules panel')).toBeInTheDocument();
    expect(screen.queryByText('Manual rules panel')).not.toBeInTheDocument();
  });

  it('has no All/Manual/Automatic filter left anywhere in the rail', () => {
    render(<ConnectPane />);
    expect(screen.queryByRole('button', { name: 'All rules' })).not.toBeInTheDocument();
  });

  it('lifts paper/live and manual/automatic out of the SuperTrend page onto their own', () => {
    // auto_execute is user-global and Navigator reuses the same placement path,
    // so it never belonged behind a page titled "SuperTrend Engine".
    render(<ConnectPane />);
    fireEvent.click(screen.getByRole('button', { name: /Trading Mode Paper\/live, manual\/automatic/i }));
    expect(screen.getByRole('heading', { name: 'Trading Mode' })).toBeInTheDocument();
    expect(screen.getByText('Trading mode controls')).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: /SuperTrend Scan, entry & exit/i }));
    expect(screen.queryByText('Trading mode controls')).not.toBeInTheDocument();
  });

  it('sends the retired shared-market deep link to the engine that now owns its settings', () => {
    localStorage.setItem('kite_connect_section', 'sharedScan');
    render(<ConnectPane />);
    expect(screen.getByRole('heading', { name: 'SuperTrend' })).toBeInTheDocument();
  });

  it('sends the retired order-selection deep link to Automatic Rules, which absorbed it', () => {
    localStorage.setItem('kite_connect_section', 'orderSelection');
    render(<ConnectPane />);
    expect(screen.getByRole('heading', { name: 'Automatic Rules' })).toBeInTheDocument();
  });

  it('follows the one-page Trade Rules deep link to the manual half', () => {
    localStorage.setItem('kite_connect_section', 'rules');
    render(<ConnectPane />);
    expect(screen.getByRole('heading', { name: 'Manual Rules' })).toBeInTheDocument();
  });
});
