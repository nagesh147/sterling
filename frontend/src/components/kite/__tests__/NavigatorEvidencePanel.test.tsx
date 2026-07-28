import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import React from 'react';
import { NavigatorEvidencePanel } from '../NavigatorEvidencePanel';
import type { NavigatorDecision } from '../../../types/navigator';

function decision(overrides: Partial<NavigatorDecision> = {}): NavigatorDecision {
  return {
    decision_id: 'nav_1', schema_version: 1, config_revision: 1, model_versions: { fusion: 'fusion_v1' },
    generated_at_ms: Date.now(), bar_close_ms: Date.now() - 5000, activation_watermark_ms: 0,
    base_signal_id: 's1', trigger: 'base_fresh', direction: 'long', status: 'CONFIRMED',
    base_score: 85, suite_score: 78, effective_score: 82, execution_eligible: true, data_quality: 'ok',
    reason_codes: ['OK'],
    avwap: { component: 'avwap', as_of_bar_close_ms: 1, observed_at_ms: 2, direction: 1, confidence_100: 90, quality: 'ok', reason_codes: ['OK'], diagnostics: {} },
    volatility: { component: 'volatility', as_of_bar_close_ms: 1, observed_at_ms: 2, direction: 1, confidence_100: 70, quality: 'ok', reason_codes: ['OK'], diagnostics: {} },
    option_flow: { component: 'option_flow', as_of_bar_close_ms: 1, observed_at_ms: 2, direction: 0, confidence_100: 0, quality: 'unavailable', reason_codes: ['CHAIN_UNAVAILABLE'], diagnostics: {} },
    gamma: { component: 'gamma', as_of_bar_close_ms: 1, observed_at_ms: 2, direction: 0, confidence_100: 0, quality: 'unavailable', reason_codes: ['GAMMA_UNAVAILABLE_OPTIONAL'], diagnostics: {} },
    ...overrides,
  };
}

describe('NavigatorEvidencePanel', () => {
  it('shows the status badge and distinct raw/suite/effective scores', () => {
    render(<NavigatorEvidencePanel decision={decision()} />);
    expect(screen.getByText('Confirmed')).toBeInTheDocument();
    expect(screen.getByText('85')).toBeInTheDocument(); // raw
    expect(screen.getByText('78')).toBeInTheDocument(); // suite
    expect(screen.getByText('82')).toBeInTheDocument(); // effective
  });

  it('makes an unavailable component inspectable with its reason codes, not a bare dot', () => {
    render(<NavigatorEvidencePanel decision={decision()} />);
    expect(screen.getByText(/CHAIN_UNAVAILABLE/)).toBeInTheDocument();
    expect(screen.getByText(/GAMMA_UNAVAILABLE_OPTIONAL/)).toBeInTheDocument();
  });

  it('surfaces reasons for a NO_DATA decision', () => {
    render(<NavigatorEvidencePanel decision={decision({ status: 'NO_DATA', effective_score: null, suite_score: null, reason_codes: ['PRICE_BARS_MISSING'] })} />);
    expect(screen.getByText('No data')).toBeInTheDocument();
    expect(screen.getByText(/PRICE_BARS_MISSING/)).toBeInTheDocument();
  });

  it('surfaces reasons for a CONFLICT decision', () => {
    render(<NavigatorEvidencePanel decision={decision({ status: 'CONFLICT', reason_codes: ['STRONG_OPPOSING_EVIDENCE'] })} />);
    expect(screen.getByText('Conflict')).toBeInTheDocument();
    expect(screen.getByText(/STRONG_OPPOSING_EVIDENCE/)).toBeInTheDocument();
  });

  it('shows execution eligibility and config revision for auditability', () => {
    render(<NavigatorEvidencePanel decision={decision()} />);
    expect(screen.getByText(/Execution eligible: yes/)).toBeInTheDocument();
    expect(screen.getByText(/config rev 1/)).toBeInTheDocument();
  });
});
