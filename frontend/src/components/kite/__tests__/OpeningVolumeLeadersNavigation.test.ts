import { describe, expect, it } from 'vitest';
import simpleTerminal from '../../../pages/SimpleTerminal.tsx?raw';
import kiteTab from '../KiteTab.tsx?raw';

describe('Opening Leaders navigation contract', () => {
  it('places the tab immediately after PCR in the Kite header', () => {
    expect(simpleTerminal).toMatch(
      /id: 'pcr' as const, label: 'PCR'[\s\S]*?id: 'openingLeaders' as const, label: 'Opening Leaders'/,
    );
    expect(simpleTerminal.indexOf("id: 'openingLeaders'")).toBeLessThan(simpleTerminal.indexOf("id: 'orders'"));
  });

  it('routes the tab to the live opening-volume pane', () => {
    expect(kiteTab).toContain("nav === 'openingLeaders'");
    expect(kiteTab).toContain('<OpeningVolumeLeadersPane');
  });
});
