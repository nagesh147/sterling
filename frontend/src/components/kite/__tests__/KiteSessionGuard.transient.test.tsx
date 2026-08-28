/**
 * The guard must not cry expiry over a failed check.
 *
 * `connected: false` used to mean two things at once — "Kite refused this token"
 * and "we could not reach Kite to ask" — and the guard treated both as a lapsed
 * session. One dropped request produced a "Kite session expired" modal over a
 * perfectly good session, which is what sent a `request_token` to the paste box
 * for no reason at all.
 *
 * Two properties, and the second is the subtle one: a failed check must also not
 * be RECORDED as a disconnect, or it rewrites the previous-state marker and the
 * genuine expiry that follows is no longer a true → false transition — so it
 * goes unannounced entirely. Silencing a false alarm must not silence the real one.
 */
import React from 'react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { act, render, screen, cleanup } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';

let status: Record<string, unknown> = {};

vi.mock('../../../hooks/useKite', () => ({
  useKiteStatus: () => ({ data: status }),
  useKiteAuthBroadcast: () => {},
  useGenerateKiteSession: () => ({ mutate: vi.fn(), isPending: false }),
  useOpenKiteLogin: () => ({ open: vi.fn(), opening: false, phase: 'idle', error: null, dismiss: vi.fn() }),
  useRefreshKiteSession: () => ({ mutate: vi.fn(), isPending: false }),
}));

import { KiteSessionGuard } from '../KiteSessionGuard';

function renderGuard() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  return render(
    <QueryClientProvider client={qc}>
      <KiteSessionGuard />
    </QueryClientProvider>,
  );
}

const CONNECTED = { connected: true, account_id: 'a1', has_refresh_token: false };
const REFUSED = { connected: false, account_id: 'a1', has_refresh_token: false };
const UNREACHABLE = { ...REFUSED, transient: true };

beforeEach(() => { sessionStorage.clear(); vi.useFakeTimers(); });
afterEach(() => { cleanup(); vi.useRealTimers(); });

describe('a failed check', () => {
  it('does not prompt', () => {
    status = CONNECTED;
    const view = renderGuard();
    status = UNREACHABLE;
    view.rerender(
      <QueryClientProvider client={new QueryClient()}><KiteSessionGuard /></QueryClientProvider>,
    );
    act(() => { vi.advanceTimersByTime(20_000); });
    expect(screen.queryByText(/session expired/i), 'nothing expired').toBeNull();
  });
});

describe('a refused token', () => {
  it('still prompts, so the real case is not silenced', () => {
    // The whole risk of the fix above: suppressing the false alarm must not
    // suppress this.
    status = CONNECTED;
    const view = renderGuard();
    status = REFUSED;
    view.rerender(
      <QueryClientProvider client={new QueryClient()}><KiteSessionGuard /></QueryClientProvider>,
    );
    // Inside act(): the prompt is opened from a setTimeout, and without this
    // React drops the state update and the modal never mounts — which would make
    // this test pass for the wrong reason if it were asserting absence.
    act(() => { vi.advanceTimersByTime(20_000); });
    expect(screen.getByText(/session expired/i)).toBeInTheDocument();
  });
});
