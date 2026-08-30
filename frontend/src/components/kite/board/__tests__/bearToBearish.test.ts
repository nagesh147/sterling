import { describe, expect, it } from 'vitest';
import { bearToBearishToBoard } from '../bearToBearishAdapter';
import type { BearToBearishSnapshotResponse } from '../../../../hooks/useBearToBearish';

describe('bearToBearishAdapter', () => {
  it('converts BearToBearish snapshot to BoardSignal list', () => {
    const mockSnap: BearToBearishSnapshotResponse = {
      generated_ms: 1700000000000,
      scanning: false,
      scanning_label: 'Complete',
      rows: [
        {
          id: 'btb-NIFTY-1',
          underlying: 'NIFTY',
          symbol: 'NIFTY26SEP24000PE',
          exchange: 'NFO',
          direction: 'short',
          status: 'armed',
          timestamp_ms: 1700000000000,
          pcr_open: 0.80,
          pcr_current: 0.58,
          pcr_change_5m: -0.05,
          lower_high_price: 24150,
          entry_price: 24000,
          stop_loss: 24150,
          target_price: 23700,
          score: 90,
          reason: 'PCR drop below 0.60 + Lower High structure',
          option_type: 'PE',
          strike: 24000,
          expiry: '2026-09-24',
          lot_size: 25,
        },
      ],
      pcr_history: {},
      config: { enabled: true, auto_execute: true },
    };

    const boardSignals = bearToBearishToBoard(mockSnap);
    expect(boardSignals).toHaveLength(1);
    const sig = boardSignals[0];
    const leg = sig.children?.[0] ?? sig;
    expect(sig.engine).toBe('bear_to_bearish');
    expect(sig.underlying).toBe('NIFTY');
    expect(leg.direction).toBe('short');
    expect(leg.status).toBe('armed');
    expect(leg.levels.entry).toBe(24000);
    expect(leg.levels.stop).toBe(24150);
    expect(leg.levels.target).toBe(23700);
    expect(sig.origin?.label).toContain('PCR 0.58');
  });
});
