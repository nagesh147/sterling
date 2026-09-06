/**
 * The daily-loss limit page.
 *
 * The figure it edits stops live orders, so the two things worth pinning are
 * the sign convention (typed positive, stored negative) and that a pair the
 * backend would reject cannot be submitted from here.
 */
import React from 'react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { DailyLossLimitPanel } from '../DailyLossLimitPanel';
import { api } from '../../../utils/api';

const LIMIT = {
  enabled: true, soft_warn_inr: -8000, hard_halt_inr: -12000,
  uid: 'u1', is_account_override: true, pnl_inr: -3000, level: 'clear' as const,
  default: { enabled: true, soft_warn_inr: -1000, hard_halt_inr: -1500 },
};

function show(over: Partial<typeof LIMIT> = {}) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={qc}>
      <DailyLossLimitPanel />
    </QueryClientProvider>,
  );
}

beforeEach(() => {
  vi.restoreAllMocks();
  vi.spyOn(api, 'get').mockResolvedValue(LIMIT as never);
  vi.spyOn(api, 'put').mockResolvedValue(LIMIT as never);
  vi.spyOn(api, 'delete').mockResolvedValue({ ...LIMIT, is_account_override: false } as never);
});

it('shows the stored limit as a positive rupee figure', async () => {
  show();
  expect(await screen.findByTestId('daily-loss-halt')).toHaveValue(12000);
  expect(screen.getByTestId('daily-loss-warn')).toHaveValue(8000);
});

it('stores what was typed as a loss', async () => {
  // Typed 20000, saved -20000. Asking someone to type the minus sign is how a
  // limit of +20000 that can never trigger gets saved.
  show();
  fireEvent.change(await screen.findByTestId('daily-loss-halt'), { target: { value: '20000' } });
  fireEvent.click(screen.getByRole('button', { name: 'Apply' }));
  await waitFor(() => expect(api.put).toHaveBeenCalledWith(
    '/api/v1/kite/risk/daily-loss',
    { enabled: true, soft_warn_inr: -8000, hard_halt_inr: -20000 },
  ));
});

it('will not submit a halt smaller than the warning', async () => {
  // It would halt before it ever warned, and the backend rejects the pair.
  show();
  fireEvent.change(await screen.findByTestId('daily-loss-halt'), { target: { value: '100' } });
  expect(screen.getByRole('button', { name: 'Apply' })).toBeDisabled();
  expect(api.put).not.toHaveBeenCalled();
});

it('will not submit zero, which reads as no limit but halts everything', async () => {
  show();
  fireEvent.change(await screen.findByTestId('daily-loss-halt'), { target: { value: '0' } });
  expect(screen.getByRole('button', { name: 'Apply' })).toBeDisabled();
});

it('says when the account is on the shared default rather than its own', async () => {
  vi.spyOn(api, 'get').mockResolvedValue({ ...LIMIT, is_account_override: false } as never);
  show();
  expect(await screen.findByText(/On the shared default/)).toBeInTheDocument();
  expect(screen.queryByRole('button', { name: 'Use the default' })).not.toBeInTheDocument();
});

it('offers a way back to the default only when there is an override', async () => {
  show();
  fireEvent.click(await screen.findByRole('button', { name: 'Use the default' }));
  await waitFor(() => expect(api.delete).toHaveBeenCalledWith('/api/v1/kite/risk/daily-loss'));
});
