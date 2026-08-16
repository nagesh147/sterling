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

  it('renders the Adaptive Edge pictorial visualizer, architecture pipeline, and interactive simulation', () => {
    render(<HelpPane />);
    expect(screen.getByText(/Adaptive Edge — Hybrid Microstructure & Scalp Engine/)).toBeInTheDocument();
    expect(screen.getAllByText(/Tape & Order Flow Ingestion/).length).toBeGreaterThan(0);
    expect(screen.getAllByText(/Microstructure & POC Anchors/).length).toBeGreaterThan(0);
    expect(screen.getByText(/Dynamic Scalp Escalation & Risk Matrix/)).toBeInTheDocument();
    expect(screen.getByText(/Interactive Sandbox Simulation & Real-Time P&L Engine/)).toBeInTheDocument();
    expect(screen.getByText(/Editable Trade & Execution Parameters/)).toBeInTheDocument();
    expect(screen.getByText(/Unrealized MTM P&L/)).toBeInTheDocument();
    expect(screen.getByText(/How Trailing Stop Loss \(TSL\) Protects You Step-by-Step/)).toBeInTheDocument();
    expect(screen.getByText(/Real-Time Premium Trajectory & Bounds Visualizer/)).toBeInTheDocument();
  });
});
