import React from 'react';
import { render, screen, fireEvent } from '@testing-library/react';
import { describe, it, expect } from 'vitest';
import {
  AdaptiveEdgePositionCalculator,
  getInstrumentLotSize,
} from '../AdaptiveEdgePositionCalculator';

describe('AdaptiveEdgePositionCalculator', () => {
  it('detects instrument lot sizes accurately', () => {
    expect(getInstrumentLotSize('NIFTY 50')).toBe(25);
    expect(getInstrumentLotSize('NIFTY24AUG24500CE')).toBe(25);
    expect(getInstrumentLotSize('BANKNIFTY')).toBe(15);
    expect(getInstrumentLotSize('FINNIFTY')).toBe(25);
    expect(getInstrumentLotSize('MIDCPNIFTY')).toBe(50);
    expect(getInstrumentLotSize('SENSEX')).toBe(10);
    expect(getInstrumentLotSize('RELIANCE')).toBe(250);
    expect(getInstrumentLotSize('HDFCBANK')).toBe(550);
  });

  it('renders default entry, covered points, unrealized P&L, and defined SL risk', () => {
    render(
      <AdaptiveEdgePositionCalculator
        symbol="NIFTY 50"
        defaultEntryPrice={500}
        defaultSl={400}
        defaultTsl={520}
        defaultExit={650}
        currentLtp={525}
        optionType="CE"
      />,
    );

    expect(screen.getByText('Position Sizing & P&L Calculator')).toBeInTheDocument();
    // Default 1 Lot * 25 Qty = 25 Qty
    expect(screen.getByText('25 Qty (1 Lot × 25)')).toBeInTheDocument();
    // Capital Deployed: 500 * 25 = ₹12,500
    expect(screen.getByText('₹12,500')).toBeInTheDocument();
    // Covered Points: 525 - 500 = +25 pts (+5%)
    expect(screen.getByText('+25 pts')).toBeInTheDocument();
    expect(screen.getByText('(+5%)')).toBeInTheDocument();
    // Unrealized P&L: 25 pts * 25 Qty = +₹625
    expect(screen.getByText('+₹625')).toBeInTheDocument();
    // Hard SL Risk: (500 - 400) * 25 = -₹2,500
    expect(screen.getByText('-₹2,500')).toBeInTheDocument();
    // TSL Locked: (520 - 500) * 25 = +₹500
    expect(screen.getByText('+₹500')).toBeInTheDocument();
    // Target Reward: (650 - 500) * 25 = +₹3,750
    expect(screen.getByText('+₹3,750')).toBeInTheDocument();
  });

  it('updates calculations live when changing lots and editing entry price', () => {
    render(
      <AdaptiveEdgePositionCalculator
        symbol="NIFTY 50"
        defaultEntryPrice={500}
        defaultSl={400}
        defaultTsl={500}
        defaultExit={600}
        currentLtp={550}
      />,
    );

    // Increase lots from 1 to 2
    const plusBtn = screen.getByRole('button', { name: '+' });
    fireEvent.click(plusBtn);

    // Now 2 Lots * 25 = 50 Qty
    expect(screen.getByText('50 Qty (2 Lots × 25)')).toBeInTheDocument();
    // Capital Deployed: 500 * 50 = ₹25,000
    expect(screen.getByText('₹25,000')).toBeInTheDocument();
    // Unrealized P&L: (550 - 500) * 50 = +₹2,500
    expect(screen.getByText('+₹2,500')).toBeInTheDocument();

    // Reset button appears when customized
    const resetBtn = screen.getByRole('button', { name: 'Reset Defaults' });
    fireEvent.click(resetBtn);

    // Reverts back to 1 lot
    expect(screen.getByText('25 Qty (1 Lot × 25)')).toBeInTheDocument();
    expect(screen.getByText('₹12,500')).toBeInTheDocument();
  });
});
