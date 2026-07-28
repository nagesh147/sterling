import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { HelpPane } from '../HelpPane';

describe('HelpPane', () => {
  it('renders the intro and all four scenario/settings sections', () => {
    render(<HelpPane />);
    expect(screen.getByText('Help — Signals and the Value-Flow Navigator')).toBeInTheDocument();
    expect(screen.getByText('What the Value-Flow Navigator is')).toBeInTheDocument();
    expect(screen.getByText('The 4 signal lenses')).toBeInTheDocument();
    expect(screen.getByText('The 3 new Navigator settings')).toBeInTheDocument();
    expect(screen.getByText('Quick-pick: I want to…')).toBeInTheDocument();
  });

  it('explains all 4 lenses by name', () => {
    render(<HelpPane />);
    for (const label of ['SuperTrend', 'Navigator', 'Combined', 'Common']) {
      expect(screen.getAllByText(label).length).toBeGreaterThan(0);
    }
  });

  it('explains all 3 new settings by name', () => {
    render(<HelpPane />);
    expect(screen.getByText('Structure Radar')).toBeInTheDocument();
    expect(screen.getByText('Signal Origination')).toBeInTheDocument();
    expect(screen.getByText('Auto-Execute Originated')).toBeInTheDocument();
  });

  it('lists every quick-pick scenario', () => {
    render(<HelpPane />);
    expect(screen.getByText(/Ignore Navigator entirely/)).toBeInTheDocument();
    expect(screen.getByText(/Let it trade on its own/)).toBeInTheDocument();
  });
});
