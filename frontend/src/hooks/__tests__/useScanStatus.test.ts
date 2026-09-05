/**
 * The status line has to say WHOSE scan it is showing.
 *
 * It rendered `activity.scanning_label` alone — a bare "TCS OCT 2300 PE" with
 * nothing naming the strategy. `/activity` is SuperTrend's endpoint, so that label
 * is always SuperTrend's; during a five-engine re-scan the line showed a SuperTrend
 * contract for its turn and then dropped to "AUTO" for the other four. From the
 * outside that is indistinguishable from a label unrelated to whatever is
 * scanning, which is exactly how it was reported.
 */
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { renderHook } from '@testing-library/react';

let activity: { scanning?: boolean; scanning_label?: string } | undefined;

vi.mock('../useSterlingKiteEngine', () => ({
  useEngineActivity: () => ({ data: activity }),
}));

import { useScanStatus } from '../useScanStatus';
import { useScanActivity } from '../../store/useScanActivity';

beforeEach(() => {
  activity = undefined;
  useScanActivity.getState().setCurrent(null);
});

describe('useScanStatus', () => {
  it('names SuperTrend and the contract it is reading', () => {
    activity = { scanning: true, scanning_label: 'TCS OCT 2300 PE' };
    const { result } = renderHook(() => useScanStatus());
    expect(result.current.scanning).toBe(true);
    expect(result.current.engineLabel).toBe('SuperTrend');
    expect(result.current.detail).toBe('TCS OCT 2300 PE');
  });

  it('names the engine a manual sweep is on, without inventing a contract', () => {
    // Gamma Move has a scan endpoint and publishes no progress. Naming a contract
    // it is not on would be worse than the bare label this replaces.
    useScanActivity.getState().setCurrent('gamma_move');
    const { result } = renderHook(() => useScanStatus());
    expect(result.current.scanning).toBe(true);
    expect(result.current.engineLabel).toBe('Gamma Move');
    expect(result.current.detail).toBeNull();
  });

  it('lets SuperTrend’s live feed win over the sweep position', () => {
    // The sweep runs SuperTrend first; while it does, the feed knows the item and
    // the sweep only knows the engine. Prefer the one that knows more.
    activity = { scanning: true, scanning_label: 'RELIANCE OCT 1400 CE' };
    useScanActivity.getState().setCurrent('supertrend');
    const { result } = renderHook(() => useScanStatus());
    expect(result.current.detail).toBe('RELIANCE OCT 1400 CE');
  });

  it('reports nothing scanning when neither source says so', () => {
    activity = { scanning: false, scanning_label: 'TCS OCT 2300 PE' };
    const { result } = renderHook(() => useScanStatus());
    // The stale label must NOT surface: the backend clears it at the end of a
    // scan, but a client that reads it regardless would show the last contract
    // forever, which is the bug as it was described.
    expect(result.current.scanning).toBe(false);
    expect(result.current.engineLabel).toBeNull();
    expect(result.current.detail).toBeNull();
  });

  it('says scanning even when the engine name is somehow unknown', () => {
    activity = { scanning: true };
    const { result } = renderHook(() => useScanStatus());
    expect(result.current.scanning).toBe(true);
    expect(result.current.detail).toBeNull();
  });
});
