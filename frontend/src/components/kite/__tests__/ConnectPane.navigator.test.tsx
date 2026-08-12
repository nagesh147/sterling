import { describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen } from '@testing-library/react';
import React from 'react';
import { ConnectPane } from '../ConnectPane';

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
  useSetEngineConfig: () => ({ mutate: vi.fn(), isPending: false }),
  usePatchEngineConfig: () => ({ mutate: vi.fn(), isPending: false }),
  useEngineSignals: () => ({ data: { rows: [] } }),
}));

// The rail summarises which engines are running, so ConnectPane itself reads the
// Navigator config. Unmocked, that hook has no QueryClient and every test here fails
// before it renders anything.
vi.mock('../../../hooks/useNavigator', () => ({
  useNavigatorConfig: () => ({ data: { record: { config: { enabled: false } } } }),
}));

vi.mock('../TradingModePanel', () => ({ TradingModePanel: () => <div>Trading mode controls</div> }));
vi.mock('../TradeRulesPanels', () => ({
  ManualRulesPanel: () => <div>Manual rules panel</div>,
  AutomaticRulesPanel: () => <div>Automatic rules panel</div>,
}));
vi.mock('../SuperTrendEnginePanel', () => ({ SuperTrendEnginePanel: () => <div>SuperTrend strategy panel</div> }));
vi.mock('../NavigatorSettingsPanel', () => ({ NavigatorSettingsPanel: () => <div>Navigator settings panel</div> }));
vi.mock('../NavigatorCalibrationPanel', () => ({ NavigatorCalibrationPanel: () => <div>Navigator calibration panel</div> }));
vi.mock('../KiteTelegramPanel', () => ({
  KiteTelegramPanel: () => <div>Kite alert destinations</div>,
  BrandIconPicker: () => <div>Icon picker</div>,
}));
vi.mock('../MotionStyleSettings', () => ({ MotionStyleSettings: () => <div>Motion style choices</div> }));
vi.mock('../KiteExchangeSettingsCard', () => ({ KiteExchangeSettingsCard: () => <div>Exchange choices</div> }));

describe('ConnectPane — Navigator settings section', () => {
  it('has its own dedicated rail item, separate from Engine Configuration', () => {
    render(<ConnectPane />);
    expect(screen.getByRole('button', { name: /Value-Flow Navigator AVWAP, volatility & options flow/i })).toBeInTheDocument();
  });

  it('renders NavigatorSettingsPanel only when its section is selected', () => {
    render(<ConnectPane />);
    expect(screen.queryByText('Navigator settings panel')).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: /Value-Flow Navigator AVWAP, volatility & options flow/i }));
    expect(screen.getByRole('heading', { name: 'Value-Flow Navigator' })).toBeInTheDocument();
    expect(screen.getByText('Navigator settings panel')).toBeInTheDocument();
    // Not copied into the existing engine form
    expect(screen.queryByText('SuperTrend strategy panel')).not.toBeInTheDocument();
  });
});
