import React from 'react';
import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { SystemDiagnosticsChecklistPanel } from '../SystemDiagnosticsChecklistPanel';

vi.mock('../../../hooks/useKiteDiagnostics', () => ({
  useKiteDiagnosticsSummary: () => ({
    data: {
      authenticated: true,
      account_label: 'Primary Kite',
      kite_user_id: 'AB1234',
      is_paper: true,
      has_credentials: true,
    },
    isLoading: false,
  }),
  useRunKiteDiagnostics: () => ({
    mutateAsync: vi.fn(),
    isPending: false,
  }),
}));

vi.mock('../../../hooks/useTrueData', () => ({
  useTrueDataDiagnosticsSummary: () => ({
    data: {
      authenticated: true,
      username_hint: 'TD_USER',
      is_active: true,
      realtime_port: 8084,
      has_credentials: true,
    },
    isLoading: false,
  }),
  useRunTrueDataDiagnostics: () => ({
    mutateAsync: vi.fn(),
    isPending: false,
  }),
}));

describe('SystemDiagnosticsChecklistPanel', () => {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });

  it('renders title, summary strip, and primary action button', () => {
    render(
      <QueryClientProvider client={queryClient}>
        <SystemDiagnosticsChecklistPanel />
      </QueryClientProvider>
    );

    expect(screen.getByText(/Feed & API Health & Verification Checklist/i)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Run All Verification Checks/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /All Checkpoints/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Zerodha Kite & Network/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /TrueData Market Feeds/i })).toBeInTheDocument();
  });

  it('displays core checkpoints for both Kite and TrueData', () => {
    render(
      <QueryClientProvider client={queryClient}>
        <SystemDiagnosticsChecklistPanel />
      </QueryClientProvider>
    );

    expect(screen.getByText(/Internet & DNS Gateway/i)).toBeInTheDocument();
    expect(screen.getByText(/Kite Session & User Profile/i)).toBeInTheDocument();
    expect(screen.getByText(/Kite Connect HTTPS Gateway/i)).toBeInTheDocument();
    expect(screen.getByText(/TrueData REST WebAPI & Auth Handshake/i)).toBeInTheDocument();
    expect(screen.getByText(/Indices Feed \(Spot OHLC\)/i)).toBeInTheDocument();
    expect(screen.getByText(/Options Greeks Solver/i)).toBeInTheDocument();
  });

  it('supports tab switching and expansion of verifiable proof drawer', () => {
    render(
      <QueryClientProvider client={queryClient}>
        <SystemDiagnosticsChecklistPanel />
      </QueryClientProvider>
    );

    // Switch to Kite tab
    const kiteTab = screen.getByRole('button', { name: /Zerodha Kite & Network/i });
    fireEvent.click(kiteTab);
    expect(screen.getByText(/Zerodha Kite & Network Execution Stack/i)).toBeInTheDocument();

    // Click on row to expand proof drawer
    const row = screen.getByText(/Internet & DNS Gateway/i);
    fireEvent.click(row);
    expect(screen.getByText(/Verified Field Health Checks/i)).toBeInTheDocument();
    expect(screen.getByText(/Verifiable Server Telemetry & Proof Payload/i)).toBeInTheDocument();
  });
});
