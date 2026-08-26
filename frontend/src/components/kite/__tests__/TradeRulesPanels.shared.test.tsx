/**
 * The Manual Trade / Algo Trade split is only honest if the shared settings say so.
 *
 * These pages exist so a reader knows which rules apply to them — that was the whole
 * point of replacing the single filtered page. But stop_mode, expiry_square_off_days
 * and time_stop_bars are ONE stored value rendered on both (registry.ts marks all
 * three applies:'both'), so setting a stop mode for your own hand-placed buys also
 * moves it for the algo. The disclosure that said so was dropped in the settings
 * rework, which turned the split itself into the misleading part.
 */
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import React from 'react';
import { ManualRulesPanel, AutomaticRulesPanel } from '../TradeRulesPanels';

let cfg: Record<string, unknown>;
const patch = vi.fn();

vi.mock('../config/useConfigPatch', () => ({
  useConfigPatch: () => ({ cfg, patch, saving: false }),
}));
vi.mock('../../../hooks/useSterlingKiteEngine', () => ({
  useEngineSignals: () => ({ data: { rows: [] } }),
}));
vi.mock('../../../hooks/useNavigator', () => ({
  useNavigatorConfig: () => ({ data: { record: { config: { enabled: false } } } }),
}));
vi.mock('../DirectionalModePanel', () => ({
  DirectionalModePanel: () => <div>Directional mode panel</div>,
}));

beforeEach(() => {
  patch.mockClear();
  cfg = {
    stop_mode: 'both',
    protect_manual_orders: true,
    expiry_square_off_days: 1,
    time_stop_bars: 0,
    auto_execute: false,
    risk_sizing: true,
    risk_pct: 1,
    max_lots: 10,
    strike_moneyness: ['ATM'],
    scan_expiries_indices: ['weekly', 'monthly'],
    directional_mode: false,
    vehicle: 'otm_options',
    enabled_vehicles: ['otm_options'],
  };
});

describe('shared settings disclose that they are shared', () => {
  it('the manual page says its stop mode also moves the algo', () => {
    render(<ManualRulesPanel />);
    const notes = screen.getAllByText(/One setting, shared with/i);
    expect(notes.length).toBeGreaterThan(0);
    expect(notes.some((n) => /Algo Trade/i.test(n.textContent ?? ''))).toBe(true);
  });

  it('the algo page says its stop mode also moves the manual one', () => {
    render(<AutomaticRulesPanel />);
    const notes = screen.getAllByText(/One setting, shared with/i);
    expect(notes.length).toBeGreaterThan(0);
    expect(notes.some((n) => /Manual Trade/i.test(n.textContent ?? ''))).toBe(true);
  });

  it('never claims a page shares with itself', () => {
    render(<ManualRulesPanel />);
    for (const note of screen.getAllByText(/One setting, shared with/i)) {
      expect(note.textContent).not.toMatch(/Manual Trade/i);
    }
  });
});
