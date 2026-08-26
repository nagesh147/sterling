/**
 * The instrument strip's presets.
 *
 * Twelve renderers are only maintainable if they agree on the things that must
 * not vary — the facts they read, the controls they expose, and the fact that
 * scale actually scales. Those invariants are tested across every preset rather
 * than one by one, so a thirteenth is covered the moment it is registered.
 */
import React from 'react';
import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent, within } from '@testing-library/react';
import { TickerTile, type TileData } from '../TickerTile';
import { TILE_STYLES, isTileStyle, tileStyleMeta, DEFAULT_TILE_STYLE, type TickerTileStyle } from '../../../../utils/tickerTileStyles';

const DATA: TileData = {
  symbol: 'NSE:NIFTY 50',
  primary: 'NIFTY 50',
  secondary: '',
  market: 'INDEX',
  last: 24231.85,
  change: 153.55,
  changePct: 0.64,
  open: 24110.2,
  high: 24268.4,
  low: 24081.75,
  series: [24090, 24140, 24175, 24232],
};

const ALL = TILE_STYLES.map((s) => s.id as TickerTileStyle);

describe('every preset', () => {
  it.each(ALL)('%s renders the price', (style) => {
    render(<TickerTile style={style} data={DATA} scale={1} />);
    // Formatting differs by preset — some drop the decimals — so match the
    // integer part, which every one of them must show.
    expect(document.body.textContent).toMatch(/24,231/);
  });

  it.each(ALL)('%s exposes the unpin control when one is offered', (style) => {
    const onUnpin = vi.fn();
    render(<TickerTile style={style} data={DATA} scale={1} onUnpin={onUnpin} />);
    fireEvent.click(screen.getByRole('button', { name: /Unpin NSE:NIFTY 50/ }));
    expect(onUnpin).toHaveBeenCalledWith('NSE:NIFTY 50');
  });

  it.each(ALL)('%s omits the unpin control when none is offered', (style) => {
    render(<TickerTile style={style} data={DATA} scale={1} />);
    expect(screen.queryByRole('button', { name: /Unpin/ })).not.toBeInTheDocument();
  });

  it.each(ALL)('%s opens the chart from mouse and keyboard', (style) => {
    const onOpenChart = vi.fn();
    render(<TickerTile style={style} data={DATA} scale={1} onOpenChart={onOpenChart} />);
    const tile = screen.getByRole('button', { name: /NIFTY 50, 24,231/ });
    fireEvent.click(tile);
    fireEvent.keyDown(tile, { key: 'Enter' });
    expect(onOpenChart).toHaveBeenCalledTimes(2);
    expect(onOpenChart).toHaveBeenCalledWith('NSE:NIFTY 50');
  });

  it.each(ALL)('%s survives a quote with nothing in it', (style) => {
    // A pinned instrument that has not ticked yet must not blank the strip.
    const empty: TileData = { ...DATA, last: null, change: null, changePct: null, open: null, high: null, low: null, series: [] };
    expect(() => render(<TickerTile style={style} data={empty} scale={1} />)).not.toThrow();
    expect(document.body.textContent).toMatch(/—|NIFTY/);
  });
});

describe('scale', () => {
  // The tape sizes itself from the strip, so it has no fixed width to compare.
  const sized = ALL.filter((s) => s !== 'tape' && s !== 'minimal');

  it.each(sized)('%s grows with scale', (style) => {
    const { container: small } = render(<TickerTile style={style} data={DATA} scale={0.8} />);
    const { container: large } = render(<TickerTile style={style} data={DATA} scale={1.3} />);
    const fontOf = (c: HTMLElement) => {
      const el = c.querySelector('[style*="font-size"]') as HTMLElement | null;
      return el ? parseFloat(el.style.fontSize) : 0;
    };
    expect(fontOf(large)).toBeGreaterThan(fontOf(small));
  });
});

describe('direction', () => {
  it('colours a rise and a fall differently', () => {
    const { container: up } = render(<TickerTile style="card" data={DATA} scale={1} />);
    const { container: down } = render(<TickerTile style="card" data={{ ...DATA, change: -153.55, changePct: -0.64 }} scale={1} />);
    const colours = (c: HTMLElement) => [...c.querySelectorAll<HTMLElement>('[style*="color"]')].map((e) => e.style.color);
    expect(colours(up).some((x) => x.includes('green'))).toBe(true);
    expect(colours(down).some((x) => x.includes('red'))).toBe(true);
  });

  it('stays neutral on no change, rather than claiming a direction', () => {
    const { container } = render(<TickerTile style="card" data={{ ...DATA, change: 0, changePct: 0 }} scale={1} />);
    const colours = [...container.querySelectorAll<HTMLElement>('[style*="color"]')].map((e) => e.style.color);
    expect(colours.some((x) => x.includes('green') || x.includes('red'))).toBe(false);
  });
});

describe('presets that promise something specific', () => {
  it('Day range plots where the price sits between low and high', () => {
    const { container } = render(<TickerTile style="range" data={DATA} scale={1} />);
    const bar = container.querySelector('[title*="Low"]');
    expect(bar).toBeTruthy();
    const marker = bar!.querySelector('span') as HTMLElement;
    // (24231.85 - 24081.75) / (24268.4 - 24081.75) = 0.804
    expect(parseFloat(marker.style.left)).toBeCloseTo(80.4, 0);
  });

  it('Day range omits the marker rather than guessing when there is no range', () => {
    const { container } = render(<TickerTile style="range" data={{ ...DATA, low: null, high: null }} scale={1} />);
    expect(container.querySelector('[title="Day range unavailable"]')?.querySelector('span')).toBeFalsy();
  });

  it('Quote shows the day’s open, high and low', () => {
    render(<TickerTile style="quote" data={DATA} scale={1} />);
    for (const label of ['OPEN', 'HIGH', 'LOW']) {
      expect(screen.getByText(label)).toBeInTheDocument();
    }
  });

  it('Price only keeps the symbol reachable on hover', () => {
    render(<TickerTile style="minimal" data={DATA} scale={1} />);
    // Nothing on screen but the number, so the title has to carry the rest.
    expect(document.querySelector('[title*="NIFTY 50"]')).toBeTruthy();
  });
});

describe('the preset registry', () => {
  it('names each preset once', () => {
    const ids = TILE_STYLES.map((s) => s.id);
    expect(new Set(ids).size).toBe(ids.length);
  });

  it('offers more than ten', () => {
    expect(TILE_STYLES.length).toBeGreaterThanOrEqual(10);
  });

  it('describes each one with more than its own name', () => {
    for (const s of TILE_STYLES) {
      expect(s.hint.length, s.id).toBeGreaterThan(20);
      expect(s.hint.toLowerCase()).not.toBe(s.label.toLowerCase());
    }
  });

  it('falls back to the default for anything unrecognised', () => {
    expect(isTileStyle('nonsense')).toBe(false);
    expect(tileStyleMeta('nonsense' as TickerTileStyle).id).toBe(DEFAULT_TILE_STYLE);
  });
});
