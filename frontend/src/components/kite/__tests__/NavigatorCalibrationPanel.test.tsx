import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import React from 'react';
import { NavigatorCalibrationPanel } from '../NavigatorCalibrationPanel';
import type { CalibrationCriteria, CalibrationReport } from '../../../types/navigator';

function criteria(overrides: Partial<CalibrationCriteria> = {}): CalibrationCriteria {
  return {
    eligible: false,
    criteria: [
      { key: 'min_sessions', label: 'At least 20 trading sessions captured', passed: false, detail: '12 of 20 sessions' },
      { key: 'min_evaluation_samples', label: 'At least 30 scored decisions out-of-sample', passed: true, detail: '41 of 30 scored' },
    ],
    ...overrides,
  };
}

const allPassing: CalibrationCriteria = {
  eligible: true,
  criteria: [
    { key: 'min_sessions', label: 'At least 20 trading sessions captured', passed: true, detail: '24 of 20 sessions' },
    { key: 'min_evaluation_samples', label: 'At least 30 scored decisions out-of-sample', passed: true, detail: '41 of 30 scored' },
  ],
};

function report(): CalibrationReport {
  const w = {
    label: 'x', sessions: 12, session_dates: [], total_decisions: 60, actionable: 40,
    actionable_scored: 38, actionable_hits: 21, hit_rate: 0.5526, mean_return_pct: 0.42,
    no_data: 3, no_data_rate: 0.05, unscorable: 2,
  };
  return {
    model_version: 'navigator_calibration_v1', horizon_bars: 6, total_decisions: 120,
    underlyings: ['NIFTY 50'],
    caveats: ['Returns are gross — no brokerage, spread, or slippage is deducted.'],
    calibration: { ...w, label: 'calibration' },
    evaluation: { ...w, label: 'evaluation' },
  };
}

const generateMutate = vi.fn();
const promoteMutate = vi.fn();
const demoteMutate = vi.fn();
let calibrationData: Record<string, unknown> | undefined;
let generateResult: Record<string, unknown> | undefined;

vi.mock('../../../hooks/useNavigator', () => ({
  useNavigatorCalibration: () => ({ data: calibrationData, isLoading: false }),
  useGenerateCalibrationReport: () => ({
    mutate: generateMutate, isPending: false, isError: false, error: null, data: generateResult,
  }),
  usePromoteCalibration: () => ({ mutate: promoteMutate, isPending: false, isError: false, error: null }),
  useDemoteCalibration: () => ({ mutate: demoteMutate, isPending: false }),
}));

describe('NavigatorCalibrationPanel', () => {
  beforeEach(() => {
    generateMutate.mockClear();
    promoteMutate.mockClear();
    demoteMutate.mockClear();
    generateResult = undefined;
    calibrationData = {
      calibration_readiness: 'not_ready', calibration_report_id: null, revision: 3,
      latest_report: null, criteria: null,
    };
  });

  it('shows not-calibrated and invites a first report when nothing has run', () => {
    render(<NavigatorCalibrationPanel />);
    expect(screen.getByText('Not yet calibrated')).toBeInTheDocument();
    expect(screen.getByText(/No report yet/)).toBeInTheDocument();
  });

  it('generating a report never promotes — it only asks the server to score', () => {
    render(<NavigatorCalibrationPanel />);
    fireEvent.click(screen.getByRole('button', { name: /Generate report/i }));
    expect(generateMutate).toHaveBeenCalledTimes(1);
    expect(promoteMutate).not.toHaveBeenCalled();
  });

  it('lists each criterion with its real progress, not just a pass/fail mark', () => {
    calibrationData = { ...calibrationData, criteria: criteria() };
    render(<NavigatorCalibrationPanel />);
    expect(screen.getByText('At least 20 trading sessions captured')).toBeInTheDocument();
    expect(screen.getByText('12 of 20 sessions')).toBeInTheDocument();
    expect(screen.getByText('1 still outstanding')).toBeInTheDocument();
  });

  it('keeps Promote disabled while any criterion is outstanding', () => {
    calibrationData = { ...calibrationData, criteria: criteria(), calibration_report_id: 'navcal_x' };
    render(<NavigatorCalibrationPanel />);
    expect(screen.getByRole('button', { name: /Promote to ready/i })).toBeDisabled();
  });

  it('enables Promote once every criterion passes, and requires a confirm click', () => {
    calibrationData = { ...calibrationData, criteria: allPassing, calibration_report_id: 'navcal_x' };
    render(<NavigatorCalibrationPanel />);
    const btn = screen.getByRole('button', { name: /Promote to ready/i });
    expect(btn).not.toBeDisabled();

    fireEvent.click(btn);
    expect(promoteMutate).not.toHaveBeenCalled(); // first click only arms it
    fireEvent.click(screen.getByRole('button', { name: /Click again to confirm/i }));
    expect(promoteMutate).toHaveBeenCalledWith(
      { report_id: 'navcal_x', expected_revision: 3 },
      expect.anything(),
    );
  });

  it('a freshly generated report takes precedence over the stored one', () => {
    calibrationData = { ...calibrationData, criteria: criteria() };
    generateResult = { report_id: 'navcal_fresh', report: report(), criteria: allPassing };
    render(<NavigatorCalibrationPanel />);
    expect(screen.getByText('all clear')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: /Promote to ready/i }));
    fireEvent.click(screen.getByRole('button', { name: /Click again to confirm/i }));
    expect(promoteMutate).toHaveBeenCalledWith(
      expect.objectContaining({ report_id: 'navcal_fresh' }), expect.anything(),
    );
  });

  it('surfaces the report windows and never hides the gross-returns caveat', () => {
    generateResult = { report_id: 'navcal_fresh', report: report(), criteria: allPassing };
    render(<NavigatorCalibrationPanel />);
    expect(screen.getByText('Tuning window')).toBeInTheDocument();
    expect(screen.getByText('Untouched check')).toBeInTheDocument();
    expect(screen.getByText(/Returns are gross/)).toBeInTheDocument();
  });

  it('says so loudly when nothing could be scored, instead of passing zeros off as accuracy', () => {
    const broken = report();
    broken.warnings = [
      'Scored none of the 31 recorded decisions because no price history was available. '
      + 'The counts below reflect that, not Navigator\'s actual accuracy.',
    ];
    generateResult = { report_id: 'navcal_x', report: broken, criteria: criteria() };
    render(<NavigatorCalibrationPanel />);
    expect(screen.getByText(/couldn't score everything/i)).toBeInTheDocument();
    expect(screen.getByText(/not Navigator's actual accuracy/)).toBeInTheDocument();
  });

  it('shows no warning banner on a clean report', () => {
    generateResult = { report_id: 'navcal_x', report: report(), criteria: allPassing };
    render(<NavigatorCalibrationPanel />);
    expect(screen.queryByText(/couldn't score everything/i)).not.toBeInTheDocument();
  });

  it('once ready, shows the unlocked state and offers revoke instead of promote', () => {
    calibrationData = {
      calibration_readiness: 'ready', calibration_report_id: 'navcal_x', revision: 7,
      latest_report: null, criteria: allPassing,
    };
    render(<NavigatorCalibrationPanel />);
    expect(screen.getByText('Ready — gate unlocked')).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /Promote to ready/i })).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: /Revoke/i }));
    expect(demoteMutate).toHaveBeenCalledWith({ expected_revision: 7 });
  });
});
