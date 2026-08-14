import { beforeEach, describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen } from '@testing-library/react';
import React from 'react';
import { TrueDataCredentialsPanel } from '../TrueDataCredentialsPanel';

const addMutate = vi.fn();
const deleteMutate = vi.fn();
const updateMutate = vi.fn();

vi.mock('../../../hooks/useTrueData', () => ({
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
  });

  it('renders status card without exposing raw credentials', () => {
    render(<TrueDataCredentialsPanel />);
    expect(screen.getByText('TRUEDATA MARKET DATA STATUS')).toBeInTheDocument();
    expect(screen.getByText('Connected (tu****23)')).toBeInTheDocument();
    expect(screen.getByText('Primary TrueData Feed')).toBeInTheDocument();
    expect(screen.getByText('User: tu****23 · Active Feed · Connected')).toBeInTheDocument();
  });

  it('allows clicking add button to reveal form with password input', () => {
    render(<TrueDataCredentialsPanel />);
    const addBtn = screen.getByRole('button', { name: '+ ADD TRUEDATA CREDENTIAL' });
    fireEvent.click(addBtn);

    expect(screen.getByText('ADD TRUEDATA CREDENTIAL')).toBeInTheDocument();
    expect(screen.getByPlaceholderText('TrueData Username')).toBeInTheDocument();
    
    const passInput = screen.getByPlaceholderText('TrueData Password') as HTMLInputElement;
    expect(passInput).toBeInTheDocument();
    expect(passInput.type).toBe('password');
  });
});
