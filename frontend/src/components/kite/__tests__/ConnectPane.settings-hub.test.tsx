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
  useEngineSignals: () => ({ data: { rows: [] } }),
}));

vi.mock('../TradingModeControls', () => ({ TradingModeControls: () => <div>Trading mode controls</div> }));
vi.mock('../DirectionalModePanel', () => ({ DirectionalModePanel: () => <div>Order profile controls</div> }));
vi.mock('../EngineConfigurationPanel', () => ({ EngineConfigurationPanel: () => <div>Engine configuration panel</div> }));
vi.mock('../SharedScanSetupPanel', () => ({ SharedScanSetupPanel: () => <div>Shared scan setup panel</div> }));
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

    fireEvent.click(screen.getByRole('button', { name: /SuperTrend Engine Triple-SuperTrend signals & exits/i }));
    expect(screen.getByRole('heading', { name: 'SuperTrend Engine' })).toBeInTheDocument();
    expect(screen.getByText('Trading mode controls')).toBeInTheDocument();
    expect(screen.getByText('Engine configuration panel')).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: /Order Selection & Entry Quality Vehicle profile & filters/i }));
    expect(screen.getByRole('heading', { name: 'Order Selection & Entry Quality' })).toBeInTheDocument();
    expect(screen.getByText('Order profile controls')).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: /Notifications Kite Telegram alerts/i }));
    expect(screen.getByRole('heading', { name: 'Notifications' })).toBeInTheDocument();
    expect(screen.getByText('Kite alert destinations')).toBeInTheDocument();
    expect(screen.queryByText('Icon picker')).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: /Experience Motion & feedback/i }));
    expect(screen.getByRole('heading', { name: 'Experience' })).toBeInTheDocument();
    expect(screen.getByText('Motion style choices')).toBeInTheDocument();
    expect(screen.getByText('Icon picker')).toBeInTheDocument();
  });

  it('gives the settings both engines share their own home, separate from either engine', () => {
    render(<ConnectPane />);
    fireEvent.click(screen.getByRole('button', { name: /Scan Setup Shared by both engines/i }));
    expect(screen.getByRole('heading', { name: 'Scan Setup' })).toBeInTheDocument();
    expect(screen.getByText('Shared scan setup panel')).toBeInTheDocument();
    // it is its own section, not nested inside the SuperTrend engine's page
    expect(screen.queryByText('Engine configuration panel')).not.toBeInTheDocument();
  });
});
