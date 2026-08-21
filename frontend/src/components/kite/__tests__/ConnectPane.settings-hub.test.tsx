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
  // SuperTrend's contract picker moved onto this page, and it reads the live
  // Kite expiry calendar.
  useExpiryCalendar: () => ({ data: undefined, isLoading: false, isError: false, isFetching: false, refetch: vi.fn() }),
  useRunScan: () => ({ mutate: vi.fn(), isPending: false }),
}));

// The rail summarises which engines are running, so ConnectPane itself reads the
// Navigator config. Unmocked, that hook has no QueryClient and every test here fails
// before it renders anything.
vi.mock('../../../hooks/useNavigator', () => ({
  useNavigatorConfig: () => ({ data: { record: { config: { enabled: false } } } }),
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
vi.mock('../AdaptiveEdgeSettingsPanel', () => ({ AdaptiveEdgeSettingsPanel: () => <div>Adaptive Edge settings panel</div> }));
vi.mock('../OrbMomentumOptionsSettingsPanel', () => ({ OrbMomentumOptionsSettingsPanel: () => <div>ORB options settings panel</div> }));
vi.mock('../../datalake/DataLakeSettingsPanel', () => ({ DataLakeSettingsPanel: () => <div>Offline data settings</div> }));

describe('ConnectPane settings hub', () => {
  beforeEach(() => {
    localStorage.clear();
    setConfig.mockClear();
  });

  it('uses one category rail and gives each settings family one home', () => {
    render(<ConnectPane />);

    // The page title is now the selected section's own name, under a quiet
    // "Settings" eyebrow — so the heading tracks where you are rather than
    // restating the hub on every page.
    expect(screen.getByText('Settings')).toBeInTheDocument();
    expect(screen.getByRole('navigation', { name: 'Kite settings sections' })).toBeInTheDocument();
    expect(screen.queryAllByRole('tab')).toHaveLength(0);
    expect(screen.getByRole('heading', { name: 'Account & Login' })).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: /SuperTrend\s*Scan, entry & exit/i }));
    expect(screen.getByRole('heading', { name: 'SuperTrend' })).toBeInTheDocument();
    expect(screen.getByText('SuperTrend strategy panel')).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: /Notifications\s*Kite Telegram alerts/i }));
    expect(screen.getByRole('heading', { name: 'Notifications' })).toBeInTheDocument();
    expect(screen.getByText('Kite alert destinations')).toBeInTheDocument();
    expect(screen.queryByText('Icon picker')).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: /Experience\s*Motion & feedback/i }));
    expect(screen.getByRole('heading', { name: 'Experience' })).toBeInTheDocument();
    expect(screen.getByText('Motion style choices')).toBeInTheDocument();
    expect(screen.getByText('Icon picker')).toBeInTheDocument();
  });

  it('groups the rail by what a setting decides', () => {
    render(<ConnectPane />);
    ['Connection', 'Trading', 'Signal engines', 'Platform']
      .forEach((group) => expect(screen.getByText(group)).toBeInTheDocument());
  });

  it('places Adaptive Edge next to Value-Flow Navigator', () => {
    render(<ConnectPane />);
    const navigator = screen.getByRole('button', { name: /Value-Flow Navigator AVWAP, volatility & options flow/i });
    const adaptive = screen.getByRole('button', { name: /Adaptive Edge Score, modes, TBT structure/i });
    expect(navigator.compareDocumentPosition(adaptive) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    fireEvent.click(adaptive);
    expect(screen.getByRole('heading', { name: 'Adaptive Edge' })).toBeInTheDocument();
    expect(screen.getByText('Adaptive Edge settings panel')).toBeInTheDocument();
  });

  it('gives ORB + VWAP Options a home in the rail', () => {
    // The panel existed but was mounted nowhere, so the whole ORB UI was
    // unreachable from the app. This is the assertion that would have caught it.
    render(<ConnectPane />);
    const orb = screen.getByRole('button', { name: /ORB \+ VWAP Options Opening range breakout, buy-only/i });
    fireEvent.click(orb);
    expect(screen.getByRole('heading', { name: 'ORB + VWAP Options' })).toBeInTheDocument();
    expect(screen.getByText('ORB options settings panel')).toBeInTheDocument();
  });

  it('groups ORB with the other signal engines', () => {
    render(<ConnectPane />);
    const adaptive = screen.getByRole('button', { name: /Adaptive Edge Score, modes, TBT structure/i });
    const orb = screen.getByRole('button', { name: /ORB \+ VWAP Options/i });
    expect(adaptive.compareDocumentPosition(orb) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
  });

  it('gives manual and automatic rules separate homes, not one filtered page', () => {
    // The single page with an All / Manual / Automatic filter made the reader
    // decode a per-row badge to know whether a rule applied to them.
    render(<ConnectPane />);

    fireEvent.click(screen.getByRole('button', { name: /Manual Trade\s*Orders you place/i }));
    expect(screen.getByRole('heading', { name: 'Manual Trade' })).toBeInTheDocument();
    expect(screen.getByText('Manual rules panel')).toBeInTheDocument();
    expect(screen.queryByText('Automatic rules panel')).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: /Algo Trade\s*Orders the algo places/i }));
    expect(screen.getByRole('heading', { name: 'Algo Trade' })).toBeInTheDocument();
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
    fireEvent.click(screen.getByRole('button', { name: /Trading Mode\s*Paper\/live, manual\/algo/i }));
    expect(screen.getByRole('heading', { name: 'Trading Mode' })).toBeInTheDocument();
    expect(screen.getByText('Trading mode controls')).toBeInTheDocument();
    expect(screen.getByText('Exchange choices')).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: /SuperTrend\s*Scan, entry & exit/i }));
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
    expect(screen.getByRole('heading', { name: 'Algo Trade' })).toBeInTheDocument();
  });

  it('follows the one-page Trade Rules deep link to the manual half', () => {
    localStorage.setItem('kite_connect_section', 'rules');
    render(<ConnectPane />);
    expect(screen.getByRole('heading', { name: 'Manual Trade' })).toBeInTheDocument();
  });
});
