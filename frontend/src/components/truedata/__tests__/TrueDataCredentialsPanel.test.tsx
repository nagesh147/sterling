import { beforeEach, describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen } from '@testing-library/react';
import React from 'react';
import { TrueDataCredentialsPanel } from '../TrueDataCredentialsPanel';

const addMutate = vi.fn();
const deleteMutate = vi.fn();
const updateMutate = vi.fn();
const updateSettingsMutate = vi.fn();
const runDiagMutateAsync = vi.fn().mockResolvedValue({
  categories: [
    {
      id: 'truedata_auth',
      status: 'PASS',
      latency_ms: 372.9,
    },
  ],
});

vi.mock('../../../hooks/useTrueData', () => ({
  useTrueDataSettings: () => ({
    data: { data_source: 'truedata' },
    isLoading: false,
  }),
  useUpdateTrueDataSettings: () => ({ mutate: updateSettingsMutate, isPending: false }),
  useTrueDataCredentials: () => ({
    data: [
      {
        id: 'TD-TEST1',
        user_id: 'user1',
        label: 'Primary TrueData Feed',
        username_hint: 'tu****23',
        has_credentials: true,
        connected: true,
        is_active: true,
        realtime_port: 8082,
        created_at_ms: 1700000000000,
        updated_at_ms: 1700000000000,
      },
    ],
    isLoading: false,
  }),
  useAddTrueDataCredential: () => ({ mutate: addMutate, isPending: false, error: null }),
  useUpdateTrueDataCredential: () => ({ mutate: updateMutate, isPending: false, error: null }),
  useDeleteTrueDataCredential: () => ({ mutate: deleteMutate, isPending: false }),
  useRunTrueDataDiagnostics: () => ({ mutateAsync: runDiagMutateAsync, isPending: false }),
  useTrueDataStatus: () => ({
    data: {
      connected: true,
      is_active: true,
      account_id: 'TD-TEST1',
      username_hint: 'tu****23',
      message: 'Credentials configured',
    },
  }),
}));

describe('TrueDataCredentialsPanel', () => {
  beforeEach(() => {
    addMutate.mockClear();
    deleteMutate.mockClear();
    updateMutate.mockClear();
    updateSettingsMutate.mockClear();
    runDiagMutateAsync.mockClear();
  });

  it('renders data source selector with TrueData and Zerodha options', () => {
    render(<TrueDataCredentialsPanel />);
    expect(screen.getByText('PRIMARY MARKET DATA SOURCE')).toBeInTheDocument();
    expect(screen.getByText('ACTIVE: TRUEDATA')).toBeInTheDocument();
    expect(screen.getByText('TrueData Feed (Recommended)')).toBeInTheDocument();
    expect(screen.getByText('Zerodha Kite Feed')).toBeInTheDocument();

    const kiteOption = screen.getByText('Zerodha Kite Feed');
    fireEvent.click(kiteOption);
    expect(updateSettingsMutate).toHaveBeenCalledWith({ data_source: 'zerodhakite' });
  });

  it('renders status card without exposing raw credentials and supports test connection', async () => {
    render(<TrueDataCredentialsPanel />);
    expect(screen.getByText('TRUEDATA MARKET DATA STATUS')).toBeInTheDocument();
    expect(screen.getByText('Connected (tu****23)')).toBeInTheDocument();
    expect(screen.getByText('Primary TrueData Feed')).toBeInTheDocument();
    expect(screen.getByText('User: tu****23 · Active Feed · Connected')).toBeInTheDocument();

    // Expand the card
    const cardHeader = screen.getByText('Primary TrueData Feed');
    fireEvent.click(cardHeader);

    // Verify Test button is rendered and functional
    const testBtn = screen.getByRole('button', { name: /Test Connection/i });
    expect(testBtn).toBeInTheDocument();
    await fireEvent.click(testBtn);
    expect(runDiagMutateAsync).toHaveBeenCalledWith({ category_id: 'truedata_auth' });
  });

  it('allows clicking add button to reveal form with password input', () => {
    render(<TrueDataCredentialsPanel />);
    const addBtn = screen.getByRole('button', { name: '+ ADD TRUEDATA CREDENTIALS' });
    fireEvent.click(addBtn);

    expect(screen.getByText('NEW TRUEDATA FEED CREDENTIALS')).toBeInTheDocument();
    expect(screen.getByPlaceholderText('TrueData Username')).toBeInTheDocument();
    
    const passInput = screen.getByPlaceholderText('TrueData Password') as HTMLInputElement;
    expect(passInput).toBeInTheDocument();
    expect(passInput.type).toBe('password');
  });
});
